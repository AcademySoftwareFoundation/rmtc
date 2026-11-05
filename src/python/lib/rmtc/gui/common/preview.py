# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import numpy as np

from Qt import QtWidgets, QtGui, QtCore
from rmtc.ops.artifacts import Dataset
from rmtc.ops.assets import Image


class AssetPreview(QtWidgets.QWidget):

    def __init__(self, rmtc_system, title=None, entities=None, parent=None):
        super(AssetPreview, self).__init__(parent=parent)
        self._system = rmtc_system
        self._title = QtWidgets.QLabel(title)
        self._label = QtWidgets.QLabel("No Asset")
        self._label.setMinimumHeight(50)
        self._label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._label.setSizePolicy(
            QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding
        )
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(
            self._title,
            alignment=QtCore.Qt.AlignmentFlag.AlignTop
            | QtCore.Qt.AlignmentFlag.AlignHCenter,
        )
        layout.addWidget(self._label)
        self.setLayout(layout)
        if entities is not None:
            self.set_obj(entities[0])

    def set_obj(self, asset):
        self._label.setText("No Asset")
        if asset is not None:
            self._label.setText(f"NO PREVIEW\n'{asset.name}'")


class SkeletonPreview(AssetPreview):
    """
    Joint hierarchy with names in 3D viewports
    """

    pass


class LabelPreview(AssetPreview):
    """
    Text list
    """

    pass


class CameraPreview(AssetPreview):
    """Simple 3D viewport of camera against an origin with the frame"""

    pass


class MeshPreview(AssetPreview):
    """Simple 3D viewport of mesh"""

    pass


class ImagePreview(AssetPreview):

    def __init__(self, rmtc_system, title=None, entities=None, parent=None):
        super(ImagePreview, self).__init__(
            rmtc_system=rmtc_system, title=title, parent=parent
        )
        self._image = None
        self._image_view = None
        if entities is not None:
            self.set_obj(entities[0])

    def resizeEvent(self, event):
        if self._image_view is not None:
            scaled = self._image_view.scaledToHeight(self.height())
            self._label.setPixmap(QtGui.QPixmap.fromImage(scaled))
        super(ImagePreview, self).resizeEvent(event)

    def set_obj(self, obj):
        self._image = obj
        self._image_view = None
        self._label.setPixmap(None)
        if self._image is None:
            self._label.setText("No Asset")
            return
        if self._image.is_valid():
            data = self._image.tensors[0]
            data = np.clip(data * 255.0, 0, 255)
            data = np.ascontiguousarray(data, dtype=np.uint8)
            self._image_view = QtGui.QImage(
                data,
                self._image.width,
                self._image.height,
                QtGui.QImage.Format.Format_RGBA8888,
            ).copy()
            scaled = self._image_view.scaledToHeight(self._label.height())
            self._label.setPixmap(QtGui.QPixmap.fromImage(scaled))
        else:
            self._label.setText(obj.name)


class DatasetViewer(QtWidgets.QWidget):

    def __init__(self, rmtc_system, entities=None, parent=None):
        super(DatasetViewer, self).__init__(parent=parent)

        self._dataset = None
        self._system = rmtc_system
        self._iterator = None
        self._row = None
        self._index = 0
        self._row_widget = QtWidgets.QWidget()
        self._load = QtWidgets.QPushButton("No Dataset")
        self._load.clicked.connect(self.load)
        self._load.setEnabled(False)
        self._load.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding,
        )
        self._row_layout = QtWidgets.QHBoxLayout(self._row_widget)
        self._row_layout.addWidget(self._load)
        self._widgets = []
        self._slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._slider.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Ignored,
        )
        self._slider.valueChanged.connect(self.seek)
        self._slider.setSingleStep(1)
        self._slider.setTickInterval(10)
        self._label = QtWidgets.QLabel("0000/0000")
        self._load.setEnabled(False)
        self._label.setEnabled(False)
        self._slider.setEnabled(False)

        # layout
        footer = QtWidgets.QWidget()
        footer_layout = QtWidgets.QHBoxLayout(footer)
        footer_layout.addWidget(self._label)
        footer_layout.addWidget(self._slider)
        scroller = QtWidgets.QScrollArea()
        scroller.setWidget(self._row_widget)
        scroller.setWidgetResizable(True)
        scroller.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(scroller)
        layout.addWidget(footer)
        self.setLayout(layout)

        if entities is not None:
            self.set_obj(entities[0])

    def set_obj(self, obj):

        # cleanup
        if self._dataset is not None:
            self._system.ops.asset_manager.reset([self._dataset])
            self._dataset = None
            self._iterator = None
            self._index = 0
            self._slider.setValue(0)
            self._label.setText("0000/0000")
            self._load.setText("No Dataset")
            self._load.setEnabled(False)
            self._label.setEnabled(False)
            self._slider.setEnabled(False)

        # clean up
        if self._row is not None:
            self._system.ops.asset_manager.reset(self._row)
        for widget in self._widgets:
            self._row_layout.removeWidget(widget)
            widget.deleteLater()
        self._widgets = []

        # assign
        if isinstance(obj, Dataset):
            self._dataset = obj
        else:
            self._dataset = None

        # sort label
        self._load.show()
        if self._dataset is not None:
            self._load.setEnabled(True)
            self._load.setText(f"Load: {self._dataset.name}")
        else:
            self._load.setEnabled(False)
            self._load.setText("No Dataset")

    def seek(self, row):
        if self._iterator is not None:
            while self._index != row:
                try:
                    self._row = next(self._iterator)
                    self._index += 1
                except StopIteration:
                    self._iterator = iter(self._dataset)
                    self._index = -1
            self.show()

    def load(self):

        # setup iterator
        if self._dataset is not None:
            if self._iterator is None:
                try:
                    self._system.ops.asset_manager.read([self._dataset])
                    self._slider.setMaximum(len(self._dataset) - 1)
                    self._iterator = iter(self._dataset)
                    self._row = next(self._iterator)
                    self._load.hide()
                    self._label.setEnabled(True)
                    self._slider.setEnabled(True)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    self._system.log.error(e)
                self._index = 0
                self._slider.setValue(0)
                self.show()

    def show(self):

        # clean up old row
        if self._row is not None:
            self._system.ops.asset_manager.reset(self._row)
            for widget in self._widgets:
                self._row_layout.removeWidget(widget)
                widget.deleteLater()
            self._widgets = []

        # setup new row
        if self._row is not None:
            self._label.setText(f"{self._index+1:04}/{len(self._dataset):04}")
            self._system.ops.asset_manager.read(self._row)
            for i, asset in enumerate(self._row):
                if isinstance(asset, Image):
                    widget = ImagePreview(
                        self._system,
                        title=self._dataset.get_column_name(i),
                        entities=[asset],
                        parent=self,
                    )
                else:
                    widget = AssetPreview(
                        self._system,
                        title=self._dataset.get_column_name(i),
                        entities=[asset],
                        parent=self,
                    )
                self._row_layout.addWidget(widget)
                self._widgets.append(widget)
