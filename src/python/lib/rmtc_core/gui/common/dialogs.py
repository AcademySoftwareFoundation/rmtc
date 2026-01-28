# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from Qt import QtWidgets, QtCore

from rmtc_core.gui.common import DIALOG_SIZE
from rmtc_core.gui.common.widgets import Publisher
from rmtc.system import URI, TypeName


class NewEntityDialog(QtWidgets.QDialog):

    def __init__(self, category, factory):

        super(NewEntityDialog, self).__init__()

        self._category = category
        self._type_class = None
        self._type_name = None
        self._factory = factory

        # populate with types
        type_names = factory.get_type_names(category)
        completer = QtWidgets.QCompleter([str(item) for item in type_names])
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        self._editor = QtWidgets.QLineEdit()
        self._editor.setCompleter(completer)
        self._editor.setPlaceholderText(f"Enter type of {category}")

        # buttons
        button_box = QtWidgets.QWidget()
        button_layout = QtWidgets.QHBoxLayout(button_box)
        ok_button = QtWidgets.QPushButton("OK")
        cancel_button = QtWidgets.QPushButton("Cancel")
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

        # populate com
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._editor)
        layout.addWidget(button_box)
        self.setLayout(layout)

    @property
    def type_name(self):
        return self._type_name

    @property
    def type_class(self):
        return self._type_class

    def accept(self):
        type_name = self._editor.text()
        type_class = self._factory.resolve(TypeName(string=type_name))
        if type_class is not None:
            self._type_name = type_name
            self._type_class = type_class
            super(NewEntityDialog, self).accept()
        else:
            QtWidgets.QMessageBox.warning(
                self, "Type Name Invalid", f"Factory could not resolve {type_name}"
            )


class LoginDialog(QtWidgets.QDialog):
    """
    Login dialog for database authentication.

    Currently unused as the system defers to the config file
    for login authentication.
    """

    def __init__(self, system):
        """Initialize the login dialog with system configuration."""
        super().__init__()
        self.setWindowTitle("Login")
        self.setMinimumSize(DIALOG_SIZE[0], DIALOG_SIZE[1])

        # inputs
        self._uri_label = QtWidgets.QLabel("URI:")
        self._uri_input = QtWidgets.QLineEdit(str(system.store.uri))
        self._user_label = QtWidgets.QLabel("Username:")
        self._user_input = QtWidgets.QLineEdit("postgres")
        self._password_label = QtWidgets.QLabel("Password:")
        self._password_input = QtWidgets.QLineEdit("postgres")
        self._password_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self._uri_label.setBuddy(self._uri_input)
        self._user_label.setBuddy(self._user_input)
        self._password_label.setBuddy(self._password_input)

        # buttons
        button_box = QtWidgets.QWidget()
        button_layout = QtWidgets.QHBoxLayout(button_box)
        self._login_button = QtWidgets.QPushButton("Login")
        self._cancel_button = QtWidgets.QPushButton("Cancel")
        button_layout.addWidget(self._login_button)
        button_layout.addWidget(self._cancel_button)
        self._login_button.clicked.connect(self.accept)
        self._cancel_button.clicked.connect(self.reject)

        # layout
        form = QtWidgets.QWidget()
        form_layout = QtWidgets.QFormLayout(form)
        form_layout.addRow("URI:", self._uri_input)
        form_layout.addRow("Username:", self._user_input)
        form_layout.addRow("Password:", self._password_input)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(form)
        layout.addWidget(button_box)
        self.setLayout(layout)

    @property
    def uri(self):
        """Get the entered URI as an RMTC URI object."""
        return URI(string=self._uri_input.text())

    @property
    def user(self):
        """Get the entered username."""
        return self._user_input.text()

    @property
    def password(self):
        """Get the entered password."""
        return self._password_input.text()


class PublisherDialog(QtWidgets.QDialog):
    """Publisher Dialog"""

    def __init__(self, system, entities=None, parent=None):
        super(PublisherDialog, self).__init__(parent=parent)
        self._system = system

        self.stacked_widget = QtWidgets.QStackedWidget(parent=self)

        # Publisher
        self.publisher = Publisher(self._system, entities=entities, parent=self)
        self.stacked_widget.addWidget(self.publisher)

        # Progress tab
        self.progress_tab = QtWidgets.QWidget(parent=self)
        progress_layout = QtWidgets.QVBoxLayout(self.progress_tab)
        progress_layout.addStretch()
        label = QtWidgets.QLabel("Publishing...")
        label.setAlignment(QtCore.Qt.AlignCenter)
        progress_layout.addWidget(label)
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 0)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addStretch()
        self.stacked_widget.addWidget(self.progress_tab)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.stacked_widget)
        layout.addStretch()

        self.stacked_widget.setCurrentIndex(0)

        # Create confirmation buttons
        self.buttonBox = QtWidgets.QDialogButtonBox(QtCore.Qt.Horizontal)
        self.buttonBox.addButton("Cancel", QtWidgets.QDialogButtonBox.RejectRole)
        self.buttonBox.addButton("Publish", QtWidgets.QDialogButtonBox.AcceptRole)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox)

        self.setLayout(layout)

        self.setWindowTitle("Publish")
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)

        self.resize(500, 600)

    def set_entities(self, entities):
        """Set the publishable entities"""
        self.publisher.set_entities(entities)

    def start_publish(self):
        self.stacked_widget.setCurrentIndex(1)

    def finish_publish(self):
        self.stacked_widget.setCurrentIndex(0)

    def accept(self):
        """When the user clicks accept, do the publish."""
        if self.publisher.validate():
            self.start_publish()
            self.publisher.publish()
            self.finish_publish()
            super(PublisherDialog, self).accept()
        else:
            QtWidgets.QMessageBox.warning(
                self,
                "Publish Error",
                "Invalid publish options. Please update the settings.",
                QtWidgets.QMessageBox.Ok,
            )
