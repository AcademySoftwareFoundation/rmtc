# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import sys

from Qt import QtWidgets, QtCore

from rmtc.objects import PropertyType, Object, PropertyMessage
from rmtc.system import Type, TypeName, RMTCException


def resolve_type(name, factory, prop, index):
    type_name = TypeName(name)
    type_class = factory.resolve(type_name)
    if type_class is not None:
        value = Type(type_class=type_class, type_name=type_name)
        prop.set(value, index)


def _blocked_call(widget, func, *args):
    """This prevents an re-entrance bug when widgets are updated"""
    try:
        widget.blockSignals(True)
        try:
            func(*args)
        finally:
            widget.blockSignals(False)
    except RuntimeError:  # HACK : catch C++ warnings, unlikely
        pass


def _create_widget(prop, factory, index=0, parent=None):

    widget = None
    value = prop.get(index)
    type_class = prop.type_class

    if prop.prop_type == PropertyType.OBJECT:

        if prop.is_member_object():

            category = prop.type_class.category()
            widget = ObjectWidget(value, factory, category, parent=parent)
            widget.changed.connect(lambda obj: prop.set(obj, index))

            # listen to prop
            cb = lambda prop: _blocked_call(widget, widget.set_obj, prop.get(index))
            prop.broadcaster.add(PropertyMessage.UPDATED, cb)
            widget.destroyed.connect(
                lambda: prop.broadcaster.remove(PropertyMessage.UPDATED, cb)
            )

        else:

            widget = QtWidgets.QLineEdit(parent=parent)
            if value is not None:
                widget.setText(str(value.obj_id))
            widget.setPlaceholderText("Not Set")
            widget.setReadOnly(True)

            # listen to prop
            cb = lambda prop: _blocked_call(
                widget,
                widget.setText,
                (
                    str(prop.get(index).obj_id)
                    if prop.get(index) is not None
                    else "Not Set"
                ),
            )
            prop.broadcaster.add(PropertyMessage.UPDATED, cb)
            widget.destroyed.connect(
                lambda: prop.broadcaster.remove(PropertyMessage.UPDATED, cb)
            )

    elif prop.prop_type == PropertyType.ENUM:

        # NOTE : assumes the enum is contiguous i.e. value == index
        elements = [item.name for item in type_class]
        widget = QtWidgets.QComboBox(parent=parent)
        widget.addItems(elements)
        widget.setCurrentIndex(value)
        widget.currentIndexChanged.connect(lambda idx: prop.set(idx, index))

        # listen to prop
        cb = lambda prop: _blocked_call(widget, widget.setCurrentIndex, prop.get(index))
        prop.broadcaster.add(PropertyMessage.UPDATED, cb)
        widget.destroyed.connect(
            lambda: prop.broadcaster.remove(PropertyMessage.UPDATED, cb)
        )

    elif prop.prop_type == PropertyType.TYPE:

        # build list of typenames
        category = None
        if value.type_name is not None and value.type_name.is_valid():
            category = value.type_name.category
        elif prop.default is not None:  # if it is none then check the default
            category = prop.default.type_class.category()
        else:
            raise RMTCException(
                f"Can't create widget for {prop.name}, no category info"
            )
        type_names = []
        for type_name in factory.get_type_names(category=category):
            type_info = factory.get_type_info(type_name)
            if not type_info["abstract"]:
                type_names.append(type_name)

        # create widget
        widget = QtWidgets.QComboBox(parent=parent)
        type_names.sort()
        widget.addItems(["Not Assigned"] + [str(item) for item in type_names])
        if value.type_name is not None:
            text = str(value.type_name.abridged())
            widget.setCurrentIndex(widget.findText(text))
        else:
            widget.setCurrentIndex(0)
        widget.currentTextChanged.connect(
            lambda text: resolve_type(text, factory, prop, index)
        )

        # listen to prop
        cb = lambda prop: _blocked_call(
            widget,
            widget.setCurrentIndex,
            (
                widget.findText(
                    str(prop.get(index).type_name.abridged())
                    if prop.get(index) is not None
                    else ""
                )
            ),
        )
        prop.broadcaster.add(PropertyMessage.UPDATED, cb)
        widget.destroyed.connect(
            lambda: prop.broadcaster.remove(PropertyMessage.UPDATED, cb)
        )

    elif prop.prop_type == PropertyType.BOOLEAN:

        widget = QtWidgets.QCheckBox(parent=parent)
        widget.setChecked(value)
        widget.stateChanged.connect(
            lambda state: prop.set(state == QtCore.Qt.Checked, index)
        )

        # listen to prop
        cb = lambda prop: _blocked_call(widget, widget.setChecked, prop.get(index))
        prop.broadcaster.add(PropertyMessage.UPDATED, cb)
        widget.destroyed.connect(
            lambda: prop.broadcaster.remove(PropertyMessage.UPDATED, cb)
        )

    elif prop.prop_type == PropertyType.URI:

        widget = QtWidgets.QLineEdit(str(value), parent=parent)
        widget.setPlaceholderText("Enter URI")
        widget.editingFinished.connect(lambda: prop.set(widget.text(), index))

        # listen to prop
        cb = lambda prop: _blocked_call(
            widget,
            widget.setText,
            (str(prop.get(index)) if prop.get(index) is not None else ""),
        )
        prop.broadcaster.add(PropertyMessage.UPDATED, cb)
        widget.destroyed.connect(
            lambda: prop.broadcaster.remove(PropertyMessage.UPDATED, cb)
        )

    elif prop.prop_type == PropertyType.DATETIME:

        widget = QtWidgets.QDateTimeEdit(parent=parent)
        widget.setDateTime(
            QtCore.QDateTime.fromString(str(prop.get(index)), QtCore.Qt.ISODate)
        )
        widget.dateTimeChanged.connect(
            lambda time: prop.set(time.toString(QtCore.Qt.ISODate), index)
        )

        # listen to prop
        cb = lambda prop: _blocked_call(
            widget,
            widget.setDateTime,
            (
                QtCore.QDateTime.fromString(str(prop.get(index)), QtCore.Qt.ISODate)
                if prop.get(index) is not None
                else QtCore.QDateTime()
            ),
        )
        prop.broadcaster.add(PropertyMessage.UPDATED, cb)
        widget.destroyed.connect(
            lambda: prop.broadcaster.remove(PropertyMessage.UPDATED, cb)
        )

    elif prop.prop_type == PropertyType.NUMBER:

        widget = QtWidgets.QDoubleSpinBox(parent=parent)
        widget.setRange(-sys.float_info.max, sys.float_info.max)
        widget.valueChanged.connect(lambda value: prop.set(value, index))

        # listen to prop
        cb = lambda prop: _blocked_call(widget, widget.setValue, prop.get(index))
        prop.broadcaster.add(PropertyMessage.UPDATED, cb)
        widget.destroyed.connect(
            lambda: prop.broadcaster.remove(PropertyMessage.UPDATED, cb)
        )

    elif prop.prop_type == PropertyType.INTEGER:

        widget = QtWidgets.QSpinBox(parent=parent)
        widget.setRange(-(2**31), 2**31 - 1)
        widget.setValue(value)
        widget.valueChanged.connect(lambda value: prop.set(value, index))

        # listen to prop
        cb = lambda prop: _blocked_call(widget, widget.setValue, prop.get(index))
        prop.broadcaster.add(PropertyMessage.UPDATED, cb)
        widget.destroyed.connect(
            lambda: prop.broadcaster.remove(PropertyMessage.UPDATED, cb)
        )

    else:

        widget = QtWidgets.QLineEdit(str(value), parent=parent)
        widget.setPlaceholderText("Enter Value")
        widget.editingFinished.connect(lambda: prop.set(widget.text(), index))

        # listen to prop
        cb = lambda prop: _blocked_call(
            widget,
            widget.setText,
            (str(prop.get(index)) if prop.get(index) is not None else ""),
        )
        prop.broadcaster.add(PropertyMessage.UPDATED, cb)
        widget.destroyed.connect(
            lambda: prop.broadcaster.remove(PropertyMessage.UPDATED, cb)
        )

    return widget


class Expander(QtWidgets.QWidget):

    def __init__(self, title, widget, parent=None):
        super(Expander, self).__init__(parent=parent)

        self._title = QtWidgets.QLabel(title)

        self._expand_button = QtWidgets.QPushButton("expand", parent=self)
        self._expand_button.clicked.connect(self.expand)

        self._content = QtWidgets.QFrame(parent=self)
        self._content.setObjectName("Expander")
        self._content.setStyleSheet("""
            QFrame#Expander {
                border: 1px solid #909090;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        self._content.setVisible(False)
        self._content_layout = QtWidgets.QVBoxLayout(self._content)
        widget.parent = self._content
        self._content_layout.addWidget(widget)

        line = QtWidgets.QWidget(parent=self)
        line_layout = QtWidgets.QHBoxLayout(line)
        line_layout.addWidget(self._title)
        line_layout.addWidget(self._expand_button)
        line_layout.setContentsMargins(0, 0, 0, 0)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(line)
        layout.addWidget(self._content)
        self.setLayout(layout)

    def expand(self):

        self._content.setVisible(not self._content.isVisible())
        label = "expand"
        if self._content.isVisible():
            label = "collapse"
        self._expand_button.setText(label)


class ObjectWidget(QtWidgets.QWidget):
    """Allow creation of an object from a category and inspect"""

    changed = QtCore.Signal(Object)

    def __init__(self, obj, factory, category, parent=None):
        super(ObjectWidget, self).__init__(parent=parent)

        self._obj_editor = ObjectProperties(factory, parent=self)
        self._obj_editor.obj = obj
        self._obj_creator = None
        self._obj = obj
        self._factory = factory

        type_names = factory.get_type_names(category)
        completer = QtWidgets.QCompleter([str(item) for item in type_names])
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        self._obj_creator = QtWidgets.QLineEdit(parent=self)
        self._obj_creator.setCompleter(completer)
        self._obj_creator.setPlaceholderText(f"Enter type of {category}")
        self._obj_creator.returnPressed.connect(self.change_object)

        self.update_widgets()

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._obj_creator)
        layout.addWidget(self._obj_editor)
        self.setLayout(layout)

    @property
    def obj(self):
        return self._obj

    def set_obj(self, obj):
        if self._obj == obj:
            return
        self._obj = obj
        self._obj_editor.obj = obj
        self.update_widgets()

    @obj.setter
    def obj(self, value):
        self.set_obj(value)

    def update_widgets(self):
        if self._obj is None:
            self._obj_editor.hide()
        else:
            self._obj_creator.setText(self._obj.class_category)

    def change_object(self):
        if self._obj is not None:
            type_name = self._factory.resolve_inverse(self._obj.__class__)
            if type_name is None:
                return
            if self._obj_creator.text() == str(type_name.abridged()):
                return
            result = QtWidgets.QMessageBox.question(
                self,
                "Replace Object?",
                f"Replace {self._obj.name}?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            if result != QtWidgets.QMessageBox.Yes:
                return
        obj = self._factory.create(TypeName(self._obj_creator.text()))
        self._obj_editor.obj = obj
        self._obj = obj
        self.changed.emit(obj)
        if obj is not None:
            self._obj_editor.show()
        else:
            self._obj_editor.hide()


class ObjectProperties(QtWidgets.QWidget):
    """Inspect the properties of an existing object"""

    def __init__(self, factory, obj=None, parent=None):
        super(ObjectProperties, self).__init__(parent=parent)

        self._factory = factory
        self._obj = None
        self._prop_widgets = []
        self._obj_widgets = []

        props_widget = QtWidgets.QWidget(parent=self)
        self._props_layout = QtWidgets.QFormLayout(props_widget)
        self._props_layout.setContentsMargins(0, 0, 0, 0)

        objs_widget = QtWidgets.QWidget(parent=self)
        self._objs_layout = QtWidgets.QVBoxLayout(objs_widget)
        self._objs_layout.setContentsMargins(0, 0, 0, 0)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(5, 0, 5, 0)
        layout.addWidget(props_widget)
        layout.addWidget(objs_widget)
        layout.addStretch()
        self.setLayout(layout)

        self.obj = obj

    def set_obj(self, obj):
        self.obj = obj

    @property
    def obj(self):
        return self._obj

    @obj.setter
    def obj(self, obj):
        if self._obj == obj:
            return
        self._obj = obj
        self.update_widgets()

    def update_widgets(self):
        self.clear_widgets()
        self.create_widgets()

    def clear_widgets(self):

        # clear layouts
        while self._props_layout.rowCount() > 0:
            self._props_layout.removeRow(0)
        while self._objs_layout.count() > 0:
            item = self._objs_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

        self._prop_widgets = []
        self._obj_widgets = []

    def create_widgets(self):

        # add the new one
        if self._obj is not None:

            for prop in self._obj.properties.values():

                # don't show system properties
                if prop.is_hidden():
                    continue

                # create the wdget
                if self._obj.requires_sync() and not prop.is_required():
                    widget = QtWidgets.QLineEdit("???")
                    widget.setAlignment(QtCore.Qt.AlignCenter)
                    widget.setEnabled(False)
                elif prop.is_array():
                    widget = ArrayProperty(prop, self._factory)
                else:
                    widget = _create_widget(prop, self._factory, parent=self)

                if prop.is_object():
                    collapsible = Expander(title=prop.name, widget=widget)
                    self._obj_widgets.append(collapsible)
                    self._objs_layout.addWidget(collapsible)
                else:
                    self._prop_widgets.append(widget)
                    self._props_layout.addRow(prop.name, widget)


class ArrayProperty(QtWidgets.QWidget):
    """Array property"""

    def __init__(self, prop, factory, parent=None):
        super(ArrayProperty, self).__init__(parent=parent)

        buttons = QtWidgets.QWidget(parent=self)

        self._prop = prop
        self._factory = factory
        add = QtWidgets.QPushButton("+", parent=buttons)
        remove = QtWidgets.QPushButton("-", parent=buttons)
        add.setStyleSheet("text-align: center;")
        remove.setStyleSheet("text-align: center;")
        add.clicked.connect(self.add_element)
        remove.clicked.connect(self.remove_element)
        self._widgets_widget = QtWidgets.QWidget(parent=parent)
        self._widgets = QtWidgets.QFormLayout(self._widgets_widget)
        self._widgets.setContentsMargins(0, 0, 0, 0)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        button_layout = QtWidgets.QHBoxLayout(buttons)
        button_layout.setContentsMargins(0, 0, 0, 0)

        button_layout.addWidget(add)
        button_layout.addWidget(remove)
        layout.addWidget(buttons)

        layout.addWidget(self._widgets_widget)

        self.setLayout(layout)
        if len(self._prop.value) > 0:
            for index in range(len(self._prop.value)):
                widget = _create_widget(self._prop, self._factory, index, parent=self)
                self._widgets.addRow(f"{index}:", widget)
        else:
            self._widgets_widget.setVisible(False)

    def set_element(self, index, value):
        self._prop.value[index] = value

    def add_element(self):
        value = None
        if self._prop.prop_type != PropertyType.OBJECT:
            value = self._prop.type_class()
        self._prop.value.append(value)
        widget = _create_widget(
            self._prop, self._factory, len(self._prop.value) - 1, parent=self
        )
        self._widgets.addRow(f"{len(self._prop.value)-1}:", widget)
        self._widgets_widget.setVisible(True)

    def remove_element(self):
        if len(self._prop.value) > 0:
            self._prop.value.pop()
            item = self._widgets.itemAt(self._widgets.count() - 1)
            self._widgets.removeRow(item.widget())
        if len(self._prop.value) == 0:
            self._widgets_widget.setVisible(False)
