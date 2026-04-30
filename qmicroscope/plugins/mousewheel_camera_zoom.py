from qtpy.QtGui import QMouseEvent

from typing import Any, Dict, Optional
import typing
from qmicroscope.plugins.base_plugin import BasePlugin

if typing.TYPE_CHECKING:
    from qmicroscope.microscope import Microscope


class MouseWheelCameraZoomPlugin(BasePlugin):
    def __init__(self, parent: "Optional[Microscope]" = None):
        """
        This plugin takes a number of camera feeds that represents
        different zoom levels and switches between them when a
        mousewheel is used    
        """
        super().__init__(parent)
        self.name = "Mousewheel camera zoom"
        self.parent = parent
        self.urls = []
        self.current_url_index = 0
    
    def context_menu_entry(self):
        actions = []
        return actions

    def read_settings(self, settings: Dict[str, Any]):
        self.urls = settings.get("urls", [])

    def write_settings(self) -> Dict[str, Any]:
        return {"urls": self.urls}

    def mouse_wheel_event(self, event: QMouseEvent):
        if not self.parent:
            return
        if len(self.urls) > 1:
            delta = event.angleDelta().y() if hasattr(event, "angleDelta") else 0
            if delta > 0:
                if self.current_url_index < len(self.urls) - 1:
                    self.current_url_index += 1
                    self.parent.videoThread.setUrl(self.urls[self.current_url_index])
            else:
                if self.current_url_index > 0:
                    self.current_url_index -= 1
                    self.parent.videoThread.setUrl(self.urls[self.current_url_index])
            
            
    
