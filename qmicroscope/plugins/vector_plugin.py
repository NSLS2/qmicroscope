from typing import Optional, Dict, Any, TYPE_CHECKING, List
from qtpy.QtWidgets import (
    QAction,
    QColorDialog,
    QGraphicsScene,
    QGroupBox,
    QFormLayout,
    QSpinBox,
    QGraphicsItem,
    QGraphicsEllipseItem,
    QGraphicsSceneMouseEvent,
)
from qtpy.QtCore import QPoint, Qt, QRect, QRectF, Signal, QObject, QLineF
from qtpy.QtGui import QColor, QPen, QCursor, QGuiApplication
from qmicroscope.widgets.color_button import ColorButton
from qmicroscope.plugins.base_plugin import BasePlugin
from qtpy.QtGui import QMouseEvent
from collections import defaultdict

if TYPE_CHECKING:
    from qmicroscope.microscope import Microscope


class VectorNodeSignal(QObject):
    moved = Signal(object)


class VectorNode(QGraphicsEllipseItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setAcceptHoverEvents(True)

    def itemChange(self, change: "QGraphicsItem.GraphicsItemChange", value: Any) -> Any:
        if change == QGraphicsItem.ItemPositionChange:
            self.vector_node_signal.moved.emit("moved")
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event):
        cursor = QCursor(Qt.OpenHandCursor)
        self.setCursor(cursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setCursor(QCursor(Qt.ArrowCursor))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: "QGraphicsSceneMouseEvent") -> None:
        cursor = QCursor(Qt.ClosedHandCursor)
        self.setCursor(cursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: "QGraphicsSceneMouseEvent") -> None:
        self.setCursor(QCursor(Qt.ArrowCursor))
        super().mouseReleaseEvent(event)


class VectorPlugin(BasePlugin):
    def __init__(self, parent: "Optional[Microscope]" = None):
        super().__init__(parent)
        self.parent: Microscope
        self.name = "Vector"
        self.start_node = None
        self.end_node = None
        self.vector_line = None
        self.node_radius = 5
        self._add_start = False
        self._add_end = False
        self.vector_node_signal = VectorNodeSignal()
        self.vector_node_signal.moved.connect(self._update_vector)

    def context_menu_entry(self) -> List[QAction]:
        actions = []
        if not self.start_node:
            self.add_start_node_action = QAction("Add start node", self.parent)
            self.add_start_node_action.triggered.connect(self._add_start_node)
            actions.append(self.add_start_node_action)
        if not self.end_node:
            self.add_end_node_action = QAction("Add end node", self.parent)
            self.add_end_node_action.triggered.connect(self._add_end_node)
            actions.append(self.add_end_node_action)
        return actions

    def _add_start_node(self):
        self._add_start = True
        self.parent.view.setCursor(Qt.CrossCursor)

    def _add_end_node(self):
        self._add_end = True
        self.parent.view.setCursor(Qt.CrossCursor)

    def mouse_press_event(self, event: QMouseEvent):
        if self._add_start:
            self._place_node("start_node", event.pos(), QColor("blue"))
            self._add_start = False
        elif self._add_end:
            self._place_node("end_node", event.pos(), QColor("red"))
            self._add_end = False
        self._update_vector()

    def _place_node(self, node_name, pos: QPoint, color):
        pos.setX(pos.x() - self.node_radius)
        pos.setY(pos.y() - self.node_radius)
        rect = QRectF(0, 0, 2 * self.node_radius, 2 * self.node_radius)
        node = VectorNode(rect)
        node.vector_node_signal = self.vector_node_signal
        node.setPen(color)
        node.setBrush(color)
        self.parent.scene.addItem(node)
        node.setPos(pos)
        node.setZValue(2)
        self.parent.view.setCursor(Qt.ArrowCursor)
        setattr(self, node_name, node)

    def _update_vector(self):
        if self.end_node and self.start_node:
            if self.vector_line:
                self.parent.scene.removeItem(self.vector_line)
            offset = QPoint(self.node_radius, self.node_radius)
            line = QLineF(self.start_node.pos() + offset, self.end_node.pos() + offset)
            self.vector_line = self.parent.scene.addLine(
                line, QPen(QColor("red"), self.node_radius / 2)
            )
