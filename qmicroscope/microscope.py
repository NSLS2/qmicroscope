from collections.abc import Iterable
from typing import Any, Dict, List, Optional
import typing

from qtpy.QtCore import QByteArray, QEvent, QPoint, QSettings, QSize, Qt, Signal
from qtpy.QtGui import (
    QContextMenuEvent,
    QHideEvent,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPixmap,
    QCloseEvent,
    QShowEvent,
)
from qtpy.QtWidgets import (
    QAction,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from .plugin_settings import PluginSettingsDialog
from .plugins.base_plugin import BasePlugin, SupportsBasePlugin
from .widgets.downloader import VideoThread


class Microscope(QWidget):
    roiClicked: Signal = Signal(int, int)
    clicked_url: Signal = Signal(str)
    mouse_press_signal: Signal = Signal(object)
    mouse_double_click_signal: Signal = Signal(object)
    mouse_move_signal: Signal = Signal(object)
    mouse_release_signal: Signal = Signal(object)
    mouse_wheel_signal: Signal = Signal(object)
    key_press_signal: Signal = Signal(object)
    key_release_signal: Signal = Signal(object)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        viewport: bool = True,
        plugins: List[BasePlugin] = list(),
    ) -> None:
        super(Microscope, self).__init__(parent)
        self.plugin_classes = plugins
        self.viewport = viewport
        self.setMinimumWidth(300)
        self.setMinimumHeight(300)
        self.image = QImage("image.jpg")
        self.pixmap = QGraphicsPixmapItem(None)
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.scene.addItem(self.pixmap)
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.view)
        self.setLayout(self.layout)
        self.settings_group = None

        self.yDivs: int = 5
        self.xDivs: int = 5
        self.color: bool = False
        self.fps: int = 5
        self.scale: List[int] = []

        self.url: str = "http://localhost:8080/output.jpg"

        self.videoThread = VideoThread(fps=self.fps, url=self.url, parent=self)
        self.videoThread.imageReady.connect(self.updateImageData)

        self.plugins: Dict[str, BasePlugin] = {}
        for plugin_cls in self.plugin_classes:
            if isinstance(plugin_cls, SupportsBasePlugin):
                self.plugins[plugin_cls.__name__] = plugin_cls(self)
            else:
                print(
                    f"{plugin_cls.__name__} does not implement BasePlugin, ignoring Plugin"
                )

        for plugin in self.plugins.values():
            self.mouse_press_signal.connect(plugin.mouse_press_event)
            self.mouse_double_click_signal.connect(plugin.mouse_double_click_event)
            self.mouse_move_signal.connect(plugin.mouse_move_event)
            self.mouse_release_signal.connect(plugin.mouse_release_event)
            self.mouse_wheel_signal.connect(plugin.mouse_wheel_event)
            self.key_press_signal.connect(plugin.key_press_event)
            self.key_release_signal.connect(plugin.key_release_event)

        self.view.viewport().installEventFilter(self)
        self.view.installEventFilter(self)

    def closeEvent(self, a0: typing.Optional[QCloseEvent]) -> None:
        self.acquire(False)
        return super().closeEvent(a0)

    def hideEvent(self, a0: typing.Optional[QHideEvent]) -> None:
        if self.videoThread.isRunning():
            self.videoThread.stop()
            self.videoThread.wait()
        return super().hideEvent(a0)

    def updatedImageSize(self) -> None:
        if self.image.size() != self.minimumSize():
            self.setMinimumSize(self.image.size())
            self.center = QPoint(
                int(self.image.size().width() / 2), int(self.image.size().height() / 2)
            )

    def acquire(self, start: bool = True) -> None:
        if start:
            self.videoThread.setUrl(self.url)
            self.videoThread.setFPS(self.fps)
            self.videoThread.start()
            for plugin in self.plugins.values():
                plugin.start_plugin()
        elif self.videoThread.isRunning() and not start:
            for plugin in self.plugins.values():
                plugin.stop_plugin()
            self.videoThread.stop()
            self.videoThread.wait()

    def stop_plugins(self):
        "For cleaning up threads and other processes"
        for plugin in self.plugins.values():
            plugin.stop_plugin()

    def eventFilter(self, obj, event):
        if obj is self.view.viewport():
            if event.type() == QEvent.MouseButtonPress:
                self.mouse_press_event(event)
            if event.type() == QEvent.MouseButtonDblClick:
                self.mouse_double_click_event(event)
            if event.type() == QEvent.MouseButtonRelease:
                self.mouse_release_event(event)
            if event.type() == QEvent.MouseMove:
                self.mouse_move_event(event)
            if event.type() == QEvent.Wheel:
                self.mouse_wheel_event(event)
        if obj is self.view:
            if event.type() == QEvent.Type.Enter:
                self.view.setFocus()
            if event.type() == QEvent.Type.Leave:
                self.view.clearFocus()
            if event.type() == QEvent.KeyPress:
                self.key_press_event(event)
            if event.type() == QEvent.KeyRelease:
                self.key_release_event(event)

        return QWidget.eventFilter(self, obj, event)

    def key_press_event(self, event: QKeyEvent):
        self.key_press_signal.emit(event)

    def key_release_event(self, event: QKeyEvent):
        self.key_release_signal.emit(event)

    def mouse_wheel_event(self, event):
        self.mouse_wheel_signal.emit(event)

    def mouse_press_event(self, a0: QMouseEvent):
        if self.viewport:
            self.clicked_url.emit(self.settings_group)

        self.mouse_press_signal.emit(a0)

    def mouse_double_click_event(self, a0: QMouseEvent):
        self.mouse_double_click_signal.emit(a0)

    def mouse_move_event(self, a0: QMouseEvent):
        self.setFocus()
        self.mouse_move_signal.emit(a0)

    def mouse_release_event(self, a0: QMouseEvent) -> None:
        self.mouse_release_signal.emit(a0)

    def contextMenuEvent(self, a0: QContextMenuEvent) -> None:
        """Add entries into the context menu based on plugins used"""
        super().contextMenuEvent(a0)
        self.menu = QMenu(self)
        config_plugins_action = QAction("Configure Plugins", self)
        config_plugins_action.triggered.connect(self._config_plugins)
        self.addMenuItem(config_plugins_action)

        for plugin in self.plugins.values():
            self.menu.addSection(plugin.name)
            context_menu_entry = plugin.context_menu_entry()

            if isinstance(context_menu_entry, Iterable):
                for item in context_menu_entry:
                    self.addMenuItem(item)
            else:
                self.addMenuItem(context_menu_entry)

        self.menu.move(a0.globalPos())
        self.menu.show()

    def addMenuItem(self, item):
        if isinstance(item, QAction):
            self.menu.addAction(item)
        elif isinstance(item, QMenu):
            self.menu.addMenu(item)

    def _config_plugins(self):
        plugin_settings_dialog = PluginSettingsDialog(
            parent=self, plugins=self.plugins.values()
        )

    def sizeHint(self) -> QSize:
        return QSize(400, 400)

    def updateImageData(self, image: QImage):
        """Triggered when the new image is ready, update the view."""
        if isinstance(image, QByteArray):
            self.image.loadFromData(image, "JPG")
        else:
            self.image = image

        # Loop through plugins to process video image
        for plugin in self.plugins.values():
            if plugin.updates_image:
                self.image = plugin.update_image_data(self.image)

        if len(self.scale) == 2:
            if self.scale[0] > 0:
                self.image = self.image.scaledToWidth(self.scale[0])
            elif self.scale[1] > 0:
                self.image = self.image.scaledToHeight(self.scale[1])

        self.updatedImageSize()
        # self.view.setFixedSize(self.image.size())
        pixmap = QPixmap.fromImage(self.image)
        self.pixmap.setPixmap(pixmap)
        self.scene.setSceneRect(self.pixmap.boundingRect())
        rect = self.image.rect()
        ht = self.image.rect().height()
        wd = self.image.rect().width()
        rect.setHeight(ht + 2)
        rect.setWidth(wd + 2)
        self.view.setGeometry(rect)
        self.update()

    def resizeImage(self):
        if len(self.scale) == 2:
            if self.scale[0] > 0:
                self.image = self.image.scaledToWidth(self.scale[0])
            elif self.scale[1] > 0:
                self.image = self.image.scaledToHeight(self.scale[1])

    def readFromDict(self, settings: Dict[Any, Any]):
        """Read the settings from a Python dict."""
        if settings.has_key("url"):
            self.url = settings["url"]
        if settings.has_key("fps"):
            self.fps = settings["fps"]
        if settings.has_key("xDivs"):
            self.xDivs = settings["xDivs"]
        if settings.has_key("yDivs"):
            self.yDivs = settings["yDivs"]
        if settings.has_key("color"):
            self.color = settings["color"]
        if settings.has_key("scaleW"):
            self.scale = [settings["scaleW"], 200]
        if settings.has_key("scaleH"):
            if len(self.scale) == 2:
                self.scale[1] = 200  # settings['scaleW']
            else:
                self.scale = [200, settings["scaleW"]]

    def writeToDict(self):
        """Write the widget's settings to a Python dict."""
        settings = {
            "url": self.url,
            "fps": self.fps,
            "xDivs": self.xDivs,
            "yDivs": self.yDivs,
            "color": self.color,
        }
        if len(self.scale) == 2:
            settings["scaleW"] = self.scale[0]
            settings["scaleH"] = self.scale[1]
        return settings

    def readSettings(self, settings: QSettings):
        """Read the settings for this microscope instance."""
        self.settings_group = settings.group()  # Keep a copy
        self.settings = settings
        self.url = settings.value("url", "http://localhost:9998/jpg/image.jpg")
        self.fps = settings.value("fps", 5, type=int)
        self.xDivs = settings.value("xDivs", 5, type=int)
        self.yDivs = settings.value("yDivs", 5, type=int)
        self.color = settings.value("color", False, type=bool)

        for plugin in self.plugins.values():
            settings.beginGroup(plugin.name)
            settings_values = {}
            for key in settings.allKeys():
                settings_values[key] = settings.value(key)
            plugin.read_settings(settings_values)
            settings.endGroup()

        if settings.value("scaleW", -1, type=int) >= 0 and self.viewport:
            self.scale = [
                settings.value("scaleW", 200, type=int),
                settings.value("scaleH", 200, type=int),
            ]
            print(f"Reading {self.settings_group} {self.scale}")
            self.resizeImage()

    def writeSettings(
        self, settings: Optional[QSettings] = None, settings_group: Optional[str] = None
    ):
        """Write the settings for this microscope instance."""
        if not settings:
            settings = self.settings
        else:
            self.settings = settings

        if not settings_group:
            settings_group = self.settings_group
        else:
            self.settings_group = settings_group

        if settings_group:
            settings.beginGroup(settings_group)
            settings.setValue("url", self.url)
            settings.setValue("fps", self.fps)
            settings.setValue("xDivs", self.xDivs)
            settings.setValue("yDivs", self.yDivs)
            settings.setValue("color", self.color)
            if len(self.scale) == 2:
                print(f"Writing {settings_group} {self.scale}")
                settings.setValue("scaleW", self.scale[0])
                settings.setValue("scaleH", self.scale[1])

            for plugin in self.plugins.values():
                settings.beginGroup(plugin.name)
                settings_values = plugin.write_settings()
                for key, value in settings_values.items():
                    settings.setValue(key, value)
                settings.endGroup()
            settings.endGroup()
