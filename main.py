import sys
import argparse
from pathlib import Path, PosixPath
import yaml
from qtpy.QtCore import (
    QPoint,
    QSettings,
    QSize,
)
from qtpy.QtGui import QColor
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
    QFileDialog,
    QMessageBox,
)

from qmicroscope.microscope import Microscope
from qmicroscope.container import Container
from qmicroscope.settings import Settings
from qmicroscope.plugins.record_plugin import RecordPlugin
from qmicroscope.plugins.c2c_plugin import C2CPlugin

class Form(QMainWindow):
    def __init__(self, settings=None, parent=None):
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
        self.saveSettingsButton = QPushButton("Save Settings")

        # Create layout and add widgets
        layout = QVBoxLayout()
        hButtonBox = QHBoxLayout()
        hButtonBox.addStretch()
        hButtonBox.addWidget(self.startButton)
        hButtonBox.addWidget(self.settingsButton)
        hButtonBox.addWidget(self.saveSettingsButton)
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
        self.saveSettingsButton.clicked.connect(self.saveSettingsButtonClicked)

        # Connect to the microscope ROI clicked signal
        if self.microscope:
            self.microscope.roiClicked.connect(self.onRoiClicked)

        # Read the settings and persist them
        if settings is None:
            settings = QSettings("NSLS2", "main")

        root = self.parse_settings(settings)
        yaml.safe_dump(root, stream=sys.stdout, sort_keys=False, default_flow_style=False)
        self.readSettings(settings)

        self.settingsDialog = Settings(self)
        self.settingsDialog.setContainer(self.container)

    def parse_settings(self, settings) -> dict:
        root = {}
        for full_key in settings.allKeys():
            parts = full_key.split('/')
            cursor = root
            for part in parts[:-1]:
                cursor = cursor.setdefault(part, {})
            cursor[parts[-1]] = settings.value(full_key)
        return root

    # event : QCloseEvent
    def closeEvent(self, event):
        settings = QSettings("NSLS2", "main")
        # self.writeSettings(settings)
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

    def saveSettingsButtonClicked(self):
        dialog = QFileDialog(self)
        filename, _ = dialog.getSaveFileName(
                        self,
                        "Export settings as YAML",
                        str(Path.home() / "settings.yaml"),
                        "YAML files (*.yaml *.yml);;All files (*)"
        )
        if filename:
            try:
                data = self.parse_settings(QSettings("NSLS2", "main"))
                yaml_str = yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
                Path(filename).write_text(yaml_str, encoding='utf-8')
                QMessageBox.information(self, "Export complete",
                                         f"Settings written to:\n{filename}")
            except Exception as e:
                QMessageBox.critical(self, "Export failed", str(e))
    
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


def setup_yaml_parser():
    # ── 1. Dumper → Python → YAML ──────────────────────────────────────────────────
    def qpoint_representer(dumper, data: QPoint):
        # Emit a YAML *sequence* tagged as !QPoint, e.g.   !QPoint [10, 20]
        return dumper.represent_sequence('!QPoint', [data.x(), data.y()])

    def qsize_representer(dumper, data: QSize):
        # Emit !QSize [width, height]
        return dumper.represent_sequence('!QSize', [data.width(), data.height()])

    def path_representer(dumper, data: Path):
        return dumper.represent_scalar('!Path', str(data))

    def qcolor_representer(dumper, data: QColor):
        # tag name can be anything; keep it short
        return dumper.represent_scalar('!QColor', data.name())

    yaml.SafeDumper.add_representer(QColor, qcolor_representer)
    yaml.SafeDumper.add_representer(QPoint, qpoint_representer)
    yaml.SafeDumper.add_representer(QSize,  qsize_representer)
    yaml.SafeDumper.add_representer(PosixPath, path_representer)

    # ── 2. Loader ← YAML ← Python ──────────────────────────────────────────────────
    def qpoint_constructor(loader, node):
        x, y = loader.construct_sequence(node)
        return QPoint(int(x), int(y))

    def qsize_constructor(loader, node):
        w, h = loader.construct_sequence(node)
        return QSize(int(w), int(h))

    def path_constructor(loader, node):
        path = loader.construct_scalar(node)
        return Path(path)

    def qcolor_constructor(loader, node):
        value = loader.construct_scalar(node)
        return QColor(value)
    yaml.SafeLoader.add_constructor('!QPoint', qpoint_constructor)
    yaml.SafeLoader.add_constructor('!QSize',  qsize_constructor)
    yaml.SafeLoader.add_constructor('!Path',  path_constructor)
    yaml.SafeLoader.add_constructor('!QColor', qcolor_constructor)

def overlay_yaml(settings_obj, yaml_file):
    with open(yaml_file, encoding='utf-8') as f:
        def walk(prefix, node):
            if isinstance(node, dict):
                for k, v in node.items():
                    walk(f"{prefix}/{k}" if prefix else k, v)
            else:
                print(f"Setting value: {prefix} : {node}")
                settings_obj.setValue(prefix, node)
        walk("", yaml.safe_load(f) or {})

if __name__ == "__main__":
    setup_yaml_parser()
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
    form = Form(settings=settings)
    form.show()

    # Run the main Qt loop
    sys.exit(app.exec_())
