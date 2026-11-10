#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Overall tool to invoke the other GUI objects
"""

import os

from Qt import QtWidgets, QtCore, QtGui

from rmtc.gui.common import get_icon_path
from rmtc.gui.provenance.widgets import SignalBox
from rmtc.gui.ingestion.widgets import Junction
from rmtc.gui.traintrack.widgets import TrainTrack
from rmtc.gui.common.widgets import (
    Toolbar,
    ObjectPropertyEditor,
    Publisher,
    Log,
    Scheduler,
)
from rmtc.gui.common.preview import (
    DatasetViewer,
)


class GUI:

    def __init__(
        self,
        rmtc_system,
        app=None,
        provenance_widget=None,
        ingestion_widget=None,
        traintrack_widget=None,
        publisher_widget=None,
        property_widget=None,
        toolbar_widget=None,
        scheduler_widget=None,
        viewer_widget=None,
    ):
        self._app = app or QtWidgets.QApplication([])
        self._sys = rmtc_system

        # construct the items
        provenance = provenance_widget or SignalBox(rmtc_system)
        ingestion = ingestion_widget or Junction(rmtc_system)
        traintrack = traintrack_widget or TrainTrack(rmtc_system)
        toolbar = toolbar_widget or Toolbar(rmtc_system)
        publisher = publisher_widget or Publisher(rmtc_system)
        scheduler = scheduler_widget or Scheduler(rmtc_system)
        properties = property_widget or ObjectPropertyEditor(rmtc_system)
        viewer = viewer_widget or DatasetViewer(rmtc_system)
        log = Log(log=rmtc_system.log)

        # link events
        ingestion.train_request.connect(lambda run: scheduler.train(run))
        ingestion.infer_request.connect(lambda inference: scheduler.infer(inference))
        ingestion.build_request.connect(lambda artifacts: rmtc_system.build(artifacts))
        ingestion.publish_request.connect(
            lambda artifacts: publisher.publish(artifacts)
        )
        ingestion.examine_request.connect(
            lambda entities: (
                properties.set_obj(entities[0]),
                viewer.set_obj(entities[0]),
            )
        )
        provenance.examine_request.connect(
            lambda entities: properties.set_obj(entities[0])
        )
        traintrack.examine_request.connect(
            lambda entities: properties.set_obj(entities[0])
        )
        toolbar.layout_request.connect(lambda entities: (ingestion.layout(entities),))

        # layout
        ui = QtWidgets.QTabWidget()
        ui.addTab(ingestion, "Create")
        ui.addTab(traintrack, "Track")
        ui.addTab(provenance, "Trace")

        # dock the properties
        property_dock = QtWidgets.QDockWidget("Properties")
        property_dock.setWidget(properties)
        log_dock = QtWidgets.QDockWidget("Log")
        log_dock.setWidget(log)
        viewer_dock = QtWidgets.QDockWidget("Viewer")
        viewer_dock.setWidget(viewer)

        # create the main window
        self._main_window = QtWidgets.QMainWindow()
        self._main_window.setWindowTitle(f"RMTC ({rmtc_system.mode})")
        self._main_window.setWindowIcon(QtGui.QIcon(get_icon_path("rmtc")))
        pos = QtGui.QCursor.pos()
        self._main_window.setGeometry(QtCore.QRect(pos.x(), pos.y(), 1280, 720))
        self._main_window.addToolBar(toolbar)
        self._main_window.setCentralWidget(ui)
        self._main_window.addDockWidget(QtCore.Qt.LeftDockWidgetArea, property_dock)
        self._main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, viewer_dock)
        self._main_window.addDockWidget(QtCore.Qt.BottomDockWidgetArea, log_dock)

        width = self._main_window.width()
        height = self._main_window.height()
        property_dock.setMinimumWidth(int(width * 0.25))
        viewer_dock.setMinimumWidth(int(width * 0.25))
        log_dock.setMinimumHeight(int(height * 0.15))

    def run(self):
        self._main_window.show()
        self._app.exec_()

    @property
    def main_window(self):
        return self._main_window
