import time
import os
from urllib.parse import urlparse, unquote

from qtpy.QtCore import Signal, QByteArray, QObject, QUrl, QThread, Qt, QRect, QRectF
from qtpy.QtGui import QImage, QPainter, QBrush, QPen, QPixmap
from qtpy.QtNetwork import QNetworkReply, QNetworkRequest, QNetworkAccessManager
from typing import List, Any, Dict, Optional, NamedTuple
from cv2 import VideoCapture
import urllib.request
from io import BytesIO
from PIL import Image, ImageQt, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

_MJPEG_SUFFIXES = (".mjpg", ".mjpeg", ".cgi")


def _is_mjpeg_url(url: str) -> bool:
    """Check if a URL points to an MJPEG stream, ignoring query parameters."""
    path = urlparse(url.lower()).path
    return any(path.endswith(suffix) for suffix in _MJPEG_SUFFIXES)


def local_file_path_from_source(source: str) -> "Optional[str]":
    source = (source or "").strip()
    if not source:
        return None

    parsed = urlparse(source)
    scheme = parsed.scheme.lower()
    if scheme in ("http", "https"):
        return None

    if scheme == "file":
        raw_path = unquote(parsed.path or "")
        if parsed.netloc and parsed.netloc != "localhost":
            raw_path = f"//{parsed.netloc}{raw_path}"
        return os.path.abspath(os.path.expanduser(raw_path))

    is_windows_drive = len(scheme) == 1 and source[1:3] in (":\\", ":/")
    if scheme and not is_windows_drive:
        return None

    return os.path.abspath(os.path.expanduser(source))


class Downloader(QObject):
    imageReady = Signal(object)

    def __init__(self, parent: "QObject|None" = None) -> None:
        super(Downloader, self).__init__(parent)
        self.manager = QNetworkAccessManager()
        self.url: str = "http://localhost:9998/jpg/image.jpg"
        self.request = QNetworkRequest()
        self.request.setUrl(QUrl(self.url))
        self.buffer = QByteArray()
        self.reply: Optional[QNetworkReply] = None
        self.isMjpegFeed = False
        self.isLocalFile = False
        self.localFilePath: "Optional[str]" = None

    def setUrl(self, url: str) -> None:
        self.url = url
        self.request.setUrl(QUrl(self.url))
        if self.reply:
            self.reply.deleteLater()
            self.reply = None
        self.localFilePath = local_file_path_from_source(self.url)
        self.isLocalFile = self.localFilePath is not None

        if self.isLocalFile:
            self.isMjpegFeed = False
            self.mjpegCamera = None
        elif _is_mjpeg_url(self.url):
            self.isMjpegFeed = True
            self.mjpegCamera = VideoCapture(self.url)
        else:
            self.isMjpegFeed = False
            self.mjpegCamera = None

    def downloadData(self) -> None:
        """Only request a new image if this is the first/last completed."""
        if self.isLocalFile and self.localFilePath:
            qimage = QImage(self.localFilePath)
            if not qimage.isNull():
                self.imageReady.emit(qimage)
        elif self.reply is None and not self.isMjpegFeed:
            self.reply = self.manager.get(self.request)
            self.reply.finished.connect(self.finished)
        elif self.isMjpegFeed:
            if self.mjpegCamera:
                retVal, currentFrame = self.mjpegCamera.read()
                if currentFrame is not None:
                    height, width = currentFrame.shape[:2]
                    image = QImage(
                        currentFrame, width, height, 3 * width, QImage.Format_RGB888
                    )
                    self.imageReady.emit(image.rgbSwapped())

    def finished(self) -> None:
        """Read the buffer, emit a signal with the new image in it."""
        if self.reply:
            self.buffer = self.reply.readAll()
            self.imageReady.emit(self.buffer)
            self.reply.deleteLater()
            self.reply = None


class VideoThread(QThread):
    imageReady = Signal(object)

    def _emit_cv_frame(self, currentFrame) -> None:
        if currentFrame is None:
            return
        height, width = currentFrame.shape[:2]
        image = QImage(currentFrame, width, height, 3 * width, QImage.Format_RGB888)
        self.imageReady.emit(image.rgbSwapped())

    def _reset_mjpeg_state(self) -> None:
        self._latest_mjpeg_frame = None
        self._next_mjpeg_emit_time = time.monotonic()

    def camera_refresh(self):
        """Only request a new image if this is the first/last completed."""
        if self.isLocalFile and self.localFilePath:
            qimage = QImage(self.localFilePath)
            if not qimage.isNull():
                self._last_local_file_image = qimage
                self.showing_error = False
                self.imageReady.emit(qimage)
            elif self._last_local_file_image is not None:
                self.imageReady.emit(self._last_local_file_image)
            else:
                qimage = self.draw_message(f"Invalid image file: {self.localFilePath}")
                self.imageReady.emit(qimage)
        elif not self.isMjpegFeed:
            try:
                data = urllib.request.urlopen(self.url, timeout=1000 / self.fps).read()
                qimage = QImage.fromData(data)
                self.showing_error = False
                self.imageReady.emit(qimage)
            except urllib.error.URLError:
                qimage = self.draw_message(f"URLError: {self.url}")
                self.imageReady.emit(qimage)
            except TimeoutError:
                qimage = self.draw_message(f"Timeout Error: {self.url}")
                self.imageReady.emit(qimage)
            except OSError as e:
                qimage = self.draw_message(f"OSError {e}: {self.url}")
                self.imageReady.emit(qimage)
            except Exception as e:
                qimage = self.draw_message(f"Exception {e}: {self.url}")
                self.imageReady.emit(qimage)

        elif self.isMjpegFeed and self.mjpegCamera:
            retVal, currentFrame = self.mjpegCamera.read()
            if currentFrame is not None:
                self._emit_cv_frame(currentFrame)

    def __init__(self, *args, fps=5, url="", parent=None, **kwargs):
        # QThread.__init__(self, *args, **kwargs)
        super().__init__(parent)
        self.fps = fps
        self.url = url
        self.showing_error = False
        self.manager = QNetworkAccessManager(self)
        self.request = QNetworkRequest()
        self.request.setUrl(QUrl(self.url))
        self.buffer = QByteArray()
        self.reply: Optional[QNetworkReply] = None
        self.isMjpegFeed = False
        self.isLocalFile = False
        self.localFilePath: "Optional[str]" = None
        self.acquire = True
        self._last_local_file_image: "Optional[QImage]" = None
        self.mjpegCamera = None
        self._latest_mjpeg_frame = None
        self._next_mjpeg_emit_time = time.monotonic()

        self.error_qimage = QPixmap(400, 400).toImage()
        self.painter = QPainter(self.error_qimage)
        self.painter.setBrush(QBrush(Qt.green))
        self.painter.fillRect(QRectF(0, 0, 1000, 1000), Qt.green)
        self.painter.fillRect(QRectF(100, 100, 200, 100), Qt.white)
        self.painter.setPen(QPen(Qt.black))

    def setUrl(self, url: str) -> None:
        old_camera = self.mjpegCamera
        self.url = url
        self.request.setUrl(QUrl(self.url))
        self.localFilePath = local_file_path_from_source(self.url)
        self.isLocalFile = self.localFilePath is not None
        self._last_local_file_image = None

        if self.isLocalFile:
            self.isMjpegFeed = False
            self.mjpegCamera = None
        elif _is_mjpeg_url(self.url):
            self.isMjpegFeed = True
            self.mjpegCamera = VideoCapture(self.url)
            self._reset_mjpeg_state()
        else:
            self.isMjpegFeed = False
            self.mjpegCamera = None

        if old_camera is not None and old_camera is not self.mjpegCamera:
            old_camera.release()

    def setFPS(self, fps: int) -> None:
        self.fps = fps

    def updateCam(self, camera_object):
        self.camera_object = camera_object

    def run(self):
        try:
            while self.acquire:
                if self.isMjpegFeed and self.mjpegCamera:
                    retVal, currentFrame = self.mjpegCamera.read()
                    if retVal and currentFrame is not None:
                        self._latest_mjpeg_frame = currentFrame

                    now = time.monotonic()
                    interval = max(1.0 / max(self.fps, 1), 0.001)
                    if (
                        self._latest_mjpeg_frame is not None
                        and now >= self._next_mjpeg_emit_time
                    ):
                        self._emit_cv_frame(self._latest_mjpeg_frame)
                        self._next_mjpeg_emit_time = now + interval
                    elif not retVal:
                        self.msleep(5)
                else:
                    self.camera_refresh()
                    self.msleep(int(1000 / self.fps))
        finally:
            if self.mjpegCamera is not None:
                self.mjpegCamera.release()
                self.mjpegCamera = None

    def start(self):
        self.acquire = True
        super().start()

    def stop(self):
        self.acquire = False

    def draw_message(self, message: str) -> QImage:
        self.painter.drawText(QRectF(100, 100, 200, 100), message)
        return self.error_qimage
