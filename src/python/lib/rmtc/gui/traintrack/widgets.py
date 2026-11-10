# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
The TrainTrack GUI classes
"""

from Qt import QtWidgets, QtCore, QtGui

from rmtc.gui.common.dialogs import PublisherDialog
from rmtc.system.objects import Object
from rmtc.ops.scheduling import Status, Task


class TrainTrack(QtWidgets.QWidget):
    """
    User interface for tracking RMTC training tasks.
    """

    # 10 Seconds
    REFRESH_INTERVAL = 10000

    examine_request = QtCore.Signal(Object)

    def __init__(self, rmtc_system, parent=None):
        super(TrainTrack, self).__init__(parent=parent)

        self._system = rmtc_system

        # Timer for auto-refresh
        self._refresh_timer = QtCore.QTimer(parent=self)
        self._refresh_timer.setInterval(self.REFRESH_INTERVAL)
        self._refresh_timer.timeout.connect(self._auto_refresh)

        self._setup_ui()

    def _setup_ui(self):
        """Initialize the UI."""
        main_layout = QtWidgets.QVBoxLayout()

        self._toolbar_widget = QtWidgets.QWidget(parent=self)
        toolbar_layout = QtWidgets.QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self._toolbar_widget.setLayout(toolbar_layout)
        self._toolbar_widget.setMaximumHeight(25)

        # Search bar
        self._search_bar = QtWidgets.QLineEdit(parent=self)
        self._search_bar.setPlaceholderText("Task Name")
        self._search_bar.returnPressed.connect(self.populate)
        toolbar_layout.addWidget(self._search_bar)

        # Search button
        self._search_button = QtWidgets.QPushButton("Search", parent=self)
        self._search_button.clicked.connect(self.populate)
        search_icon = QtGui.QIcon.fromTheme("system-search")
        self._search_button.setIcon(search_icon)
        toolbar_layout.addWidget(self._search_button)

        # Refresh button
        self._refresh_button = QtWidgets.QPushButton("Refresh", parent=self)
        self._refresh_button.clicked.connect(self.refresh)
        refresh_icon = QtGui.QIcon.fromTheme("view-refresh")
        self._refresh_button.setIcon(refresh_icon)
        toolbar_layout.addWidget(self._refresh_button)

        # Options
        self._refresh_option = QtWidgets.QCheckBox("Refresh Automatically", parent=self)
        self._refresh_option.stateChanged.connect(self._toggle_auto_refresh)
        self._refresh_option.setChecked(False)
        toolbar_layout.addWidget(self._refresh_option)

        # Main list widget
        self._task_list_widget = QtWidgets.QListWidget(parent=self)
        self._task_list_widget.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection
        )
        self._task_list_widget.itemSelectionChanged.connect(self._on_task_selected)

        main_layout.addWidget(self._task_list_widget)
        main_layout.addWidget(self._toolbar_widget)

        self.setLayout(main_layout)

    def populate(self, all_tasks=True):
        """Populate the list of tasks.

        Args:
            all_tasks (bool): Re-populate all the tasks. If false, only adds new tasks.
        """
        if all_tasks:
            self.clear()

        tasks = []
        for i in range(self._task_list_widget.count()):
            task_item = self._task_list_widget.item(i)
            task_widget = self._task_list_widget.itemWidget(task_item)
            tasks.append(task_widget.task.obj_id)

        task_name = self._search_bar.text()
        for task in self._system.get_entities(
            name=task_name, categories=["Run", "Inference"]
        ):
            # TODO: add a filter for this
            if not isinstance(task, Task):
                continue
            if task.status in (Status.INVALID, Status.READY):
                continue
            if not all_tasks:
                if task.obj_id not in tasks:
                    self._add_task(task)
            else:
                self._add_task(task)

    def refresh(self):
        """Refresh the tasks and statuses."""
        for i in range(self._task_list_widget.count()):
            task_item = self._task_list_widget.item(i)
            task_widget = self._task_list_widget.itemWidget(task_item)

            # Pull task updates from the RMTC system
            self._system.pull([task_widget.task])

            # Refresh the task widget
            task_widget.refresh_status()

        # Update properties widget
        self._on_task_selected()

    def clear(self):
        """Clear all tasks"""
        self._task_list_widget.clear()

    def _auto_refresh(self):
        """Automatically refresh and reset the timer."""
        if self.isVisible():
            # Only do the refresh if the widget is currently shown
            self.populate(all_tasks=False)
            self.refresh()
        if self._refresh_option.isChecked():
            self._refresh_timer.start()

    def _add_task(self, task):
        """Add task to the list."""
        task_item = QtWidgets.QListWidgetItem(parent=self._task_list_widget)
        task_widget = TaskWidget(task, self._system, parent=self)
        task_item.setSizeHint(task_widget.sizeHint())
        self._task_list_widget.addItem(task_item)
        self._task_list_widget.setItemWidget(task_item, task_widget)

    def _on_task_selected(self, **_kwargs):
        """Updates when a task is selected."""
        selected_items = self._task_list_widget.selectedItems()
        if selected_items:
            task_widget = self._task_list_widget.itemWidget(selected_items[0])
            self.examine_request.emit([task_widget.task])

    def _toggle_auto_refresh(self, _state):
        """Toggle automatic refresh of the task list."""
        if self._refresh_option.isChecked():
            self._refresh_timer.start()
            self.populate()
        else:
            self._refresh_timer.stop()


class MetricLabel(QtWidgets.QLabel):

    def __init__(self, metric=None, parent=None):
        """
        Color coded label for displaying a model's metric during training.

        Args:
            metric (float): Training metric (loss)
            parent (QtWidgets.QWidget): Parent widget
        """
        super(MetricLabel, self).__init__(parent=parent)
        if metric is not None:
            self.set_metric(metric)

    def set_metric(self, metric):
        self.setText(f"Metric: {metric:.3f}")

        # Set the label color based on the metric value
        if metric >= 0.5:
            metric_color = QtGui.QColor(135, 19, 0)
        elif metric >= 0.2:
            metric_color = QtGui.QColor(195, 174, 45)
        else:
            metric_color = QtGui.QColor(230, 230, 230)

        style_sheet = f"color: {metric_color.name()};"
        self.setStyleSheet(style_sheet)


class TaskStatusWidget(QtWidgets.QWidget):

    STATUS_STYLESHEET = """
    QLabel {{
        font-weight: bold;
        background-color: {status_color};
        padding: 5px;
        border-radius: 5px; 
    }}"""

    STATUS_COLORS = {
        Status.INVALID: QtGui.QColor(66, 66, 66),
        Status.READY: QtGui.QColor(38, 98, 117),
        Status.RUNNING: QtGui.QColor(195, 174, 45),
        Status.PAUSED: QtGui.QColor(38, 98, 117),
        Status.STOPPED: QtGui.QColor(135, 19, 0),
        Status.FINISHED: QtGui.QColor(76, 115, 0),
        Status.FAILED: QtGui.QColor(135, 19, 0),
    }

    def __init__(self, status=0, parent=None):
        """
        Run widget to be used as an item in a list.
        """
        super(TaskStatusWidget, self).__init__(parent=parent)
        layout = QtWidgets.QVBoxLayout()
        self._color_label = QtWidgets.QLabel("STATUS", parent=self)
        self._color_label.setFixedWidth(100)
        self._color_label.setFixedHeight(40)
        self._color_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._color_label.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.MinimumExpanding
        )
        layout.addWidget(self._color_label)

        self.setLayout(layout)

        self.set_status(status)

    def set_status(self, status):
        """Set the RMTC task status"""
        status_text = Status(status).name
        self._color_label.setText(status_text)
        status_color = self.STATUS_COLORS[status]
        style_sheet = self.STATUS_STYLESHEET.format(status_color=status_color.name())
        self._color_label.setStyleSheet(style_sheet)


class TaskWidget(QtWidgets.QWidget):

    def __init__(self, task, rmtc_system, parent=None):
        """
        Run widget to be used as an item in a list.
        """
        super(TaskWidget, self).__init__(parent=parent)
        self._task = task
        self._system = rmtc_system
        self._dialog = None
        self._publishable = False

        self._setup_ui()
        self.refresh_status()

    @property
    def task(self):
        return self._task

    @property
    def publishable(self):
        return self._publishable

    def _setup_ui(self):
        """Initialize the UI."""
        layout = QtWidgets.QGridLayout()

        # Run info
        self._name_label = QtWidgets.QLabel(
            f"{self._task.name} ({self._task.category()})", parent=self
        )
        self._name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._name_label, 0, 0, 1, 1)

        self._status_label = TaskStatusWidget(status=self._task.status, parent=self)
        layout.addWidget(self._status_label, 0, 1, 4, 1)

        self._date_label = QtWidgets.QLabel(
            self._task.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            parent=self,
        )
        layout.addWidget(self._date_label, 1, 0, 1, 1)

        self._metric_label = MetricLabel(metric=self._task.metric, parent=self)
        self._metric_label.setMaximumWidth(200)
        self._metric_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self._metric_label, 0, 2, 2, 1)

        self._epoch_label = QtWidgets.QLabel("", parent=self)
        self._epoch_label.setMaximumWidth(200)
        self._epoch_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self._epoch_label, 1, 2, 2, 1)

        # Stop button
        self._stop_button = QtWidgets.QPushButton("Stop", parent=self)
        self._stop_button.setMaximumWidth(70)
        self._stop_button.setMinimumHeight(25)
        self._stop_button.clicked.connect(self._stop)
        self._stop_button.setToolTip(
            "Stop the task after the current epoch finishes and save a checkpoint."
        )
        layout.addWidget(self._stop_button, 0, 3, 4, 1)

        # Publish button
        self._publish_button = QtWidgets.QPushButton("Publish", parent=self)
        self._publish_button.setMaximumWidth(70)
        self._publish_button.setMinimumHeight(25)
        self._publish_button.clicked.connect(self._publish)
        self._publish_button.setToolTip("Publish the trained model weights.")
        layout.addWidget(self._publish_button, 0, 4, 4, 1)

        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 0)
        layout.setColumnStretch(2, 1)
        layout.setColumnStretch(3, 0)
        layout.setColumnStretch(4, 0)

        self.setLayout(layout)

    def set_publishable(self, publishable):
        """Make this task publishable."""
        self._publish_button.setEnabled(publishable)
        self._publishable = publishable

    def _publish(self):
        """Publish the trained model weights"""
        if not self._dialog:
            # Create dialog if one is not already open
            self._dialog = PublisherDialog(
                self._system,
                entities=self._get_entities_to_publish(),
                parent=self,
            )
        mouse_pos = QtGui.QCursor.pos()
        self._dialog.move(mouse_pos)
        self._dialog.show()

    def _get_entities_to_publish(self):
        """Get the entities to publish, once the task is complete"""
        publish_entities = []
        if not self._publishable:
            return publish_entities

        # Ensure task is up-to-date
        self._task.mark_for_sync()
        self._system.pull([self._task])

        # Add trained weights
        weights = self._task.result_weights
        if weights:
            self._system.pull([weights])
            publish_entities.append(weights)

        # Add model if it's not yet published
        model = self._task.model
        self._system.pull([model])
        if not self._system.ops.asset_manager.is_published([model]):
            publish_entities.append(model)
        else:
            self._system.log.info(f"Model already published: {model.uri}")

        # Add most recent checkpoint
        checkpoints = self._task.result_checkpoints
        if checkpoints:
            self._system.pull(checkpoints)
            publish_entities.append(checkpoints[-1])

        return publish_entities

    def _stop(self):
        """Stop the training task"""
        # Ensure status is up-to-date
        self.refresh_status()

        if self._task.status in (Status.READY, Status.RUNNING, Status.PAUSED):
            # If task hasn't already finished or failed, stop it
            self._task.status = Status.STOPPED
            self._system.push([self._task])
        self.refresh_status()

    def refresh_status(self):
        """Refresh the task UI."""
        # Mark for sync is required to pull up-to-date task properties
        self._task.mark_for_sync()
        self._system.pull([self._task])
        self._status_label.set_status(self._task.status)
        self._stop_button.setEnabled(self._task.is_inflight())
        self.set_publishable(self._task.status == Status.FINISHED)
        self._metric_label.set_metric(self._task.metric)
        if self._task.trainer is not None:
            self._epoch_label.setText(
                f"Epoch: {self._task.epoch}/{self._task.trainer.epochs}"
            )
        else:
            self._epoch_label.setText("Epoch: 1")
