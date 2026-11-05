# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Inference systems and representations.
"""

import statistics
from abc import ABC, abstractmethod

import rmtc.system
import rmtc.track

from rmtc.track.entities import Dataset
from rmtc.track.store import Entity
from rmtc.system import Device, Datetime, RMTCException
from rmtc.system.objects import OUT, Immutable
from rmtc.ops.scheduling import Status, Task


class Inference(rmtc.track.entities.Inference, Task):
    """
    Simple wrapper for inferences within the infer module
    """

    def __init__(
        self,
        name=None,
        context=None,
        model=None,
        weights=None,
        inputs=None,
        outputs=None,
        metric=1.0,
        inferer=None,
        solution=None,
    ):
        super(Inference, self).__init__(
            name=name,
            context=context,
            model=model,
            weights=weights,
            inputs=inputs,
            outputs=outputs,
            metric=metric,
            solution=solution,
        )
        self.add_property(
            "inferer",
            Inferer,
            inferer,
            direction=OUT,
        )
        self.add_property("duration", float, 0.0, volatile=True)
        self.add_property("remaining", int, 0, volatile=True)
        self.add_property("started", Datetime, volatile=True)
        self.add_property("status", Status, Status.READY, volatile=True)
        self._start_time = None
        self._metrics = []

    def get_remaining(self):
        return self.remaining

    def get_status(self):
        return self.status

    def init(self, rmtc_system):
        """Initialize run state to default values."""

        self.status = Status.READY
        self.metric = 1.0
        self.duration = 0.0
        self._metrics = []

        # load in the dataset, gather size and then reset
        asset_manager = rmtc_system.ops.asset_manager
        asset_manager.read([self.inputs])
        self.remaining = len(self.inputs) if len(self.inputs) > 0 else 1
        asset_manager.reset([self.inputs])

    def run(self, rmtc_system, run_range=None):

        # checks
        if rmtc_system is None:
            raise RMTCException("No system")
        if run_range is None or len(run_range) != 2:
            run_range = (0, self.remaining)

        # run immutably
        metric, outputs = (0.0, None)
        with Immutable(self):
            metric, outputs = self.inferer.run(
                inference=self,
                asset_manager=rmtc_system.ops.asset_manager,
                input_range=run_range,
            )

        return (metric, outputs)

    def update(self, rmtc_system, index, results):
        """
        Merge in the results
        """
        # TODO : manage out of sequence
        metric = results[0]
        outputs = results[1][0]
        for row in outputs:
            row = self.outputs.fill_row(row)
        self.remaining = self.remaining - len(outputs)
        self._metrics.append(metric)

    def start(self):
        """Start the inferer if in READY state."""
        if self.status == Status.READY:
            self.started = Datetime()
            self.status = Status.RUNNING
            self._start_time = Datetime.now()

    def stop(self):
        """Stop a running or paused inference and update duration."""
        if self.status in (
            Status.RUNNING,
            Status.PAUSED,
        ):
            self.status = Status.STOPPED
            self.duration += (Datetime.now().timestamp() * 1000) - (
                self._start_time.timestamp() * 1000.0
            )

    def resume(self):
        """Resume paused inference."""
        if self.status == Status.PAUSED:
            self.status = Status.RUNNING
            self._start_time = Datetime.now()

    def pause(self):
        """Pause inference and update duration."""
        if self.status == Status.RUNNING:
            self.status = Status.PAUSED
            self.duration += (Datetime.now().timestamp() * 1000) - (
                self._start_time.timestamp() * 1000.0
            )

    def finish(self):
        """
        Complete the inference with outputs.
        """
        if self.status not in (
            Status.FAILED,
            Status.INVALID,
        ):
            self.status = Status.FINISHED
            self.duration += (Datetime.now().timestamp() * 1000) - (
                self._start_time.timestamp() * 1000.0
            )
            self.metric = statistics.mean(self._metrics)

    def is_complete(self):
        return self.status not in (
            Status.INVALID,
            Status.READY,
            Status.RUNNING,
            Status.PAUSED,
        )

    def is_inflight(self):
        return self.status in (Status.RUNNING, Status.PAUSED)

    def get_duration(self):
        return self.duration


class Inferer(Entity, ABC):
    """
    Abstract base class for model inference operations.

    The Inferer class provides a standardized interface for running inference
    on machine learning models with optional weights. It manages the lifecycle
    of model instances, handles asset loading and cleanup, and creates inference
    tracking records for provenance and metrics.

    The class follows a lazy loading pattern where the model instance is only
    created when needed during the first inference run. It supports both
    weighted and unweighted models, automatically loading weights when available.
    """

    def __init__(
        self,
        name=None,
        device=Device.GPU,
    ):
        """Initialize the Inferer with model and optional weights."""
        super(Inferer, self).__init__(name=name)

        # members
        self.add_property("device", Device, device)

        # internals
        self._model_instance = None
        self._model_weights = None

    def reset(self):
        """
        Reset the inferer state and clean up resources.

        Resets the internal model instance and clears cached data to free
        memory and prepare for fresh inference operations. This method should
        be called when the inferer is no longer needed or when switching
        between different inference sessions.
        """
        self._model_instance = None
        self._model_weights = None

    def get_model_instance(self, inference, asset_manager):
        if self._model_instance is None:
            self._model_instance = inference.model.duplicate(descendent=True)
            if self._model_instance is None:
                raise rmtc.system.RMTCException(f"Invalid model duplicate {self}")
            asset_manager.read([self._model_instance])
            if inference.weights is not None:
                self._model_weights = inference.weights.duplicate()
                asset_manager.read([self._model_weights])
                self._model_instance.load_weights(self._model_weights)
        if self._model_instance is None or not self._model_instance.is_valid():
            raise rmtc.system.RMTCException(f"Invalid model {self._model_instance}")
        self._model_instance.move(self.device)
        return self._model_instance

    def __call__(
        self,
        inference,
        asset_manager,
        input_range,
    ) -> (float, (Dataset,)):
        return self.run(inference, asset_manager, input_range)

    @abstractmethod
    def run(
        self,
        inference,
        asset_manager,
        input_range,
    ) -> (float, (Dataset,)):
        pass

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Inferer"
