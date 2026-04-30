from qtpy import QtWidgets
from qtpy.QtWidgets import QWidget
from qtpy.QtCore import QPoint, QPointF, QRect, Qt

from typing import Any, Dict, Optional

from qmicroscope.widgets.rubberband import ResizableRubberBand
from qmicroscope.plugins.base_plugin import BaseImagePlugin


class ZoomPlugin(BaseImagePlugin):
    def __init__(self, parent: "Optional[QWidget]" = None):
        super().__init__(parent)
        self.name = "Zoom"
        self.zoomRubberBand: "Optional[ResizableRubberBand]" = None
        self.startCrop = False
        self.parent = parent
        self.crop: "Optional[QRect]" = None
        self._temp_start_viewport: "Optional[QPoint]" = None

    def _parent_widget(self) -> QWidget:
        if self.parent is None:
            raise RuntimeError("ZoomPlugin parent is not set")
        return self.parent

    def _clamp_scene_point(self, point: QPoint) -> QPoint:
        parent = self._parent_widget()
        width = parent.image.width()
        height = parent.image.height()
        if width <= 0 or height <= 0:
            return point
        max_x = max(width - 1, 0)
        max_y = max(height - 1, 0)
        return QPoint(min(max(point.x(), 0), max_x), min(max(point.y(), 0), max_y))

    def _viewport_to_scene(self, point: QPoint) -> QPoint:
        parent = self._parent_widget()
        mapped = parent.view.mapToScene(point)
        return self._clamp_scene_point(mapped.toPoint())

    def _scene_to_viewport(self, point: QPoint) -> QPoint:
        parent = self._parent_widget()
        return parent.view.mapFromScene(QPointF(point))

    def _sync_rubberband_geometry(self):
        if not self.zoomRubberBand or self.crop is None:
            return
        scene_rect = QRect(self.crop)
        top_left = self._scene_to_viewport(scene_rect.topLeft())
        bottom_right = self._scene_to_viewport(scene_rect.bottomRight())
        viewport_rect = QRect(top_left, bottom_right).normalized()
        if viewport_rect != self.zoomRubberBand.geometry():
            previous_state = self.zoomRubberBand.blockSignals(True)
            self.zoomRubberBand.setGeometry(viewport_rect)
            self.zoomRubberBand.blockSignals(previous_state)

    def _crop_image(self) -> None:
        if self.zoomRubberBand:
            rubberband_rect = self.zoomRubberBand.geometry()
            rect_x = int(rubberband_rect.x())
            rect_y = int(rubberband_rect.y())
            rect_width = int(rubberband_rect.width())
            rect_ht = int(rubberband_rect.height())
            top_left = self._viewport_to_scene(QPoint(rect_x, rect_y))
            bottom_right = self._viewport_to_scene(
                QPoint(rect_x + rect_width, rect_y + rect_ht)
            )
            self.crop = QRect(top_left, bottom_right).normalized()
            self._temp_start_viewport = None
            self.zoomRubberBand.hide()
            self.zoomRubberBand = None

    def _start_crop(self):
        self.startCrop = True
        parent = self._parent_widget()
        parent.setCursor(Qt.CursorShape.CrossCursor)

    def context_menu_entry(self):
        parent = self._parent_widget()
        actions = []
        self.crop_action = QtWidgets.QAction("Zoom/Crop to selection", parent)
        self.crop_action.triggered.connect(self._start_crop)
        actions.append(self.crop_action)
        if self.crop is not None:
            self.reset_crop_action = QtWidgets.QAction("Reset Zoom/Crop", parent)
            self.reset_crop_action.triggered.connect(self._reset_crop)
            actions.append(self.reset_crop_action)
        return actions

    def mouse_press_event(self, event):
        if (
            not self.zoomRubberBand
            and self.startCrop
            and event.buttons() == Qt.MouseButton.LeftButton
        ):
            parent = self._parent_widget()
            self.zoomRubberBand = ResizableRubberBand(parent.view.viewport())
            self._temp_start_viewport = event.pos()
            self.zoomRubberBand.setGeometry(
                QRect(self._temp_start_viewport, self._temp_start_viewport)
            )

    def mouse_move_event(self, event):
        if self.startCrop and event.buttons() == Qt.MouseButton.LeftButton:
            if self._temp_start_viewport is None:
                self._temp_start_viewport = event.pos()
            if self.zoomRubberBand:
                self.zoomRubberBand.show()
                self.zoomRubberBand.setGeometry(
                    QRect(self._temp_start_viewport, event.pos()).normalized()
                )

    def mouse_release_event(self, event):
        if self.startCrop:
            self._crop_image()
            self.startCrop = False
            parent = self._parent_widget()
            parent.unsetCursor()

    def update_image_data(self, image):
        self.org_image_ht = image.height()
        self.org_image_wd = image.width()
        self._sync_rubberband_geometry()
        if self.crop is not None:
            image = image.copy(self.crop)
        return image

    def _reset_crop(self) -> None:
        self.crop = None

    def read_settings(self, settings: Dict[str, Any]):
        self.crop = settings.get("crop", None)

    def write_settings(self) -> Dict[str, Any]:
        return {"crop": self.crop}
