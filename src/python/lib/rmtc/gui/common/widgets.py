# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from Qt import QtWidgets, QtGui, QtCore
from rmtc.gui.common.properties import ObjectProperties
from rmtc.gui.common import get_icon_path
from rmtc.system import LogMessage, RMTCException, TypeName
from rmtc.system.objects import Object
from rmtc.track.store import EntityMessage


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


class ObjectType(QtWidgets.QWidget):
    """Allow creation of an object from a category and inspect"""

    changed = QtCore.Signal(Object)

    def __init__(self, factory, category, parent=None):
        super(ObjectType, self).__init__(parent=parent)
        self._factory = factory
        type_names = factory.get_type_names(category)
        completer = QtWidgets.QCompleter([str(item) for item in type_names])
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        self._type_select = QtWidgets.QLineEdit(parent=self)
        self._type_select.setCompleter(completer)
        self._type_select.setPlaceholderText(f"Enter type of {category}")
        self._type_select.returnPressed.connect(self.change_type)
        self._type_name = None
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._type_select)
        self.setLayout(layout)

    @property
    def type_name(self):
        return self._type_name

    def change_type(self):
        type_name = TypeName(self._type_select.text())
        type_info = self._factory.get_type_info(type_name)
        self._type_name = None
        if type_info is not None:
            self._type_name = type_name.abridged()


class Scheduler(QtWidgets.QWidget):

    def __init__(self, rmtc_system, parent=None):
        super(Scheduler, self).__init__(parent=parent)
        self._system = rmtc_system
        self._scheduler_type = ObjectType(rmtc_system.factory, "Scheduler", parent=self)
        layout = QtWidgets.QFormLayout()
        layout.addRow("Scheduler", self._scheduler_type)
        self.setLayout(layout)

    def train(self, run):

        if self._scheduler_type.type_name is None:
            return

        # use local if empty
        scheduler = self._system.create_scheduler(
            self._scheduler_type.type_name,
            task=run,
        )

        # TODO : make this work async
        scheduler()

    def infer(self, inference):
        """When the user clicks accept, create and submit the inferece."""

        if self._scheduler_type.type_name is None:
            return

        if inference.model is None:
            if inference.solution is None:
                raise RMTCException("No model or solution specified for inference")
            run = self._system.get_best_run(solution=inference.solution)
            if run is not None:
                inference.model = run.model
                if inference.weights is None:
                    inference.weights = run.result_weights
        if inference.model is None:
            raise RMTCException("No model defined")

        scheduler = self._system.create_scheduler(
            self._scheduler_type.type_name,
            task=inference,
        )

        # TODO : make this work async
        scheduler()


class Publisher(QtWidgets.QWidget):
    """Publisher widget, which dynamically populates based on the asset manager"""

    STYLESHEET = """
        QCheckBox::indicator:unchecked {
            background-color : #303030;
        };"""

    def __init__(self, rmtc_system, entities=None, parent=None, publish_options=None):
        super(Publisher, self).__init__(parent=parent)
        self._system = rmtc_system
        self._entities = entities
        self._publish_options = publish_options

        self._setup_ui()

        if entities:
            self.set_entities(entities)

        self.set_build_pipelines(self._system.ops.pipelines)

    def set_entities(self, entities):
        """Set the publishable entities."""
        self._entities = entities
        self.refresh_entities()
        self._publish_options.set_entities(entities)

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
        if self._publish_options is None:
            self._publish_options = PublishOptions(
                entities=self._entities,
                parent=self,
            )
        layout.addWidget(self._publish_options)

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
        return self._publish_options.validate()

    def publish(self, entities=None, **kwargs):
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
                to_publish, **self._publish_options.publish_options
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

    def __init__(self, rmtc_system, obj=None):
        super(ObjectPropertyEditor, self).__init__()

        self._system = rmtc_system
        self._factory = rmtc_system.factory
        self._obj = None
        self._properties = ObjectProperties(self._factory, parent=self)
        self._name = QtWidgets.QLineEdit()
        self._name.setPlaceholderText("No Object")
        self._name.setAlignment(QtCore.Qt.AlignCenter)
        self._name.setReadOnly(True)

        self._copy = QtWidgets.QPushButton(QtGui.QIcon(get_icon_path("copy")), "")
        self._copy.setFlat(True)
        self._copy.clicked.connect(self.copy_name)

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

        top_widget = QtWidgets.QWidget()
        name_layout = QtWidgets.QHBoxLayout(top_widget)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.addWidget(self._name)
        name_layout.addWidget(self._copy)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(top_widget)
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

    def copy_name(self):
        QtWidgets.QApplication.clipboard().setText(self._name.text())

    def update(self, obj=None):
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

    layout_request = QtCore.Signal(Object)

    def __init__(self, rmtc_system):
        super(EntitySearch, self).__init__()
        self._system = rmtc_system
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
                "Right",
            ]
        )
        self._entity_pattern = QtWidgets.QLineEdit("")
        self._entity_sync = QtWidgets.QCheckBox("Sync")
        self._entity_sync.setChecked(True)
        self._entity_pattern.setPlaceholderText("Fetch entities by regex search string")
        self._entity_pattern.returnPressed.connect(self.fetch)
        self._entity_exact = QtWidgets.QCheckBox("Exact")
        self._entity_exact.setChecked(False)
        self._entity_limit = QtWidgets.QLineEdit(str(self._system.track.store.limit))
        self._entity_limit.setValidator(
            QtGui.QIntValidator(1, self._system.track.store.limit)
        )
        self._entity_limit.setFixedWidth(30)
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(QtWidgets.QLabel("Fetch:"))
        layout.addWidget(self._entity_pattern)
        layout.addWidget(self._categories)
        layout.addWidget(self._entity_limit)
        # layout.addWidget(self._entity_sync)
        # layout.addWidget(self._entity_exact)
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
        entities = []
        if category != "Any":
            entities = self._system.get_entities(
                pattern,
                category=category,
                exact=self._entity_exact.isChecked(),
                sync=self._entity_sync.isChecked(),
            )
        else:
            entities = self._system.get_entities(
                pattern,
                sync=self._entity_sync.isChecked(),
                exact=self._entity_exact.isChecked(),
                limit=int(self._entity_limit.text()),
            )
        if entities:
            self.layout_request.emit(entities)


class DeviceEditor(QtWidgets.QWidget):

    def __init__(self, system):
        super(DeviceEditor, self).__init__()
        self._system = system
        self._device_edit = QtWidgets.QLineEdit("")
        self._device_edit.setPlaceholderText("/proj/sequence/scene/shot")
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(QtWidgets.QLabel("Filter Device:"))
        layout.addWidget(self._device_edit)
        self.setLayout(layout)

    @property
    def device(self):
        return self._device_edit.text()


class Toolbar(QtWidgets.QToolBar):

    def __init__(self, system):
        super(Toolbar, self).__init__("RMTC")
        self._system = system

        # create
        self._push_action = QtWidgets.QAction(
            QtGui.QIcon(get_icon_path("push")), "Push", self
        )
        self._fetch_action = QtWidgets.QAction(
            QtGui.QIcon(get_icon_path("fetch")), "Fetch", self
        )
        self._clear_action = QtWidgets.QAction(
            QtGui.QIcon(get_icon_path("clear")), "Clear", self
        )

        self._device_editor = DeviceEditor(system)
        self._entity_search = EntitySearch(system)

        self._push_action.triggered.connect(self.push)
        self._fetch_action.triggered.connect(self.fetch)
        self._clear_action.triggered.connect(self.clear)

        self._device_editor.setEnabled(False)  # TODO: not implemented

        # layout
        self.addWidget(self._entity_search)
        self.addSeparator()
        self.addAction(self._push_action)
        self.addAction(self._fetch_action)
        self.addAction(self._clear_action)
        self.addSeparator()
        self.addWidget(self._device_editor)

    @property
    def layout_request(self):
        return self._entity_search.layout_request

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


class ClickedLineEdit(QtWidgets.QLineEdit):
    """
    LineEdit that emits a signal whenever the mouse is pressed or released.
    """

    pressed = QtCore.Signal()  # Emits when line edit is clicked on
    released = QtCore.Signal()  # Emits when mouse is released over the line edit

    def mousePressEvent(self, event):
        super(ClickedLineEdit, self).mousePressEvent(event)
        self.pressed.emit()

    def mouseReleaseEvent(self, event):
        super(ClickedLineEdit, self).mouseReleaseEvent(event)
        self.released.emit()


class FilterComboBox(QtWidgets.QComboBox):
    """
    A combo box that allows the user to type into the line edit
    to filter the list of items.
    """

    def __init__(self, parent=None):
        super(FilterComboBox, self).__init__(parent)

        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setEditable(True)
        self.setInsertPolicy(QtWidgets.QComboBox.NoInsert)

        self._wheelScrollEnabled = False

        self._clickedLineEdit = ClickedLineEdit(parent=self)
        self.setLineEdit(self._clickedLineEdit)

        self._filterModel = QtCore.QSortFilterProxyModel(parent=self)
        self._filterModel.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self._filterModel.setSourceModel(self.model())

        self._completer = QtWidgets.QCompleter(parent=self)
        self._completer.setModel(self._filterModel)
        self._completer.setCompletionMode(
            QtWidgets.QCompleter.UnfilteredPopupCompletion
        )

        self.setCompleter(self._completer)
        self.view().installEventFilter(self)

        self._connectSignals()

    def _connectSignals(self):
        self.lineEdit().textEdited.connect(self._filterModel.setFilterFixedString)
        self._completer.activated.connect(self.onCompleterActivated)
        self._clickedLineEdit.released.connect(self.lineEditActivated)
        self._clickedLineEdit.textEdited.connect(self.lineEditTextEdited)
        self._clickedLineEdit.editingFinished.connect(self.lineEditEditingFinished)

    def setModel(self, model):
        super(FilterComboBox, self).setModel(model)
        self._filterModel.setSourceModel(model)
        self._completer.setModel(self._filterModel)

    def setModelColumn(self, column):
        self._completer.setCompletionColumn(column)
        self._filterModel.setFilterKeyColumn(column)
        super(FilterComboBox, self).setModelColumn(column)

    def onCompleterActivated(self, text):
        if text:
            index = self.findText(str(text))
            self.setCurrentIndex(index)

    def eventFilter(self, _watched, event):
        if event.type() == QtCore.QEvent.KeyPress:
            if event.key() == QtCore.Qt.Key_Up or event.key() == QtCore.Qt.Key_Down:
                return False

            # NOTE: By default when the standard combo box popup is visible it will steal all
            # of the user's keyboard input. We want to allow the user to also start typing, to
            # filter the items, while that popup is visible. So we intercept the key event, wrap
            # it up into a new event, and then feed it directly to the line edit. The current
            # event is ignored.
            newEvent = QtGui.QKeyEvent(
                event.type(),
                event.key(),
                event.modifiers(),
                event.text(),
                event.isAutoRepeat(),
                event.count(),
            )

            focusEvent = QtGui.QFocusEvent(
                QtCore.QEvent.FocusIn, QtCore.Qt.OtherFocusReason
            )
            QtCore.QCoreApplication.postEvent(self.lineEdit(), focusEvent)
            QtCore.QCoreApplication.postEvent(self.lineEdit(), newEvent)
            return True

        return False

    def setWheelScrollEnabled(self, enabled=True):
        self._wheelScrollEnabled = enabled

    def wheelEvent(self, event):
        if self._wheelScrollEnabled:
            super(FilterComboBox, self).wheelEvent(event)
        else:
            event.ignore()

    def lineEditActivated(self):
        """
        When the user clicks into the line edit show the full list of items
        in the combo box, using the native popup.
        """
        self.showPopup()
        self._clickedLineEdit.selectAll()
        self._clickedLineEdit.setFocus()

    def lineEditTextEdited(self, _text):
        """
        Hide the native popup in favor of the completer popup once
        the user starts to edit the text in the line edit
        """
        self.hidePopup()

    def lineEditEditingFinished(self):
        """
        Make sure the text of the line edit is not left in an invalid state
        """
        if self.currentText() != self.itemText(self.currentIndex()):
            self.lineEdit().setText(self.itemText(self.currentIndex()))

    def setPopupMinimumWidth(self, width):
        """Set minimum width for the popup"""
        self.view().setMinimumWidth(width)
        self._completer.popup().setMinimumWidth(width)

    def setStyle(self, style):
        super(FilterComboBox, self).setStyle(style)
        popup = self._completer.popup()
        popup.setStyle(style)
        self._completer.setPopup(popup)

    def setFont(self, font):
        super(FilterComboBox, self).setFont(font)
        popup = self._completer.popup()
        popup.setFont(font)
        self._completer.setPopup(popup)
