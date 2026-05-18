from typing import Dict, Any, TYPE_CHECKING, Optional
from qtpy.QtWidgets import (
    QAction,
    QGroupBox,
    QFormLayout,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QSpinBox,
    QLineEdit,
    QCheckBox,
)
from qtpy.QtGui import QImage, QPainter, QPen, QFont, QColor
from qmicroscope.plugins.base_plugin import BasePlugin
from qmicroscope.widgets.color_button import ColorButton
from qmicroscope.utils import convert_str_bool
from qtpy.QtGui import QMouseEvent, QKeyEvent
from qtpy.QtCore import QThread, Signal, QObject, Qt, QTimer
import cv2 as cv
import numpy as np
from pathlib import Path
from datetime import datetime
from epics import PV

if TYPE_CHECKING:
    from qmicroscope.microscope import Microscope


class RecorderThread(QThread):
    """
    A QThread subclass for recording video frames to a file using OpenCV.

    Attributes:
        - video_recorder: cv2.VideoWriter - An instance of cv2.VideoWriter for writing frames to a file.
        - record: bool - A flag indicating whether recording is currently in progress.
        - width: int - The width of the video frames in pixels.
        - height: int - The height of the video frames in pixels.
        - fps: int - The frame rate of the video in frames per second.
        - fourcc: str or int - The FourCC code or string identifying the video codec to use.
        - path: str - The file path where the recorded video will be saved.
        - timer: QTimer - A QTimer instance for scheduling the recording of frames.
        - current_frame: numpy.ndarray - The most recently captured video frame.

    """

    def __init__(self):
        """
        Initializes a new instance of the RecorderThread class.
        """
        super().__init__()
        self.video_recorder = cv.VideoWriter()
        self.record = True
        self.width = 100
        self.height = 100
        self.fps = 5
        self.fourcc = cv.VideoWriter_fourcc(*"avc1")
        self.path = "output.mp4"
        self.timer = QTimer()
        self.timer.timeout.connect(self.write_frame)
        self.current_frame = None

    def start(self, path, fourcc, fps, width, height):
        """
        Starts the video recording process with the specified parameters.

        Args:
            - path: str - The file path where the recorded video will be saved.
            - fourcc: str or int - The FourCC code or string identifying the video codec to use.
            - fps: int - The frame rate of the video in frames per second.
            - width: int - The width of the video frames in pixels.
            - height: int - The height of the video frames in pixels.
        """
        self.set_params(path, fourcc, fps, width, height)
        self._setup_recorder()
        super().start()

    def set_params(
        self, path="output.mp4", fourcc="avc1", fps=5, width=100, height=100
    ):
        """
        Sets the parameters for the video recording process.

        Args:
            - path: str - The file path where the recorded video will be saved.
            - fourcc: str or int - The FourCC code or string identifying the video codec to use.
            - fps: int - The frame rate of the video in frames per second.
            - width: int - The width of the video frames in pixels.
            - height: int - The height of the video frames in pixels.
        """
        self.width = width
        self.height = height
        if isinstance(fourcc, str):
            self.fourcc = cv.VideoWriter(*fourcc)
        else:
            self.fourcc = self.fourcc
        self.fps = fps
        self.path = path

    def _setup_recorder(self):
        """
        Sets up the video recorder instance.
        """
        self.timer.start(int(1000 / self.fps))
        self.video_recorder.open(
            str(self.path), self.fourcc, float(self.fps), (self.width, self.height)
        )

    def stop(self):
        """
        Stops the video recording process.
        """
        self.timer.stop()
        self.video_recorder.release()
        self.record = False

    def run(self):
        """
        Runs the recording loop until recording is stopped.
        """
        while self.record:
            continue

    def handle_frame(self, frame):
        """
        Receives a video frame and prepares it for writing to the output file.

        Args:
            frame (numpy.ndarray): The video frame to be recorded.
        """
        if frame.shape[0] != self.height or frame.shape[1] != self.width:
            self.height = frame.shape[0]
            self.width = frame.shape[1]
            self.video_recorder.release()
            self._setup_recorder()
        # print(f'Frame shape: {frame.shape} w,d: {self.width} {self.height}')
        self.current_frame = frame

    def write_frame(self):
        """
        Writes the current video frame to the output file.
        """
        if self.video_recorder.isOpened() and self.current_frame is not None:
            self.video_recorder.write(self.current_frame)


class RecordPlugin(QObject):
    """
    A plugin to record video from the microscope.

    Args:
        parent (Microscope): The parent Microscope instance.

    Attributes:
        image_ready (Signal): A signal that is emitted when a new frame is ready.
        name (str): The name of the plugin.
        fourcc (int): The fourcc codec used for video recording.
        filename (Path): The path to the output directory.
        current_filepath (Path): The path to the current output file.
        file_extension (str): The extension of the output file.
        recording (bool): True if recording is currently ongoing, False otherwise.
        fps (int): The frames per second of the recorded video.
        width (int): The width of the recorded video.
        height (int): The height of the recorded video.
        hours_per_file (int): The maximum number of hours that can be recorded in a single file.
        number_of_files (int): The maximum number of files that can be stored in the output directory.
        video_recorder_thread (RecorderThread): The thread used for recording video.
        updates_image (bool): True if the image should be updated during recording, False otherwise.
        raw_image (bool): True if the raw image should be recorded, False if a pixmap should be recorded.
        timestamp (bool): True if the current time should be overlaid on the video, False otherwise.
        timestamp_color (QColor): The color of the timestamp.
        timestamp_font_size (int): The font size of the timestamp.
    """

    image_ready = Signal(object)

    def __init__(self, parent: "Optional[Microscope]" = None) -> None: 
        super().__init__(parent)
        # self.parent = parent
        self.name = "Record"
        self.fourcc = cv.VideoWriter_fourcc(*"mp4v")  # H264 avc1 - mp4
        # self.filename = Path('/nsls2/data/fmx/legacy/2023-1/pass-312064/video_test/output')
        self.filename = Path.home() / Path("output")
        self.current_filepath = None
        self.file_extension = "mp4"
        self.recording = False
        self.fps = 5
        self.width = 480
        self.height = 480
        self.hours_per_file = 12
        self.number_of_files = 6
        self.video_recorder_thread = RecorderThread()
        self.image_ready.connect(self.video_recorder_thread.handle_frame)
        self.updates_image = True
        self.raw_image = True
        self.timestamp = False
        self.timestamp_color = QColor.fromRgb(0, 255, 0)
        self.timestamp_font_size = 12
        self.use_epics_pv: bool = False
        self.epics_pv_name: str = ""
        self.epics_pv: "PV|None" = None
        self.start_record_action = QAction("Start Record", self.parent())
        self.start_record_action.triggered.connect(lambda: self._set_record(True))
        self.stop_record_action = QAction("Stop Record", self.parent())
        self.stop_record_action.triggered.connect(lambda: self._set_record(False))

    def qimage_to_mat(self, qimage: QImage):
        qimage = qimage.convertToFormat(QImage.Format.Format_ARGB32)
        qimage = qimage.scaledToWidth(self.width)
        self.height = qimage.height()

        if self.timestamp:
            p = QPainter(qimage)
            p.setPen(QPen(self.timestamp_color))
            p.setFont(QFont("Times", self.timestamp_font_size, QFont.Bold))
            p.drawText(
                qimage.rect(),
                Qt.AlignHCenter,
                f'{datetime.now().strftime("%b-%d-%Y %H:%M:%S")}',
            )
            p.end()

        qimage = qimage.rgbSwapped()
        width = qimage.width()
        height = qimage.height()

        # Get the byte array from the QImage
        byte_array = qimage.bits().asarray(qimage.byteCount())
        # Create a 1D numpy array from the byte array
        image_array = np.frombuffer(byte_array, dtype=np.uint8).reshape(
            (height, width, 4)
        )

        # Convert QImage format to OpenCV format (BGR)
        arr = cv.cvtColor(image_array, cv.COLOR_RGBA2BGR)
        self.image_ready.emit(arr)

    def update_image_data(self, image: QImage):
        """
        Updates the recorded image data.

        Args:
            image: The image to record.
        """
        if self.recording and image:
            if (datetime.now() - self.start_time).seconds >= 3600 * self.hours_per_file:
                # Stop recording after x hours
                self._set_record(False)
                # Restart recording
                self._set_record(True)

            if self.raw_image:
                recorded_image = image.copy()
            else:
                pixmap = self.parent().grab()
                recorded_image = pixmap.toImage().convertToFormat(QImage.Format_RGB888)

            self.qimage_to_mat(recorded_image)

        return image

    def mouse_move_event(self, event: QMouseEvent):
        pass

    def mouse_double_click_event(self, event: QMouseEvent):
        pass

    def mouse_press_event(self, event: QMouseEvent):
        pass

    def mouse_release_event(self, event: QMouseEvent):
        pass

    def mouse_wheel_event(self, event: QMouseEvent):
        pass

    def key_press_event(self, event: QKeyEvent):
        pass

    def key_release_event(self, event: QKeyEvent):
        pass

    def context_menu_entry(self):
        actions = []
        label = "Stop recording" if self.recording else "Start recording"
        if not self.use_epics_pv:
            if self.recording:
                actions.append(self.stop_record_action)
            else:
                actions.append(self.start_record_action)
        return actions

    def _set_record(self, start):
        if start and not self.recording:
            print("Starting record in _set_record")
            self.recording = True
            self.start_time = datetime.now()
            self.current_filepath = Path(self.filename.parent) / Path(
                f'{self.filename.stem}_{self.start_time.strftime("%b-%d-%Y_%H%M%S")}.{self.file_extension}'
            )
            if self.current_filepath.exists():
                print("Already recording")
                return
            print(f"Writing to {self.current_filepath}")
            # self.out = cv.VideoWriter(str(self.current_filepath), self.fourcc, 5.0, (self.width,self.height))
            self.video_recorder_thread.start(
                self.current_filepath, self.fourcc, self.fps, self.width, self.height
            )
        elif not start and self.recording:
            print("Stopping record in _set_record")
            self.recording = False
            if not self.current_filepath:
                return
            self.video_recorder_thread.stop()
            self.video_recorder_thread.wait(500)
            self.end_time = datetime.now()
            self.new_filepath = Path(
                f'{self.current_filepath.stem}_{self.end_time.strftime("%b-%d-%Y_%H%M%S")}.{self.file_extension}'
            )
            self.current_filepath.rename(
                self.current_filepath.parent / self.new_filepath
            )
            print(
                f"Finished writing to {self.current_filepath.parent/self.new_filepath}"
            )
            self._update_files()

    def _update_files(self):
        """Function to check if number of files in the destination folder is correct
        Otherwise delete oldest file(s)
        """
        files_found = list(
            self.filename.parent.glob(f"{self.filename.stem}*.{self.file_extension}")
        )
        if len(files_found) > self.number_of_files:
            files_found = sorted(
                files_found, key=lambda f: f.stat().st_mtime, reverse=True
            )
            files_to_delete = files_found[self.number_of_files :]
            print(f"Files to delete: {files_to_delete}")
            for f in files_to_delete:
                f.unlink(missing_ok=True)

    def _start_epics_record(self, **kwargs):
        if kwargs["pvname"] == self.epics_pv_name:
            if kwargs["value"] == 1 and not self.recording:
                print(f"{self.epics_pv_name} : {kwargs['value']}. START record action")
                self.start_record_action.trigger()
            elif kwargs["value"] == 0 and self.recording:
                print(f"{self.epics_pv_name} : {kwargs['value']}. STOP record action")
                self.stop_record_action.trigger()

    def read_settings(self, settings: Dict[str, Any]):
        self.fps = int(settings.get("fps", 5))
        raw_path = settings.get("path")
        base_path = Path(raw_path) if raw_path else Path.home()
        stem = settings.get("stem") or "output"
        self.filename = base_path / Path(stem)
        self.hours_per_file = int(settings.get("hours_per_file", 1))
        self.number_of_files = int(settings.get("number_of_files", 1))
        self.raw_image = convert_str_bool(settings.get("raw_image", True))
        self.timestamp = convert_str_bool(settings.get("timestamp", False))
        self.timestamp_color = settings.get(
            "timestamp_color", QColor.fromRgb(0, 255, 0)
        )
        self.timestamp_font_size = int(settings.get("timestamp_font_size", 12))
        self.width = int(settings.get("image_width", 480))
        self.use_epics_pv = convert_str_bool(settings.get("use_epics", True))
        self.epics_pv_name = str(settings.get("epics_pv", ""))
        self.setup_epics()

    def setup_epics(self):
        if self.epics_pv_name:
            self.epics_pv = PV(
                pvname=self.epics_pv_name, callback=self._start_epics_record
            )

    def write_settings(self) -> Dict[str, Any]:
        settings = {}
        settings["fps"] = self.fps
        settings["path"] = str(self.filename.parent)
        settings["stem"] = self.filename.stem
        settings["hours_per_file"] = self.hours_per_file
        settings["number_of_files"] = self.number_of_files
        settings["raw_image"] = self.raw_image
        settings["timestamp"] = self.timestamp
        settings["timestamp_color"] = self.timestamp_color
        settings["timestamp_font_size"] = self.timestamp_font_size
        settings["image_width"] = self.width
        settings["use_epics"] = self.use_epics_pv
        settings["epics_pv"] = self.epics_pv_name
        return settings

    def start_plugin(self):
        pass

    def stop_plugin(self):
        self.video_recorder_thread.stop()

    def add_settings(self, parent=None) -> Optional[QGroupBox]:
        parent = parent if parent else self.parent()
        groupBox = QGroupBox(self.name, parent)
        layout = QFormLayout()

        self.base_path_widget = QLineEdit(str(self.filename.parent), parent)
        layout.addRow("Destination path", self.base_path_widget)

        self.file_prefix_widget = QLineEdit(str(self.filename.stem), parent)
        layout.addRow("File prefix", self.file_prefix_widget)

        ## Start row
        self.fps_widget = QSpinBox()
        self.fps_widget.setRange(1, self.parent().fps)
        self.fps_widget.setValue(self.fps)

        self.image_width_widget = QSpinBox()
        self.image_width_widget.setRange(1, 4096)
        self.image_width_widget.setValue(self.width)

        hbox0 = QHBoxLayout()
        hbox0.addWidget(self.fps_widget)
        label0 = QLabel("Image width")
        hbox0.addWidget(label0)
        hbox0.addWidget(self.image_width_widget)
        layout.addRow("FPS", hbox0)
        ## End row

        ## Start row
        self.num_of_files_widget = QSpinBox()
        self.num_of_files_widget.setRange(1, 1000)
        self.num_of_files_widget.setValue(self.number_of_files)

        self.hours_per_file_widget = QSpinBox()
        self.hours_per_file_widget.setRange(1, 48)
        self.hours_per_file_widget.setValue(self.hours_per_file)

        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.hours_per_file_widget)
        label = QLabel("# of files")
        hbox1.addWidget(label)
        hbox1.addWidget(self.num_of_files_widget)
        layout.addRow("Hours per file", hbox1)
        ## End row

        ## Start row
        self.raw_image_widget = QCheckBox()
        self.raw_image_widget.setChecked(self.raw_image)
        label2 = QLabel("Add timestamp")
        self.timestamp_widget = QCheckBox()
        self.timestamp_widget.setChecked(self.timestamp)

        hbox2 = QHBoxLayout()
        hbox2.addWidget(self.raw_image_widget)
        hbox2.addWidget(label2)
        hbox2.addWidget(self.timestamp_widget)

        layout.addRow("Record without overlays", hbox2)
        ## End row

        ## Start row
        self.timestamp_color_widget = ColorButton(
            parent=parent, color=self.timestamp_color
        )
        self.timestamp_font_size_widget = QSpinBox()
        self.timestamp_font_size_widget.setRange(1, 100)
        self.timestamp_font_size_widget.setValue(int(self.timestamp_font_size))
        hbox3 = QHBoxLayout()
        hbox3.addWidget(self.timestamp_color_widget)
        hbox3.addWidget(QLabel("Timestamp font size"))
        hbox3.addWidget(self.timestamp_font_size_widget)
        layout.addRow("Timestamp color", hbox3)
        ## End row

        ## Start row
        self.use_epics_pv_checkbox = QCheckBox()
        self.use_epics_pv_checkbox.setChecked(self.use_epics_pv)
        epics_pv_name = QLabel("EPICS PV")
        self.epics_pv_textbox = QLineEdit(self.epics_pv_name, parent)
        hbox_epics = QHBoxLayout()
        hbox_epics.addWidget(self.use_epics_pv_checkbox)
        hbox_epics.addWidget(epics_pv_name)
        hbox_epics.addWidget(self.epics_pv_textbox)
        layout.addRow("Use EPICS PV", hbox_epics)
        ## End row

        groupBox.setLayout(layout)
        return groupBox

    def save_settings(self, settings_groupbox):
        if not self.file_prefix_widget.text():
            prefix = "output"
        else:
            prefix = self.file_prefix_widget.text()

        try:
            base_path = Path(self.base_path_widget.text())
        except:
            base_path = Path.home()

        self.filename = base_path / Path(prefix)
        self.width = self.image_width_widget.value()
        self.fps = self.fps_widget.value()
        self.number_of_files = self.num_of_files_widget.value()
        self.hours_per_file = self.hours_per_file_widget.value()
        self.raw_image = self.raw_image_widget.isChecked()
        self.timestamp = self.timestamp_widget.isChecked()
        self.timestamp_color = self.timestamp_color_widget.color()
        self.timestamp_font_size = self.timestamp_font_size_widget.value()
        self.use_epics_pv = self.use_epics_pv_checkbox.isChecked()
        self.epics_pv_name = self.epics_pv_textbox.text()
        self.setup_epics()
