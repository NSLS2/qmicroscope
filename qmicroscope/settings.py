from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QDialog,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QSpinBox,
)

from .container import Container
from .microscope import Microscope


class Settings(QDialog):
    roiClicked = Signal(int, int)

    def __init__(self, parent=None):
        super(Settings, self).__init__(parent)

        # Create a form with some controls
        self.selector = QComboBox()
        self.selector.setEditable(True)
        self.cameraCols = QSpinBox()
        self.cameraCols.setMinimum(1)
        self.cameraCols.setMaximum(6)
        self.cameraCols.setValue(1)
        self.cameraRows = QSpinBox()
        self.cameraRows.setMinimum(1)
        self.cameraRows.setMaximum(6)
        self.cameraRows.setValue(1)
        self.scale = QSpinBox()
        self.scale.setRange(100, 5000)
        self.scale.setSingleStep(10)
        self.scale.setValue(100)
        self.fps = QSpinBox()
        self.fps.setRange(1, 60)
        self.fps.setValue(5)
        self.xDivs = QSpinBox()
        self.xDivs.setRange(1, 50)
        self.xDivs.setValue(5)
        self.yDivs = QSpinBox()
        self.yDivs.setRange(1, 50)
        self.yDivs.setValue(5)
        self.color = QCheckBox()
        # self.container = None
        # self.microscope: "Microscope|None" = None

        self.url = QLineEdit("http://localhost:9998/jpg/image.jpg")
        self.okButton = QPushButton("OK")
        self.applyButton = QPushButton("Apply")
        self.cancelButton = QPushButton("Cancel")

        # Lay it out
        formLayout = QFormLayout()
        formLayout.addRow("Camera:", self.selector)
        rowsCols = QHBoxLayout()
        rowsCols.addWidget(self.cameraCols)
        rowsCols.addWidget(self.cameraRows)
        formLayout.addRow("Cameras:", rowsCols)
        formLayout.addRow("Camera Source:", self.url)
        formLayout.addRow("Image Scale:", self.scale)
        formLayout.addRow("Frame Rate:", self.fps)
        formLayout.addRow("X Divisions:", self.xDivs)
        formLayout.addRow("Y Divisions:", self.yDivs)
        formLayout.addRow("Color boxes:", self.color)

        # Create layout and add widgets
        layout = QVBoxLayout()
        hbox = QHBoxLayout()
        hbox.addStretch()
        hbox.addWidget(self.okButton)
        hbox.addWidget(self.applyButton)
        hbox.addWidget(self.cancelButton)
        hbox.addStretch()
        layout.addLayout(formLayout)
        layout.addLayout(hbox)
        self.setLayout(layout)

        self.okButton.clicked.connect(self.okClicked)
        self.applyButton.clicked.connect(self.applyClicked)
        self.cancelButton.clicked.connect(self.cancelClicked)

        # Connect up some signals and slots...
        self.selector.currentIndexChanged.connect(self.selectionChanged)
        self.cameraCols.valueChanged.connect(self.cameraColsChanged)
        self.cameraRows.valueChanged.connect(self.cameraRowsChanged)

    def setMicroscope(self, microscope: "Microscope"):
        self.microscope = microscope
        self.updateForm()

    def setContainer(self, container: "Container"):
        # Store a reference to the container, default to widget 0.
        self.container = container
        self.setMicroscope(container.microscope(0))
        self.updateCameraSelect()

    def okClicked(self):
        self.updateMicroscope()
        self.accept()

    def applyClicked(self):
        self.updateMicroscope()

    def cancelClicked(self):
        self.reject()

    def updateCameraSelect(self):
        # Iterate over the microscopes and create entries in the select.
        self.selector.clear()
        for i in range(self.container.count):
            # print(f'doing element {i}')
            self.selector.addItem(f"Camera {i + 1}", i)
        self.cameraCols.setValue(self.container.size[0])
        self.cameraRows.setValue(self.container.size[1])

    def selectionChanged(self, index):
        self.updateMicroscope()
        self.microscope = self.container.microscope(index)
        self.updateForm()

    def cameraColsChanged(self, value):
        if self.container is None:
            print("Error, no active container.")
            return
        self.container.size = [value, self.container.size[1]]
        self.updateCameraSelect()
        self.container.update()

    def cameraRowsChanged(self, value):
        if self.container is None:
            print("Error, no active container.")
            return
        self.container.size = [self.container.size[0], value]
        self.updateCameraSelect()
        self.container.update()

    def updateMicroscope(self):
        if not self.microscope:
            return
        self.microscope.url = self.url.text()
        self.microscope.fps = self.fps.value()
        self.microscope.xDivs = self.xDivs.value()
        self.microscope.yDivs = self.yDivs.value()
        self.microscope.color = self.color.isChecked()
        self.microscope.scale = [self.scale.value(), 100]
        self.microscope.update()

    def updateForm(self):
        if not self.microscope:
            return
        self.url.setText(self.microscope.url)
        self.fps.setValue(self.microscope.fps)
        self.xDivs.setValue(self.microscope.xDivs)
        self.yDivs.setValue(self.microscope.yDivs)
        self.color.setChecked(self.microscope.color)
        if len(self.microscope.scale) > 0:
            self.scale.setValue(self.microscope.scale[0])
