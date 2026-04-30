from threading import Lock
from typing import Any, Dict, Optional, TYPE_CHECKING

import numpy as np
from qtpy.QtGui import QColor, QImage, QPainter
from qtpy.QtWidgets import QAction, QDoubleSpinBox, QFormLayout, QGroupBox, QSpinBox

from qmicroscope.plugins.base_plugin import BaseImagePlugin
from qmicroscope.utils import convert_str_bool
from qmicroscope.widgets.color_button import ColorButton

if TYPE_CHECKING:
    from qmicroscope.microscope import Microscope


class MaskOverlayPlugin(BaseImagePlugin):
    def __init__(self, parent: "Optional[Microscope]" = None):
        super().__init__(parent)
        self.name = "Mask Overlay"
        self._visible = True
        self._color = QColor.fromRgb(255, 0, 0)
        self._alpha = 120
        self._threshold = 0.5
        self._mask: "Optional[np.ndarray]" = None
        self._mask_lock = Lock()

    def set_mask(self, mask: Any):
        if mask is None:
            self.clear_mask()
            return
        union_mask = self._as_union_mask(mask)
        with self._mask_lock:
            self._mask = union_mask

    def set_masks(self, masks: Any):
        if masks is None:
            self.clear_mask()
            return
        union_mask = self._as_union_mask(masks)
        with self._mask_lock:
            self._mask = union_mask

    def clear_mask(self):
        with self._mask_lock:
            self._mask = None

    def context_menu_entry(self):
        actions = []
        visible_action = QAction(
            "Visible", self.parent, checkable=True, checked=self._visible
        )
        visible_action.triggered.connect(self._toggle_visibility)
        actions.append(visible_action)

        clear_action = QAction("Clear mask", self.parent)
        clear_action.triggered.connect(self.clear_mask)
        actions.append(clear_action)

        return actions

    def _toggle_visibility(self, value):
        self._visible = bool(value)

    def update_image_data(self, image: QImage) -> QImage:
        if not self._visible or image is None or image.isNull():
            return image

        with self._mask_lock:
            if self._mask is None:
                return image
            mask = self._mask.copy()

        frame_height = image.height()
        frame_width = image.width()
        if frame_height <= 0 or frame_width <= 0:
            return image

        if mask.shape != (frame_height, frame_width):
            mask = self._resize_mask_nearest(mask, frame_width, frame_height)

        if not np.any(mask):
            return image

        output_image = image.copy()
        overlay = self._build_overlay(mask)
        painter = QPainter(output_image)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.drawImage(0, 0, overlay)
        painter.end()
        return output_image

    def _build_overlay(self, mask: np.ndarray) -> QImage:
        height, width = mask.shape
        overlay = np.zeros((height, width, 4), dtype=np.uint8)
        overlay[mask, 0] = self._color.red()
        overlay[mask, 1] = self._color.green()
        overlay[mask, 2] = self._color.blue()
        overlay[mask, 3] = int(self._alpha)

        qimage = QImage(
            overlay.data,
            width,
            height,
            4 * width,
            self._qimage_format_rgba8888(),
        )
        return qimage.copy()

    @staticmethod
    def _qimage_format_rgba8888():
        if hasattr(QImage, "Format") and hasattr(QImage.Format, "Format_RGBA8888"):
            return QImage.Format.Format_RGBA8888
        return QImage.Format_RGBA8888

    def _as_union_mask(self, mask_data: Any) -> "Optional[np.ndarray]":
        array = self._to_numpy(mask_data)
        array = np.asarray(array)
        array = np.squeeze(array)

        if array.ndim == 0:
            return None
        if array.ndim == 1:
            return None
        if array.ndim == 2:
            return self._to_bool_mask(array)
        if array.ndim == 3:
            bool_masks = self._to_bool_mask(array)
            if bool_masks is None:
                return None
            return np.any(bool_masks, axis=0)

        return None

    def _to_bool_mask(self, mask: np.ndarray) -> "Optional[np.ndarray]":
        if mask.size == 0:
            return None

        if np.issubdtype(mask.dtype, np.bool_):
            return mask.astype(bool)

        if np.issubdtype(mask.dtype, np.floating):
            return mask >= float(self._threshold)

        max_value = float(mask.max())
        if max_value <= 0:
            return np.zeros(mask.shape, dtype=bool)

        threshold = float(self._threshold) * max_value
        return mask >= threshold

    @staticmethod
    def _to_numpy(data: Any):
        if isinstance(data, np.ndarray):
            return data
        if hasattr(data, "detach") and hasattr(data, "cpu"):
            return data.detach().cpu().numpy()
        if hasattr(data, "cpu") and hasattr(data, "numpy"):
            return data.cpu().numpy()
        if hasattr(data, "numpy"):
            return data.numpy()
        return np.asarray(data)

    @staticmethod
    def _resize_mask_nearest(mask: np.ndarray, width: int, height: int) -> np.ndarray:
        src_height, src_width = mask.shape
        y_indices = (np.arange(height) * src_height // height).clip(0, src_height - 1)
        x_indices = (np.arange(width) * src_width // width).clip(0, src_width - 1)
        return mask[np.ix_(y_indices, x_indices)]

    def read_settings(self, settings: Dict[str, Any]):
        self._color = settings.get("color", self._color)
        self._alpha = int(settings.get("alpha", self._alpha))
        self._alpha = max(0, min(255, self._alpha))

        threshold = settings.get("threshold", self._threshold)
        self._threshold = float(threshold)
        self._threshold = max(0.0, min(1.0, self._threshold))

        self._visible = convert_str_bool(settings.get("visible", self._visible))

    def write_settings(self) -> Dict[str, Any]:
        settings = {}
        settings["color"] = self._color
        settings["alpha"] = self._alpha
        settings["threshold"] = self._threshold
        settings["visible"] = self._visible
        return settings

    def add_settings(self, parent=None) -> Optional[QGroupBox]:
        parent = parent if parent else self.parent
        groupbox = QGroupBox(self.name, parent)
        layout = QFormLayout()

        self.color_setting_widget = ColorButton(parent=parent, color=self._color)
        layout.addRow("Color", self.color_setting_widget)

        self.alpha_setting_widget = QSpinBox()
        self.alpha_setting_widget.setRange(0, 255)
        self.alpha_setting_widget.setValue(int(self._alpha))
        layout.addRow("Alpha", self.alpha_setting_widget)

        self.threshold_setting_widget = QDoubleSpinBox()
        self.threshold_setting_widget.setRange(0.0, 1.0)
        self.threshold_setting_widget.setSingleStep(0.05)
        self.threshold_setting_widget.setDecimals(3)
        self.threshold_setting_widget.setValue(float(self._threshold))
        layout.addRow("Threshold", self.threshold_setting_widget)

        groupbox.setLayout(layout)
        return groupbox

    def save_settings(self, settings_groupbox) -> None:
        self._color = self.color_setting_widget.color()
        self._alpha = int(self.alpha_setting_widget.value())
        self._threshold = float(self.threshold_setting_widget.value())
