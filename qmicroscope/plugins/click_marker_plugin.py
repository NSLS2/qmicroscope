from typing import Any, Dict, List, Optional

from qtpy.QtCore import QTimer, Qt
from qtpy.QtGui import QColor, QMouseEvent, QPen
from qtpy.QtWidgets import QFormLayout, QGraphicsEllipseItem, QGroupBox, QSpinBox, QApplication

from qmicroscope.plugins.base_plugin import BasePlugin
from qmicroscope.widgets.color_button import ColorButton


class BaseClickMarkerPlugin(BasePlugin):
    def __init__(
        self,
        parent=None,
        name: str = "Click Marker",
        default_color: "Optional[QColor]" = None,
        diameter: int = 20,
        suppress_on_double_click: bool = False,
    ) -> None:
        super().__init__(parent)
        self.name = name
        self._marker_color = default_color or QColor.fromRgb(0, 255, 0)
        self._diameter = int(diameter)
        self._visible = True
        self._marker_items: "List[QGraphicsEllipseItem]" = []
        self._marker_positions_px: "List[tuple[int, int]]" = []
        self._suppress_on_double_click = suppress_on_double_click
        self._pending_single_click = False
        self._pending_position: "Optional[tuple[int, int]]" = None

        self._single_click_timer = QTimer(self.parent)
        self._single_click_timer.setSingleShot(True)
        self._single_click_timer.timeout.connect(self._flush_single_click)

    @staticmethod
    def _convert_str_bool(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() == "true"
        return bool(value)

    def _parent_widget(self):
        if self.parent is None:
            raise RuntimeError(f"{self.name} parent is not set")
        return self.parent

    def _map_to_scene_px(self, event: QMouseEvent) -> tuple[int, int]:
        parent = self._parent_widget()
        scene_pos = parent.view.mapToScene(event.pos())
        x = int(round(scene_pos.x()))
        y = int(round(scene_pos.y()))
        if parent.image.width() > 0:
            x = max(0, min(parent.image.width() - 1, x))
        if parent.image.height() > 0:
            y = max(0, min(parent.image.height() - 1, y))
        return x, y

    def _add_marker_at(self, x: int, y: int) -> None:
        parent = self._parent_widget()
        radius = self._diameter / 2.0
        pen = QPen(self._marker_color)
        pen.setWidth(2)
        marker = parent.scene.addEllipse(
            x - radius,
            y - radius,
            self._diameter,
            self._diameter,
            pen=pen,
        )
        marker.setVisible(self._visible)
        self._marker_items.append(marker)
        self._marker_positions_px.append((int(x), int(y)))

    def get_marker_positions_px(self) -> List[tuple[int, int]]:
        return list(self._marker_positions_px)

    def clear_markers(self) -> None:
        parent = self._parent_widget()
        for marker in self._marker_items:
            if marker.scene() is not None:
                parent.scene.removeItem(marker)
        self._marker_items = []
        self._marker_positions_px = []
        self._pending_single_click = False
        self._pending_position = None
        self._single_click_timer.stop()

    def _set_markers_visible(self, visible: bool) -> None:
        self._visible = bool(visible)
        for marker in self._marker_items:
            marker.setVisible(self._visible)

    def _queue_single_click(self, event: QMouseEvent) -> None:
        parent = self._parent_widget()
        x, y = self._map_to_scene_px(event)
        self._pending_position = (x, y)
        self._pending_single_click = True
        app = QApplication.instance()
        if app is not None:
            interval = app.doubleClickInterval()
        self._single_click_timer.start(max(1, int(interval)))

    def _flush_single_click(self) -> None:
        if self._pending_single_click and self._pending_position is not None:
            x, y = self._pending_position
            self._add_marker_at(x, y)
        self._pending_single_click = False
        self._pending_position = None

    def _cancel_pending_single_click(self) -> None:
        self._single_click_timer.stop()
        self._pending_single_click = False
        self._pending_position = None

    def context_menu_entry(self):
        actions = []
        self.visible_action = self._action_cls()("Visible", self.parent)
        self.visible_action.setCheckable(True)
        self.visible_action.setChecked(self._visible)
        self.visible_action.triggered.connect(self._set_markers_visible)
        actions.append(self.visible_action)

        self.clear_action = self._action_cls()("Clear markers", self.parent)
        self.clear_action.triggered.connect(self.clear_markers)
        actions.append(self.clear_action)
        return actions

    def _action_cls(self):
        from qtpy import QtWidgets

        return QtWidgets.QAction

    def stop_plugin(self):
        self.clear_markers()

    def read_settings(self, settings: Dict[str, Any]):
        self._marker_color = settings.get("color", self._marker_color)
        self._diameter = int(settings.get("diameter", self._diameter))
        self._diameter = max(1, self._diameter)
        self._visible = self._convert_str_bool(settings.get("visible", self._visible))
        self._set_markers_visible(self._visible)

    def write_settings(self) -> Dict[str, Any]:
        return {
            "color": self._marker_color,
            "diameter": self._diameter,
            "visible": self._visible,
        }

    def add_settings(self, parent=None) -> Optional[QGroupBox]:
        parent = parent if parent else self.parent
        groupbox = QGroupBox(self.name, parent)
        layout = QFormLayout()

        self.color_setting_widget = ColorButton(parent=parent, color=self._marker_color)
        layout.addRow("Color", self.color_setting_widget)

        self.diameter_setting_widget = QSpinBox()
        self.diameter_setting_widget.setRange(1, 1000)
        self.diameter_setting_widget.setValue(int(self._diameter))
        layout.addRow("Diameter (px)", self.diameter_setting_widget)

        groupbox.setLayout(layout)
        return groupbox

    def save_settings(self, settings_groupbox) -> None:
        self._marker_color = self.color_setting_widget.color()
        self._diameter = int(self.diameter_setting_widget.value())
        self._diameter = max(1, self._diameter)
        for marker in self._marker_items:
            marker.setPen(QPen(self._marker_color, 2))


class SingleClickMarkerPlugin(BaseClickMarkerPlugin):
    def __init__(self, parent=None):
        super().__init__(
            parent=parent,
            name="Single Click Marker",
            default_color=QColor.fromRgb(0, 255, 0),
            diameter=20,
            suppress_on_double_click=True,
        )

    def mouse_press_event(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._queue_single_click(event)

    def mouse_double_click_event(self, event: QMouseEvent):
        if self._suppress_on_double_click and event.button() == Qt.MouseButton.LeftButton:
            self._cancel_pending_single_click()


class DoubleClickMarkerPlugin(BaseClickMarkerPlugin):
    def __init__(self, parent=None):
        super().__init__(
            parent=parent,
            name="Double Click Marker",
            default_color=QColor.fromRgb(255, 0, 0),
            diameter=20,
            suppress_on_double_click=False,
        )

    def mouse_double_click_event(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            x, y = self._map_to_scene_px(event)
            self._add_marker_at(x, y)
