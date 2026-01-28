# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import os

from Qt import QtWidgets, QtGui, QtCore
from rmtc_core.gui.common.properties import ObjectProperties
from rmtc.system import LogMessage
from rmtc.track import EntityMessage


class Log(QtWidgets.QWidget):

    def __init__(self, log):
        super(Log, self).__init__()
        self._log = log
        self._content = QtWidgets.QPlainTextEdit()
        self._content.setReadOnly(True)
        self._content.setObjectName("Log")
        self._content.setStyleSheet(
            """
            QPlainTextEdit#Log {
                color: #909090;
                font-family: 'Courier New';
                font-size: 8pt;
            }
        """
        )
        scroller = QtWidgets.QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setWidget(self._content)
        scroller.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(scroller)
        self.setLayout(layout)
        log.broadcaster().add(
            LogMessage.POSTED, lambda text: self._content.appendPlainText(text)
        )


class Publisher(QtWidgets.QWidget):
    """Publisher widget, which dynamically populates based on the asset manager"""

    STYLESHEET = """
        QCheckBox::indicator:unchecked {
            background-color : #303030;
        };"""

    def __init__(self, system, entities=None, parent=None):
        super(Publisher, self).__init__(parent=parent)
        self._system = system
        self._entities = entities
        self.publish_widget = None

        self._setup_ui()

        if entities:
            self.set_entities(entities)

        self.set_build_pipelines(self._system.asset_manager.pipelines)

    def set_entities(self, entities):
        """Set the publishable entities."""
        self._entities = entities
        self.refresh_entities()
        self.publish_options_widget.set_entities(entities)

    def set_build_pipelines(self, pipelines):
        """Set the post-publish build pipelines."""
        self.build_pipelines_table.clearContents()
        pipeline_names = list(pipelines.keys())
        self.build_pipelines_table.setRowCount(len(pipeline_names))

        for row, pipeline_name in enumerate(pipeline_names):
            # Checkbox
            checkbox = QtWidgets.QCheckBox(parent=self.build_pipelines_table)
            checkbox.setStyleSheet(self.STYLESHEET)
            checkbox.setChecked(False)
            checkbox.setObjectName("checkbox")
            wrapper = QtWidgets.QWidget(parent=self.build_pipelines_table)
            wrapper_layout = QtWidgets.QHBoxLayout(wrapper)
            wrapper_layout.addWidget(checkbox)
            wrapper_layout.setAlignment(QtCore.Qt.AlignCenter)
            wrapper_layout.setContentsMargins(0, 0, 0, 0)
            self.build_pipelines_table.setCellWidget(row, 0, wrapper)

            # Entity name
            pipe_item = QtWidgets.QTableWidgetItem(pipeline_name)
            pipe_item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            self.build_pipelines_table.setItem(row, 1, pipe_item)

            build_pipeline = pipelines[pipeline_name]

            checkbox.setToolTip(build_pipeline.description)
            pipe_item.setToolTip(build_pipeline.description)

    def get_selected_build_pipelines(self):
        """Get supported build pipelines selected in the UI."""
        pipeline_names = []
        for row in range(self.build_pipelines_table.rowCount()):
            checkbox = self.build_pipelines_table.cellWidget(row, 0).findChild(
                QtWidgets.QCheckBox, "checkbox"
            )
            if checkbox.isChecked():
                pipe_item = self.build_pipelines_table.item(row, 1)
                pipeline_names.append(pipe_item.text())
        return pipeline_names

    def _setup_ui(self):
        """Set up the UI based on the asset manager."""
        layout = QtWidgets.QVBoxLayout()

        # Title
        title_label = QtWidgets.QLabel("Publish Entities", parent=self)
        layout.addWidget(title_label)

        # Entity table
        self.entity_table = QtWidgets.QTableWidget(parent=self)
        self.entity_table.setColumnCount(3)
        self.entity_table.setShowGrid(False)
        self.entity_table.setHorizontalHeaderLabels(["", "Name", "Category"])
        self.entity_table.verticalHeader().setVisible(False)
        self.entity_table.setFocusPolicy(QtCore.Qt.NoFocus)
        self.entity_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        # Column sizes
        self.entity_table.setColumnWidth(0, 20)
        header = self.entity_table.horizontalHeader()
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self.entity_table)

        # Asset manager publish options
        publish_options_ui = self._system.asset_manager.get_widget_class()
        if publish_options_ui is not None:
            self.publish_options_widget = publish_options_ui(
                entities=self._entities,
                parent=self,
            )
        else:
            self.publish_options_widget = PublishOptions(
                entities=self._entities,
                parent=self,
            )
        layout.addWidget(self.publish_options_widget)

        # Builders
        build_label = QtWidgets.QLabel("Build Pipelines", parent=self)
        layout.addWidget(build_label)
        self.build_pipelines_table = QtWidgets.QTableWidget(parent=self)
        self.build_pipelines_table.setColumnCount(2)
        self.build_pipelines_table.setShowGrid(False)
        self.build_pipelines_table.setHorizontalHeaderLabels(["", "Pipeline Name"])
        self.build_pipelines_table.verticalHeader().setVisible(False)
        self.build_pipelines_table.setFocusPolicy(QtCore.Qt.NoFocus)
        self.build_pipelines_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self.build_pipelines_table.setColumnWidth(0, 20)
        header = self.build_pipelines_table.horizontalHeader()
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.build_pipelines_table)

        self.setLayout(layout)

    def refresh_entities(self):
        """Populate the entities table."""
        self.entity_table.clearContents()
        self.entity_table.setRowCount(len(self._entities))

        for row, entity in enumerate(self._entities):
            # Checkbox
            checkbox = QtWidgets.QCheckBox(parent=self.entity_table)
            checkbox.setObjectName("checkbox")
            checkbox.setStyleSheet(self.STYLESHEET)
            checkbox.setChecked(True)
            wrapper = QtWidgets.QWidget(parent=self.entity_table)
            wrapper_layout = QtWidgets.QHBoxLayout(wrapper)
            wrapper_layout.addWidget(checkbox)
            wrapper_layout.setAlignment(QtCore.Qt.AlignCenter)
            wrapper_layout.setContentsMargins(0, 0, 0, 0)
            self.entity_table.setCellWidget(row, 0, wrapper)

            # Entity name
            entity_item = QtWidgets.QTableWidgetItem(entity.name)
            entity_item.setData(QtCore.Qt.UserRole, entity)
            entity_item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            self.entity_table.setItem(row, 1, entity_item)

            # Entity type
            item_category = QtWidgets.QTableWidgetItem(entity.category() or "")
            item_category.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            self.entity_table.setItem(row, 2, item_category)

    def get_selected_entities(self):
        """Get entities selected in the UI."""
        entities = []
        for row in range(self.entity_table.rowCount()):
            checkbox = self.entity_table.cellWidget(row, 0).findChild(
                QtWidgets.QCheckBox, "checkbox"
            )
            if checkbox.isChecked():
                entity_item = self.entity_table.item(row, 1)
                entities.append(entity_item.data(QtCore.Qt.UserRole))
        return entities

    def validate(self):
        """
        Check if the current publish options are valid.

        Returns:
            bool: True if options are good to publish, otherwise False
        """
        return self.publish_options_widget.validate()

    def publish(self, entities=None):
        """Publish the selected entities with the chosen options."""
        if entities is None:
            entities = self.get_selected_entities()
        if not entities:
            QtWidgets.QMessageBox.information(
                self,
                "Unable to Publish",
                "No publishable entities are selected",
                QtWidgets.QMessageBox.Ok,
            )
            return

        publish_text = "Are you sure to push and publish the following entities:\n\n"
        entities_text = ""
        for entity in entities:
            entities_text += f"{entity.name}\n"
        publish_text += entities_text
        result = QtWidgets.QMessageBox.question(
            self,
            "Publish?",
            publish_text,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )

        if result == QtWidgets.QMessageBox.Yes:
            # Build
            built_entities = []
            for pipeline_name in self.get_selected_build_pipelines():
                result = self._system.build(entities, pipeline_name=pipeline_name)
                built_entities.extend(result)

            built_uris = ""
            for entity in built_entities:
                built_uris += f"{entity.uri}\n"

            info_msg = ""
            if built_uris:
                self._system.log.info("Successfully built:\n" + built_uris)
                info_msg += "Successfully built:\n\n" + built_uris

            self._system.push(built_entities)

            # Publish
            to_publish = set(entities + built_entities)
            published = self._system.publish(
                to_publish, **self.publish_options_widget.publish_options
            )
            if len(published) != len(to_publish):
                QtWidgets.QMessageBox.warning(
                    self,
                    "Publish Complete",
                    "Failed to publish all entities - check logs",
                    QtWidgets.QMessageBox.Ok,
                )
                return

            published_uris = ""
            for entity in published:
                published_uris += f"{entity.uri}\n"
            self._system.log.info("Successfully published:\n" + published_uris)
            info_msg += "\nSuccessfully published:\n\n" + published_uris

            self._system.push(published)

            QtWidgets.QMessageBox.information(
                self,
                "Publish Complete",
                info_msg,
                QtWidgets.QMessageBox.Ok,
            )


class PublishOptions(QtWidgets.QWidget):

    def __init__(self, entities=None, parent=None):
        """
        Publishing options UI to be used within a publisher. This is for asset
        manager-specific settings, and may change for different entity type(s).

        Args:
            entities (list of RMTC entities): Entities to display options for
            parent (QtWidgets.QWidget): Parent widget
        """
        super(PublishOptions, self).__init__(parent=parent)
        self._entities = entities

    @property
    def entities(self):
        return self._entities

    def set_entities(self, entities):
        """
        Update the option(s) for the given entities
        """
        # Do entity-specific updates here
        self._entities = entities

    @property
    def publish_options(self):
        """
        Return the publish settings as arguments accepted by the
        asset manager publish() method.
        """
        return {}

    def validate(self):
        """
        Check if the current publish options are valid.

        Returns:
            bool: True if options are good to publish, otherwise False
        """
        return True


class ObjectPropertyEditor(QtWidgets.QWidget):

    def __init__(self, factory, obj=None):
        super(ObjectPropertyEditor, self).__init__()

        self._factory = factory
        self._obj = None
        self._properties = ObjectProperties(self._factory, parent=self)
        self._name = QtWidgets.QLineEdit()
        self._name.setPlaceholderText("No Object")
        self._name.setAlignment(QtCore.Qt.AlignCenter)
        self._name.setReadOnly(True)

        self._sync = QtWidgets.QLabel("UN-SYNCED")
        self._sync.setAlignment(QtCore.Qt.AlignCenter)
        self._sync.setObjectName("SyncLabel")
        self._sync.setStyleSheet("QLabel#SyncLabel { color: red; }")
        self._sync.hide()

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)

        scroller = QtWidgets.QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setWidget(self._properties)
        scroller.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._name)
        layout.addWidget(self._sync)
        layout.addWidget(line)
        layout.addWidget(scroller)
        self.setLayout(layout)

        self.obj = obj

    def set_obj(self, obj):

        # remove the old obj
        if self._obj is not None:
            self._obj.broadcaster.remove(EntityMessage.SYNCED, self.update)
            self._properties.obj = None
            self._obj = None

        # add the new one
        if obj is not None:
            self._obj = obj
            self._properties.obj = obj
            obj.broadcaster.add(EntityMessage.SYNCED, self.update)

        self.update()

    def update(self, obj=None):  # pylint: disable=unused-argument
        self._name.setText("")
        self._name.setEnabled(False)
        self._sync.hide()
        if self._obj is not None:
            self._name.setText(str(self._obj.obj_id))
            self._name.setEnabled(True)
            if self._obj.requires_sync():
                self._sync.show()

    @property
    def obj(self):
        return self._obj

    @obj.setter
    def obj(self, obj):
        self.set_obj(obj)


class EntitySearch(QtWidgets.QWidget):

    def __init__(self, system):
        super(EntitySearch, self).__init__()
        self._system = system
        self._categories = QtWidgets.QComboBox()
        self._categories.addItems(
            [
                "Any",
                "Solution",
                "Model",
                "Dataset",
                "Group",
                "License",
                "Checkpoint",
                "Inference",
                "Asset",
                "Run",
                "Weights",
                "Trainer",
            ]
        )
        self._entity_pattern = QtWidgets.QLineEdit("")
        self._entity_sync = QtWidgets.QCheckBox("Sync")
        self._entity_sync.setChecked(True)
        self._entity_pattern.setPlaceholderText("Fetch entities by regex search string")
        self._entity_pattern.returnPressed.connect(self.fetch)
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(QtWidgets.QLabel("Fetch entities:"))
        layout.addWidget(self._entity_pattern)
        layout.addWidget(self._categories)
        layout.addWidget(self._entity_sync)
        self.setLayout(layout)

    def fetch(self):
        """
        Fetch entities from the database based on search criteria.
        """

        # get pattern
        pattern = self._entity_pattern.text()
        if pattern == "":
            return

        # fetch
        category = str(self._categories.currentText())
        if category != "Any":
            self._system.get_entities(
                pattern, category=category, sync=self._entity_sync.isChecked()
            )
        else:
            self._system.get_entities(pattern, sync=self._entity_sync.isChecked())


class ContextEditor(QtWidgets.QWidget):

    def __init__(self, system):
        super(ContextEditor, self).__init__()
        self._system = system
        self._context_edit = QtWidgets.QLineEdit("")
        self._context_edit.setPlaceholderText("/proj/sequence/scene/shot")
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(QtWidgets.QLabel("Filter Context:"))
        layout.addWidget(self._context_edit)
        self.setLayout(layout)

    @property
    def context(self):
        return self._context_edit.text()


class Toolbar(QtWidgets.QToolBar):

    def __init__(self, system):
        super(Toolbar, self).__init__("RMTC")
        self._system = system
        asset_path = f"{os.getenv('RMTC_RESOURCES')}/icons"

        # create
        self._push_action = QtWidgets.QAction(
            QtGui.QIcon(f"{asset_path}/push.svg"), "Push", self
        )
        self._fetch_action = QtWidgets.QAction(
            QtGui.QIcon(f"{asset_path}/fetch.svg"), "Fetch", self
        )
        self._clear_action = QtWidgets.QAction(
            QtGui.QIcon(f"{asset_path}/clear.svg"), "Clear", self
        )

        self._context_editor = ContextEditor(system)
        self._entity_search = EntitySearch(system)

        self._push_action.triggered.connect(self.push)
        self._fetch_action.triggered.connect(self.fetch)
        self._clear_action.triggered.connect(self.clear)

        self._context_editor.setEnabled(False)  # TODO: not implemented

        # layout
        self.addWidget(self._entity_search)
        self.addAction(self._push_action)
        self.addAction(self._fetch_action)
        self.addAction(self._clear_action)
        self.addSeparator()
        self.addWidget(self._context_editor)

    def push(self):
        result = QtWidgets.QMessageBox.question(
            self,
            "Push?",
            "Push changes to storage?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if result == QtWidgets.QMessageBox.Yes:
            self._system.push()

    def clear(self):
        if self._system.objects.is_empty():
            return
        result = QtWidgets.QMessageBox.question(
            self,
            "Clear?",
            """Are you sure to clear local session?
NOTE: This will delete all local objects that are not pushed to the store""",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if result == QtWidgets.QMessageBox.Yes:
            self._system.clear()

    def fetch(self):
        pattern, yes = QtWidgets.QInputDialog.getText(
            self, "Entity Name", "Enter entity pattern to fetch:"
        )
        if yes and pattern:
            self._system.get_entities(name=pattern)
