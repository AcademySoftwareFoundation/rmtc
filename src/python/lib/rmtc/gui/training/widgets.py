# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
The Conductor GUI classes

NOTE: this is WIP and will likely be replaced/removed
"""

import re

from Qt import QtWidgets, QtCore, QtGui

from rmtc import System
from rmtc.gui.common.widgets import FilterComboBox
from rmtc.track import TrackingMessage
from rmtc.system.objects import Object
from rmtc.system import Device, TypeName
from rmtc.gui.common import get_icon_path


class Conductor(QtWidgets.QWidget):
    """
    Interface for browsing RMTC Solutions and kicking off training runs.
    """

    examine_request = QtCore.Signal(Object)

    def __init__(self, rmtc_system, parent=None):
        super(Conductor, self).__init__(parent=parent)

        self._system = rmtc_system
        self._solutions = set()
        self._threadpool = QtCore.QThreadPool()

        self._setup_ui()

        # Update the Solutions from broadcasted system updates
        self._system.track.broadcaster.add(
            TrackingMessage.ADDED,
            lambda data: self.add_entities(entities=data),
        )
        self._system.track.broadcaster.add(
            TrackingMessage.CLEARED,
            lambda data: self.clear(),
        )

    def _setup_ui(self):
        """Initialize the UI."""
        main_layout = QtWidgets.QVBoxLayout()

        self._search_widget = QtWidgets.QWidget(parent=self)
        search_layout = QtWidgets.QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        self._search_widget.setLayout(search_layout)
        self._search_widget.setMaximumHeight(25)

        # Search bar
        self._search_bar = QtWidgets.QLineEdit(parent=self)
        self._search_bar.setPlaceholderText("RMTC Solution Name")
        self._search_bar.returnPressed.connect(self.refresh)
        search_layout.addWidget(self._search_bar)

        # Search button
        self._search_button = QtWidgets.QPushButton("Search", parent=self)
        self._search_button.clicked.connect(self.refresh)
        search_icon = QtGui.QIcon.fromTheme("system-search")
        self._search_button.setIcon(search_icon)
        search_layout.addWidget(self._search_button)

        # Refresh button
        self._refresh_button = QtWidgets.QPushButton("Refresh", parent=self)
        self._refresh_button.clicked.connect(self.update_solutions)
        refresh_icon = QtGui.QIcon.fromTheme("view-refresh")
        self._refresh_button.setIcon(refresh_icon)
        search_layout.addWidget(self._refresh_button)

        main_layout.addWidget(self._search_widget)

        # Main list widget
        self._list_widget = QtWidgets.QListWidget(parent=self)
        self._list_widget.itemSelectionChanged.connect(self._solution_selected)
        main_layout.addWidget(self._list_widget)

        self.setLayout(main_layout)

    def update_solutions(self):
        """Update solution widgets"""
        for i in range(self._list_widget.count()):
            solution_item = self._list_widget.item(i)
            solution_widget = self._list_widget.itemWidget(solution_item)

            # Pull run updates from the RMTC system
            self._system.pull([solution_widget.solution])

            # Refresh the run widget
            solution_widget.refresh()

    def refresh(self):
        """Refresh the list of solutions."""
        solution_name = self._search_bar.text()

        for i in range(self._list_widget.count()):
            solution_item = self._list_widget.item(i)
            solution_widget = self._list_widget.itemWidget(solution_item)
            if re.search(solution_name, solution_widget.solution.name):
                solution_item.setHidden(False)
            else:
                solution_item.setHidden(True)

    def add_entities(self, entities=None):
        """Add entity if it is a solution"""
        for entity in entities:
            if entity.category() == "Solution" and entity not in self._solutions:
                self._add_solution(entity)

    def clear(self):
        """Clear the entries in the UI"""
        self._list_widget.clear()
        self._solutions = set()

    def _add_solution(self, solution):
        """Add solution to the list."""
        # Ensure solution is up to date
        self._system.pull([solution])

        solution_item = QtWidgets.QListWidgetItem(parent=self._list_widget)
        solution_widget = SolutionWidget(solution, self._system, parent=self)
        solution_item.setSizeHint(solution_widget.sizeHint())
        self._list_widget.addItem(solution_item)
        self._list_widget.setItemWidget(solution_item, solution_widget)
        self._solutions.add(solution)

    def _solution_selected(self, **_kwargs):
        """Updates when a solution is selected."""
        selected_items = self._list_widget.selectedItems()
        if selected_items:
            solution_widget = self._list_widget.itemWidget(selected_items[0])
            self.examine_request.emit([solution_widget.solution])


class CreateRunDialog(QtWidgets.QDialog):

    def __init__(self, solution, rmtc_system, parent=None):
        """
        Interface for submitting training runs for a solution.

        Args:
            solution (rmtc.track.entities.Solution): RMTC Solution
            rmtc_system (rmtc.System): RMTC System object
            parent (QtWidgets.QWidget): Parent widget
        """
        super(CreateRunDialog, self).__init__(parent=parent)
        self._run = None
        self._solution = solution
        self._system = rmtc_system

        self._setup_ui()

        self.setWindowTitle("Create Training Run")
        self.setWindowIcon(QtGui.QIcon(get_icon_path("rmtc")))
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setWindowModality(QtCore.Qt.NonModal)

        self.resize(600, 700)

    @property
    def solution(self):
        return self._solution

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout()

        # Solution
        solution_form_widget = QtWidgets.QGroupBox("Solution", parent=self)
        solution_form_layout = QtWidgets.QFormLayout(solution_form_widget)
        layout.addWidget(solution_form_widget)

        self._solution_label = QtWidgets.QLabel(self._solution.name, parent=self)
        solution_form_layout.addRow("Solution:", self._solution_label)

        # Dataset
        self._dataset_combo = FilterComboBox(parent=self)
        for dataset in self._system.get_datasets():
            dataset_date = dataset.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            dataset_display_name = f"{dataset.name} ({dataset_date})"
            self._dataset_combo.addItem(dataset_display_name, dataset)
        solution_form_layout.addRow("Dataset:", self._dataset_combo)

        self._model_combo = FilterComboBox(parent=self)
        for model in self._system.get_models():
            model_date = model.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            model_display_name = f"{model.name} ({model_date})"
            self._model_combo.addItem(model_display_name, model)
        solution_form_layout.addRow("Model:", self._model_combo)

        # Trainer
        trainer_form_widget = QtWidgets.QGroupBox("Model Trainer", parent=self)
        trainer_form_layout = QtWidgets.QFormLayout(trainer_form_widget)
        layout.addWidget(trainer_form_widget)

        # Trainer Options
        type_names = self._system.factory.get_type_names("Trainer")
        completer = QtWidgets.QCompleter([str(item) for item in type_names])
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        self._trainer_creator = QtWidgets.QLineEdit(parent=self)
        self._trainer_creator.setCompleter(completer)
        self._trainer_creator.setPlaceholderText("Enter type of Trainer")
        self._trainer_creator.returnPressed.connect(self.change_object)
        trainer_form_layout.addRow("Trainer: ", self._trainer_creator)

        type_names = self._system.factory.get_type_names("Scheduler")
        completer = QtWidgets.QCompleter([str(item) for item in type_names])
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        self._scheduler_creator = QtWidgets.QLineEdit(parent=self)
        self._scheduler_creator.setCompleter(completer)
        self._scheduler_creator.setPlaceholderText("Enter type of Scheduler")
        self._scheduler_creator.returnPressed.connect(self.change_object)
        trainer_form_layout.addRow("Scheduler: ", self._scheduler_creator)

        self._option_epochs = QtWidgets.QSpinBox(parent=self)
        self._option_epochs.setValue(5)
        self._option_epochs.setRange(1, 1000)
        trainer_form_layout.addRow("Epochs:", self._option_epochs)

        self._option_batch = QtWidgets.QSpinBox(parent=self)
        self._option_batch.setValue(5)
        self._option_batch.setRange(1, 1000)
        trainer_form_layout.addRow("Batch Size:", self._option_batch)

        self._accum_steps = QtWidgets.QSpinBox(parent=self)
        self._accum_steps.setValue(1)
        self._accum_steps.setRange(1, 1000)
        trainer_form_layout.addRow("Gradient Accumulation Steps:", self._accum_steps)

        self._repeat = QtWidgets.QSpinBox(parent=self)
        self._repeat.setValue(0)
        self._repeat.setRange(0, 1000)
        trainer_form_layout.addRow("Repeat:", self._repeat)

        self._option_optimizer = QtWidgets.QComboBox(parent=self)
        optimizers = ["adam", "adadelta", "rmsprop", "sgd"]
        self._option_optimizer.addItems(optimizers)
        trainer_form_layout.addRow("Optimizer:", self._option_optimizer)

        self._option_lr = QtWidgets.QDoubleSpinBox(parent=self)
        self._option_lr.setDecimals(4)
        self._option_lr.setValue(0.001)
        self._option_lr.setMinimum(0.0)
        self._option_lr.setMaximum(1.0)
        self._option_lr.setSingleStep(0.0001)
        trainer_form_layout.addRow("Learning Rate:", self._option_lr)

        self._augment_group = QtWidgets.QGroupBox(parent=self)
        self._augment_layout = QtWidgets.QVBoxLayout(self._augment_group)
        self._augment_layout.setContentsMargins(0, 0, 0, 0)
        trainer_form_layout.addRow("Data Augmentation:", self._augment_group)

        # Create confirmation buttons
        self._buttonBox = QtWidgets.QDialogButtonBox(QtCore.Qt.Horizontal)
        self._buttonBox.addButton("Cancel", QtWidgets.QDialogButtonBox.RejectRole)
        self._buttonBox.addButton(
            "Create Training Run", QtWidgets.QDialogButtonBox.AcceptRole
        )
        self._buttonBox.accepted.connect(self.accept)
        self._buttonBox.rejected.connect(self.reject)

        layout.addStretch()
        layout.addWidget(self._buttonBox)

        self.setLayout(layout)

    def accept(self):
        """When the user clicks accept, create and submit the training run."""
        scheduler = self._factory.create(TypeName(self._scheduler_creator.text()))

        trainer = self._factory.create(
            TypeName(self._trainer_creator.text()),
            lr=self._option_lr.value(),
            batch_size=self._option_batch.value(),
            epochs=self._option_epochs.value(),
            optimizer=self._option_optimizer.currentText(),
            device=Device.GPU,
            repetitions=self._repeat.value(),
            accumulation_steps=self._accum_steps.value(),
            pre_process=self._augment_widget.get_process(),
            random_seed=self._augment_widget.get_random_seed(),
        )

        model = self._model_combo.itemData(self._model_combo.currentIndex())
        dataset = self._dataset_combo.itemData(self._dataset_combo.currentIndex())

        # Execute the local scheduler in another thread
        self._run = self._system.train(
            solution=self._solution,
            scheduler=scheduler,
            trainer=trainer,
            model=model,
            dataset=dataset,
        )

        super(CreateRunDialog, self).accept()


class SolutionWidget(QtWidgets.QWidget):

    def __init__(self, solution, rmtc_system, parent=None):
        """
        Custom Solution widget to be used as an item in a list.

        Args:
            solution (rmtc.track.entities.Solution): RMTC Solution
            rmtc_system (rmtc.System): RMTC System object
            parent (QtWidgets.QWidget): Parent widget
        """
        super(SolutionWidget, self).__init__(parent=parent)
        self._solution = solution
        self._system = rmtc_system
        self._dialog = None
        self._parent = parent

        self._setup_ui()

    @property
    def solution(self):
        return self._solution

    def _setup_ui(self):
        """Initialize the UI."""
        layout = QtWidgets.QGridLayout()

        # Solution info
        self._name_label = QtWidgets.QLabel(self._solution.name, parent=self)
        self._name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._name_label, 0, 0, 1, 1)
        self._date_label = QtWidgets.QLabel(
            self._solution.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            parent=self,
        )
        layout.addWidget(self._date_label, 1, 0, 1, 1)
        self._desc_label = QtWidgets.QLabel(self._solution.description, parent=self)
        layout.addWidget(self._desc_label, 2, 0, 1, 1)

        # Go button
        self._go_button = QtWidgets.QPushButton("Create Training Run", parent=self)
        self._go_button.setMaximumWidth(150)
        self._go_button.setMinimumHeight(20)
        self._go_button.clicked.connect(self._go)
        layout.addWidget(self._go_button, 0, 1, 1, 1)

        self.setLayout(layout)

    def refresh(self):
        """Update the solution information"""
        self._name_label.setText(self._solution.name)
        self._desc_label.setText(self._solution.description)
        self._date_label.setText(
            self._solution.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        )

    def _go(self):
        if not self._dialog:
            # Create dialog if one is not already open
            self._dialog = CreateRunDialog(self._solution, self._system, parent=self)
        mouse_pos = QtGui.QCursor.pos()
        self._dialog.move(mouse_pos)
        self._dialog.show()


class MainWindow(QtWidgets.QMainWindow):
    """Window for testing or standalone usage"""

    def __init__(self, rmtc_system):
        """Initialize the RMTC Explorer main window."""
        super(MainWindow, self).__init__()

        conductor = Conductor(rmtc_system, parent=self)

        self.setCentralWidget(conductor)

        pos = QtGui.QCursor.pos()
        self.setWindowTitle("RMTC Conductor")
        self.setWindowIcon(QtGui.QIcon(get_icon_path("rmtc")))
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setGeometry(QtCore.QRect(pos.x(), pos.y(), 650, 700))


if __name__ == "__main__":
    rmtc_sys = System()
    app = QtWidgets.QApplication([])
    ui = MainWindow(rmtc_sys)
    ui.show()
    app.exec_()
