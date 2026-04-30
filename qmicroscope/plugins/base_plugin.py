from typing import Dict, Any, Optional, List
from qtpy.QtGui import QMouseEvent, QImage, QKeyEvent
from qtpy.QtWidgets import QGroupBox, QAction
from typing import Protocol, runtime_checkable


@runtime_checkable
class SupportsBasePlugin(Protocol):
    def context_menu_entry(self) -> List[QAction]:
        ...

    def update_image_data(self, image: QImage) -> QImage:
        ...

    def mouse_press_event(self, event: QMouseEvent):
        ...

    def mouse_move_event(self, event: QMouseEvent):
        ...

    def mouse_release_event(self, event: QMouseEvent):
        ...

    def mouse_double_click_event(self, event: QMouseEvent):
        ...
    
    def mouse_wheel_event(self, event: QMouseEvent):
        ...
    
    def key_press_event(self, event: QKeyEvent):
        ...

    def key_release_event(self, event: QKeyEvent):
        ...

    def read_settings(self, settings: Dict[str, Any]):
        ...

    def write_settings(self) -> Dict[str, Any]:
        ...

    def start_plugin(self):
        ...

    def stop_plugin(self):
        ...

    def add_settings(self, parent=None) -> Optional[QGroupBox]:
        ...

    def save_settings(self, settings_groupbox) -> None:
        ...


class BasePlugin:
    """
    A base class for microscope plugins.

    Args:
        parent: Parent widget of the plugin.

    Attributes:
        name (str): Name of the plugin.
        updates_image (bool): Whether the plugin updates the microscope image.
        parent: Parent widget of the plugin.
    """

    def __init__(self, parent=None) -> None:
        """
        Initializes the BasePlugin class.

        Args:
            parent: Parent widget of the plugin.
        """
        self.name = "Generic Plugin"
        self.updates_image = False
        self.parent = parent

    def context_menu_entry(self) -> List[QAction]:
        """
        Returns a list of actions to be added to the context menu.

        Returns:
            List of QActions
        """
        return []

    def update_image_data(self, image: QImage) -> QImage:
        """
        Manipulates or uses image data provided by the microscope widget. Will only be
        called if self.updates_image is set to True

        Args:
            image: QImage instance
        returns:
            QImage instance
        """
        return image

    def mouse_press_event(self, event: QMouseEvent):
        pass

    def mouse_move_event(self, event: QMouseEvent):
        pass

    def mouse_release_event(self, event: QMouseEvent):
        pass

    def mouse_double_click_event(self, event: QMouseEvent):
        pass
    
    def mouse_wheel_event(self, event: QMouseEvent):
        pass

    def key_press_event(self, event: QKeyEvent):
        pass

    def key_release_event(self, event: QKeyEvent):
        pass

    def read_settings(self, settings: Dict[str, Any]):
        """
        Reads settings from a dictionary and sets up the plugin.
        Note: It is up to the plugin author to convert dictionary values to its appropriate type
        In Linux systems everything is stored as a string (for e.g. boolean values are 'true' and 'false' strings)

        Argument:
            settings: Dictionary of setting values
        """
        pass

    def write_settings(self) -> Dict[str, Any]:
        """
        Returns a dictionary of settings to be saved to disk.

        Returns:
            Dictionary of settings
        """
        return {}

    def start_plugin(self):
        """
        Hook to set up the plugin after the microscope starts acquiring image data. For example,
        if we don't know the image size when the plugin is initialized, we can look for it here.
        Or draw something after the image is shown
        """
        pass

    def stop_plugin(self):
        """
        Hook to do something just before acquiring stops. For example, remove a drawing
        """
        pass

    def add_settings(self, parent=None) -> Optional[QGroupBox]:
        """
        Returns an optional QGroupBox that is displayed in the "Configure plugins" window

        returns:
            Optional QGroupBox
        """
        return None

    def save_settings(self, settings_groupbox) -> None:
        """
        This function is called when the user clicks on Ok or Apply in the "configure plugins" window
        """
        pass


class BaseImagePlugin(BasePlugin):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.name = "Base Image Plugin"
        self.updates_image = True
