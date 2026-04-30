import re
from typing import Optional, Dict, Any, TYPE_CHECKING, NamedTuple
from qtpy import QtWidgets
from qtpy.QtWidgets import (
    QColorDialog,
    QGraphicsScene,
    QGroupBox,
    QFormLayout,
    QHBoxLayout,
    QSpinBox,
    QLabel,
)
from qtpy.QtCore import QPoint, QPointF, Qt, QRect, QRectF
from qtpy.QtGui import QColor, QPen
from qmicroscope.widgets.rubberband import ResizableRubberBand
from qmicroscope.widgets.color_button import ColorButton
from qmicroscope.plugins.base_plugin import BaseImagePlugin
from qmicroscope.utils import convert_str_bool
from qtpy.QtGui import QMouseEvent
from collections import defaultdict

if TYPE_CHECKING:
    from qmicroscope.microscope import Microscope


class GridPositions(NamedTuple):
    top_left: tuple[int, int]
    bottom_right: tuple[int, int]


class GridPlugin(BaseImagePlugin):
    """A plugin for displaying a grid on an image in a microscope application.

    The grid can be defined by drawing a rectangle on the image,
    and the color and number of divisions in the grid can be customized.
    The plugin also provides options for showing and hiding the grid and the rectangle used to define it.

    """

    def __init__(self, parent: "Optional[Microscope]" = None):
        """Initializes the GridPlugin instance.

        Args:
            parent (Optional[Microscope]): The microscope application that the plugin is attached to.
        """
        super().__init__(parent)
        self.name = "Grid"
        self.rubberBand: "Optional[ResizableRubberBand]" = None
        self.parent = parent
        self.grid_positions = GridPositions((0, 0), (1, 1))
        self.start_grid = False
        self._draw_start_viewport: "Optional[QPoint]" = None
        self._grid_color = QColor.fromRgb(0, 255, 0)
        self._grid_items = []
        self._grid = None
        self.plugin_state = defaultdict(bool)
        self._x_divs = 5
        self._y_divs = 5

    @staticmethod
    def _coerce_qpoint(value: Any, default: QPoint) -> QPoint:
        if isinstance(value, QPoint):
            return QPoint(value)
        if hasattr(value, "x") and hasattr(value, "y"):
            return QPoint(int(value.x()), int(value.y()))
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return QPoint(int(value[0]), int(value[1]))
        if isinstance(value, str):
            values = re.findall(r"-?\d+", value)
            if len(values) >= 2:
                return QPoint(int(values[0]), int(values[1]))
        return QPoint(default)

    def _clamp_scene_point(self, point: QPoint) -> QPoint:
        if not self.parent:
            return point
        width = self.parent.image.width()
        height = self.parent.image.height()
        if width <= 0 or height <= 0:
            return point
        max_x = max(width - 1, 0)
        max_y = max(height - 1, 0)
        return QPoint(min(max(point.x(), 0), max_x), min(max(point.y(), 0), max_y))

    def _set_grid_positions(self, first: QPoint, second: QPoint):
        p1 = self._clamp_scene_point(first)
        p2 = self._clamp_scene_point(second)
        rect = QRect(p1, p2).normalized()
        top_left = rect.topLeft()
        bottom_right = rect.bottomRight()
        self.grid_positions = GridPositions(
            (int(top_left.x()), int(top_left.y())),
            (int(bottom_right.x()), int(bottom_right.y())),
        )

    def _position_points(self) -> "tuple[QPoint, QPoint]":
        top_left = QPoint(*self.grid_positions.top_left)
        bottom_right = QPoint(*self.grid_positions.bottom_right)
        return top_left, bottom_right

    def _viewport_to_scene(self, point: QPoint) -> QPoint:
        if not self.parent:
            return point
        mapped = self.parent.view.mapToScene(point)
        return self._clamp_scene_point(mapped.toPoint())

    def _scene_to_viewport(self, point: QPoint) -> QPoint:
        if not self.parent:
            return point
        return self.parent.view.mapFromScene(QPointF(point))

    def _parent_widget(self) -> "Microscope":
        if self.parent is None:
            raise RuntimeError("GridPlugin parent is not set")
        return self.parent

    def _viewport_rect_from_positions(self) -> QRect:
        top_left_scene, bottom_right_scene = self._position_points()
        top_left = self._scene_to_viewport(top_left_scene)
        bottom_right = self._scene_to_viewport(bottom_right_scene)
        return QRect(top_left, bottom_right).normalized()

    def _sync_rubberband_geometry(self):
        if not self.rubberBand:
            return
        rect = self._viewport_rect_from_positions()
        if rect != self.rubberBand.geometry():
            previous_state = self.rubberBand.blockSignals(True)
            self.rubberBand.setGeometry(rect)
            self.rubberBand.blockSignals(previous_state)

    def get_grid_positions(self) -> GridPositions:
        return self.grid_positions

    def get_top_left_px(self) -> tuple[int, int]:
        return self.grid_positions.top_left

    def get_bottom_right_px(self) -> tuple[int, int]:
        return self.grid_positions.bottom_right

    def read_settings(self, settings: Dict[str, Any]):
        """Reads the plugin's settings from a dictionary.

        Args:
            settings (Dict[str, Any]): A dictionary containing the settings.
        """
        self._grid_color = settings.get("color", QColor.fromRgb(0, 255, 0))
        top_left = settings.get("top_left")
        bottom_right = settings.get("bottom_right")
        if top_left is not None and bottom_right is not None:
            start = self._coerce_qpoint(top_left, QPoint(0, 0))
            end = self._coerce_qpoint(bottom_right, QPoint(1, 1))
        else:
            start = self._coerce_qpoint(settings.get("start", QPoint(0, 0)), QPoint(0, 0))
            end = self._coerce_qpoint(settings.get("end", QPoint(1, 1)), QPoint(1, 1))
        self._set_grid_positions(start, end)
        self.plugin_state["grid_hidden"] = convert_str_bool(
            settings.get("grid_hidden", False)
        )
        self.plugin_state["selector_hidden"] = convert_str_bool(
            settings.get("selector_hidden", False)
        )
        self.plugin_state["grid_defined"] = convert_str_bool(
            settings.get("grid_defined", False)
        )
        self._x_divs = int(settings.get("x_divs", 5))
        self._y_divs = int(settings.get("y_divs", 5))

    def start_plugin(self):
        """Starts the plugin."""
        if self.plugin_state["grid_defined"]:
            parent = self._parent_widget()
            self.paintBoxes(parent.scene)
            if self._grid:
                self._grid.setVisible(not self.plugin_state["grid_hidden"])
            self.create_rubberband()
            self._sync_rubberband_geometry()
            if self.rubberBand:
                self.rubberBand.setVisible(not self.plugin_state["selector_hidden"])

    def stop_plugin(self):
        """Stops the plugin."""
        parent = self._parent_widget()
        self.remove_grid(parent.scene)
        if self.rubberBand:
            self.rubberBand.deleteLater()
            self.rubberBand = None

    def write_settings(self) -> Dict[str, Any]:
        """Writes the plugin's settings to a dictionary.

        Returns:
            Dict[str, Any]: A dictionary containing the settings.
        """
        settings_values = {}
        settings_values["color"] = self._grid_color
        top_left, bottom_right = self._position_points()
        settings_values["top_left"] = self.grid_positions.top_left
        settings_values["bottom_right"] = self.grid_positions.bottom_right
        settings_values["start"] = top_left
        settings_values["end"] = bottom_right
        settings_values["grid_hidden"] = self.plugin_state["grid_hidden"]
        settings_values["selector_hidden"] = self.plugin_state["selector_hidden"]
        settings_values["grid_defined"] = self.plugin_state["grid_defined"]
        settings_values["x_divs"] = self._x_divs
        settings_values["y_divs"] = self._y_divs
        return settings_values

    def update_image_data(self, image):
        if self.plugin_state["grid_defined"] and self.rubberBand:
            self._sync_rubberband_geometry()
        return image

    def context_menu_entry(self):
        """Returns a list of QAction objects representing the plugin's context menu options.

        Returns:
            List[QAction]: The list of QAction objects.
        """
        actions = []
        if self.plugin_state["grid_defined"]:
            # if not self.rubberBand:
            #    self.create_rubberband()
            #    self.rubberBand.setVisible(self.plugin_state['selector_hidden'])
            self.hide_show_action = QtWidgets.QAction(
                "Selector Visible",
                self.parent,
                checkable=True,
                checked=self.rubberBand.isVisible() if self.rubberBand else False,
            )
            self.hide_show_action.triggered.connect(self._toggle_selector)
            actions.append(self.hide_show_action)
            # if self._grid:
            self.hide_show_grid_action = QtWidgets.QAction(
                "Grid Visible",
                self.parent,
                checkable=True,
                checked=self._grid.isVisible() if self._grid else False,
            )
            # self.select_grid_color_action = QAction('Change Grid color', self.parent)
            self.hide_show_grid_action.triggered.connect(self._toggle_grid)
            # self.select_grid_color_action.triggered.connect(self._select_grid_color)
            actions.extend(
                [self.hide_show_grid_action]
            )  # , self.select_grid_color_action])

        self.start_drawing_grid_action = QtWidgets.QAction("Draw grid", self.parent)
        self.start_drawing_grid_action.triggered.connect(self._start_grid)
        actions.append(self.start_drawing_grid_action)

        return actions

    def _select_grid_color(self) -> None:
        """Shows a color picker dialog and sets the grid color to the selected color."""
        self._grid_color = QColorDialog.getColor()
        if self._grid:
            parent = self._parent_widget()
            self.paintBoxes(parent.scene)

    def _toggle_selector(self):
        """Toggles the visibility of the rectangle used to define the grid."""
        if self.rubberBand:
            self.rubberBand.toggle_selector()
            self.plugin_state["selector_hidden"] = not self.rubberBand.isVisible()

    def _toggle_grid(self) -> None:
        """Toggles the visibility of the grid."""
        if self._grid:
            if self._grid.isVisible():
                self._grid.hide()
                self.plugin_state["grid_hidden"] = True
            else:
                self._grid.show()
                self.plugin_state["grid_hidden"] = False

    def _start_grid(self):
        """Sets the start_grid flag to True."""
        self.start_grid = True

    def update_grid(self, start: QPoint, end: QPoint) -> None:
        """Updates the grid based on the new start and end points of the rectangle used to define it.

        Args:
            start (QPoint): The new starting point.
            end (QPoint): The new ending point.
        """
        parent = self._parent_widget()
        self._set_grid_positions(self._viewport_to_scene(start), self._viewport_to_scene(end))
        self.paintBoxes(parent.scene)

    def mouse_move_event(self, event: QMouseEvent):
        """Handle mouse move events. If the grid is being defined and a rubberband object exists and the
        left mouse button is pressed, updates the rubberband object's position and the end position
        of the grid.

        Parameters:
            event (QMouseEvent): The mouse move event.

        Returns:
            None.
        """
        if self.start_grid:
            if self.rubberBand and event.buttons() == Qt.MouseButton.LeftButton:
                if self.rubberBand.isVisible():
                    if self._draw_start_viewport is None:
                        self._draw_start_viewport = event.pos()
                    self.rubberBand.setGeometry(
                        QRect(self._draw_start_viewport, event.pos()).normalized()
                    )

    def mouse_press_event(self, event: QMouseEvent):
        """
        Handle mouse press events. If the grid is being defined and the left mouse button is pressed,
        sets the start position of the grid. If a rubberband object does not exist and the viewport does
        not exist, creates a new rubberband object.

        Parameters:
            event (QMouseEvent): The mouse press event.

        Returns:
            None.
        """
        if self.start_grid:
            if event.buttons() == Qt.MouseButton.LeftButton:
                self._draw_start_viewport = event.pos()

            parent = self._parent_widget()
            if not self.rubberBand and not parent.viewport:
                self.create_rubberband()
            if self.rubberBand and self._draw_start_viewport is not None:
                self.rubberBand.setGeometry(
                    QRect(self._draw_start_viewport, self._draw_start_viewport)
                )

    def mouse_release_event(self, event: QMouseEvent):
        if self.start_grid:
            if self.rubberBand:
                rect = self.rubberBand.geometry()
                self.update_grid(rect.topLeft(), rect.bottomRight())
            self.plugin_state["grid_defined"] = True
            self.start_grid = False
            self._draw_start_viewport = None

    def remove_grid(self, scene: QGraphicsScene):
        """
        Remove the current grid from the specified QGraphicsScene if it exists.

        Parameters:
            scene (QGraphicsScene): The QGraphicsScene from which to remove the grid.

        Returns:
            None.
        """
        if self._grid:
            if self._grid.scene() == scene:
                scene.removeItem(self._grid)
                self._grid = None
                self._grid_items = []

    def create_rubberband(self):
        """
        Create a new rubberband object and display it on the parent widget.

        Returns:
            None.
        """
        parent = self._parent_widget()
        self.rubberBand = ResizableRubberBand(parent.view.viewport())
        self.rubberBand.box_modified.connect(self.update_grid)
        self._sync_rubberband_geometry()
        self.rubberBand.show()

    def paintBoxes(self, scene: QGraphicsScene) -> None:
        """
        Paint the boxes of the grid onto the specified QGraphicsScene. Removes the old grid if it
        exists, creates a new grid using the current rubberband object's position and settings,
        and adds the new grid to the specified QGraphicsScene.

        Parameters:
            scene (QGraphicsScene): The QGraphicsScene onto which to paint the grid.

        Returns:
            None.
        """
        self.remove_grid(scene)
        start, end = self._position_points()
        rect = QRectF(start, end)
        if self._grid_color:
            brushColor = self._grid_color
        else:
            brushColor = QColor.fromRgb(0, 255, 0)
        pen = QPen(brushColor)
        self._grid_items.append(scene.addRect(rect, pen=pen))
        # Now draw the lines for the boxes in the rectangle.
        x1 = start.x()
        y1 = start.y()
        x2 = end.x()
        y2 = end.y()
        inc_x = (x2 - x1) / self._x_divs
        inc_y = (y2 - y1) / self._y_divs

        for i in range(1, self._x_divs):
            l = scene.addLine(int(x1 + i * inc_x), y1, int(x1 + i * inc_x), y2, pen=pen)
            self._grid_items.append(l)
        for i in range(1, self._y_divs):
            l = scene.addLine(x1, int(y1 + i * inc_y), x2, int(y1 + i * inc_y), pen=pen)
            self._grid_items.append(l)

        self._grid = scene.createItemGroup(self._grid_items)

    def add_settings(self, parent=None) -> Optional[QGroupBox]:
        """
        Create a new QGroupBox containing settings widgets for the grid plugin.

        Parameters:
            parent (QWidget): The parent widget for the QGroupBox. If None, the parent widget is set
                to the parent widget of the plugin.

        Returns:
            Optional[QGroupBox]: The new QGroupBox object.
        """
        parent = parent if parent else self.parent
        groupBox = QGroupBox(self.name, parent)
        layout = QFormLayout()
        self.color_setting_widget = ColorButton(parent=parent, color=self._grid_color)
        layout.addRow("Color", self.color_setting_widget)

        hbox = QHBoxLayout()
        self.x_divs_widget = QSpinBox()
        self.x_divs_widget.setRange(1, 10000)
        self.x_divs_widget.setValue(self._x_divs)

        self.y_divs_widget = QSpinBox()
        self.y_divs_widget.setRange(1, 10000)
        self.y_divs_widget.setValue(self._y_divs)

        hbox.addWidget(self.x_divs_widget)
        label = QLabel("Y Divisions")
        hbox.addWidget(label)
        hbox.addWidget(self.y_divs_widget)

        layout.addRow("X Divisions", hbox)
        groupBox.setLayout(layout)
        return groupBox

    def save_settings(self, settings_groupbox) -> None:
        """
        Save the settings values from the specified QGroupBox to the corresponding class variables,
        and update the grid using the new settings.

        Parameters:
            settings_groupbox (QGroupBox): The QGroupBox containing the settings widgets.

        Returns:
            None.
        """
        self._grid_color = self.color_setting_widget.color()
        self._x_divs = self.x_divs_widget.value()
        self._y_divs = self.y_divs_widget.value()

        parent = self._parent_widget()
        self.paintBoxes(parent.scene)
        self._sync_rubberband_geometry()
