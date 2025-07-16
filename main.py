import sys
import argparse
from pathlib import Path
import yaml
from qtpy.QtCore import (
    QPoint,
    QSettings,
    QSize,
)

from qtpy.QtWidgets import (
    QCheckBox,
    QLineEdit,
    QPushButton,
    QApplication,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QSpinBox,
    QMainWindow,
    QWidget,
)

from qmicroscope.microscope import Microscope
from qmicroscope.container import Container
from qmicroscope.settings import Settings
from qmicroscope.plugins.record_plugin import RecordPlugin
from qmicroscope.plugins.c2c_plugin import C2CPlugin

class Form(QMainWindow):
    def __init__(self, parent=None):
        super(Form, self).__init__(parent)
        # Create widgets
        self.setWindowTitle("NSLS-II Microscope Widget")
        self.container = Container(self, plugins=[RecordPlugin, C2CPlugin])
        self.container.count = 3
        self.container.size = [2, 2]
        self.microscope = self.container.microscope(0)
        # self.microscope = Microscope(self)

        self.startButton = QPushButton("Start")
        self.settingsButton = QPushButton("Settings")

        # Create layout and add widgets
        layout = QVBoxLayout()
        hButtonBox = QHBoxLayout()
        hButtonBox.addStretch()
        hButtonBox.addWidget(self.startButton)
        hButtonBox.addWidget(self.settingsButton)
        hButtonBox.addStretch()
        layout.addLayout(hButtonBox)
        layout.addWidget(self.container)

        # Set main windows widget using our central layout
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        # Add button signal to slot to start/stop
        self.startButton.clicked.connect(self.startButtonPressed)
        self.settingsButton.clicked.connect(self.settingsButtonClicked)

        # Connect to the microscope ROI clicked signal
        if self.microscope:
            self.microscope.roiClicked.connect(self.onRoiClicked)

        # Read the settings and persist them
        settings = QSettings("NSLS2", "main")
        root = {}
        for full_key in settings.allKeys():
            parts = full_key.split('/')
            cursor = root
            for part in parts[:-1]:
                cursor = cursor.setdefault(part, {})
            cursor[parts[-1]] = settings.value(full_key)

        # ---- 2) YAML-encode and print ----
        yaml.safe_dump(root, stream=sys.stdout, sort_keys=False, default_flow_style=False)
        self.readSettings(settings)

        self.settingsDialog = Settings(self)
        self.settingsDialog.setContainer(self.container)

    # event : QCloseEvent
    def closeEvent(self, event):
        settings = QSettings("NSLS2", "main")
        self.writeSettings(settings)
        self.container.start(False)
        event.accept()

    def startButtonPressed(self):
        # Currently being a little lame - only update state on start/stop.
        print("Button pressed!", self.startButton.text())
        if self.startButton.text() == "Start":
            self.container.start(True)
            self.startButton.setText("Stop")
        else:
            self.container.start(False)
            self.startButton.setText("Start")

    def settingsButtonClicked(self):
        # Open the settings dialog.
        self.settingsDialog.show()

    def onRoiClicked(self, x, y):
        print(f"ROI: {x}, {y}")

    def readSettings(self, settings):
        """Load the application's settings."""
        settings.beginGroup("MainWindow")
        self.resize(settings.value("size", QSize(400, 400)))
        self.move(settings.value("pos", QPoint(200, 200)))
        self.container.readSettings(settings)
        settings.endGroup()

    def writeSettings(self, settings):
        """Save the applications's settings persistently."""
        settings.beginGroup("MainWindow")
        settings.setValue("size", self.size())
        settings.setValue("pos", self.pos())
        self.container.writeSettings(settings)
        settings.endGroup()

def overlay_yaml(settings_obj, yaml_file):
    with open(yaml_file, encoding='utf-8') as f:
        def walk(prefix, node):
            if isinstance(node, dict):
                for k, v in node.items():
                    walk(f"{prefix}/{k}" if prefix else k, v)
            else:
                settings_obj.setValue(prefix, node)
        walk("", yaml.safe_load(f) or {})

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--settings", help="YAML file to override settings")
    p.add_argument("--persist", action="store_true", help="Overrides profile settings")
    args = p.parse_args()

    # Set up some application basics for saving settings
    QApplication.setOrganizationName("BNL")
    QApplication.setOrganizationDomain("bnl.gov")
    QApplication.setApplicationName("QCamera")

    settings = QSettings()

    if args.settings:
        overlay_yaml(settings, Path(args.settings).expanduser())
        if args.persist:
            settings.sync()
    # Create the Qt Application
    app = QApplication(sys.argv)

    # Create and show the form
    form = Form()
    form.show()

    # Run the main Qt loop
    sys.exit(app.exec_())
