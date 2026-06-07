# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Training classes, derivations from the tracking entities that
are trainable.
"""

from abc import ABC, abstractmethod

import rmtc.system
import rmtc.track
import rmtc.objects
import rmtc.process


class Solution(rmtc.track.Solution):
    """
    Training solution extending the base Solution class.

    A simple extension of the base Solution class for training-specific
    functionality. Currently provides no additional behavior beyond
    the base implementation.
    """

    pass


class Run(rmtc.track.Run):
    """
    Training run extending the base Run class.

    A simple extension of the base Run class for training-specific
    functionality. Currently provides no additional behavior beyond
    the base implementation.
    """

    pass


class Tracker(rmtc.objects.Object, ABC):
    """
    Abstract base class for training progress tracking.

    The Tracker class provides a standardized interface for logging and
    monitoring training progress including metrics, images, checkpoints,
    and hyperparameters. It manages the lifecycle of training runs and
    provides persistence through URI-based storage.

    This is different from the provenance tracking - but to provide
    feedback during the training process.
    """

    def __init__(self, uri=None):
        """Initialize the Tracker with optional URI."""
        super(Tracker, self).__init__()
        self.add_property("uri", rmtc.system.URI, value=uri)

    def __repr__(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__} - {self.uri}"

    @abstractmethod
    def start(self, run):
        """Start tracking for the specified run."""
        pass

    @abstractmethod
    def finish(self):
        """Finish the current tracking session."""
        pass

    @abstractmethod
    def log_debug(self, message, step=None):
        """Log a message."""
        pass

    @abstractmethod
    def log_info(self, message, step=None):
        """Log a message."""
        pass

    @abstractmethod
    def log_warning(self, message, step=None):
        """Log a message."""
        pass

    @abstractmethod
    def log_error(self, message, step=None):
        """Log a message."""
        pass

    @abstractmethod
    def log_image(self, name, image, step=None):
        """Log an image at the specified training step."""
        pass

    @abstractmethod
    def log_metric(self, name, metric, step=None):
        """Log a metric value at the specified training step."""
        pass

    @abstractmethod
    def log_checkpoint(self, checkpoint, step=None):
        """Log a model checkpoint at the specified training step."""
        pass

    @abstractmethod
    def log_hyperparameters(self, params, metric=0.0):
        """Log hyperparameters dict with associated metric."""
        pass


class Scheduler(rmtc.objects.Object, ABC):
    """
    Abstract base class for training job scheduling.

    The Scheduler class manages the execution lifecycle of training jobs
    including initialization, starting, pausing, resuming, and stopping.
    It coordinates between jobs, trackers, runs, and execution environments.
    """

    def __init__(
        self,
        tracker=None,
        run=None,
        job=None,
        asset_manager=None,
        env_manager=None,
    ):
        """Initialize the Scheduler with job components."""
        super(Scheduler, self).__init__()
        self.add_property("job", Job, job)
        self.add_property("tracker", Tracker, tracker, member=False)
        self.add_property("run", rmtc.track.Run, run, member=False)
        self._asset_manager = asset_manager
        self._env_manager = env_manager
        self._active_time = rmtc.system.Datetime()

    @property
    def asset_manager(self):
        return self._asset_manager

    @property
    def env_manager(self):
        return self._env_manager

    @asset_manager.setter
    def asset_manager(self, value):
        self._asset_manager = value

    @env_manager.setter
    def env_manager(self, value):
        self._env_manager = value

    def create_job(self, object_type, **kwargs):
        """Construct inference - note we don't store them on this weights object"""
        job = object_type(**kwargs)
        job.scheduler = self
        self.job = job
        return job

    def __call__(self):
        self.start()

    @abstractmethod
    def init(self):
        """Initialize the scheduler for job execution."""
        pass

    @abstractmethod
    def start(self):
        """Start the scheduled job execution."""
        pass

    @abstractmethod
    def resume(self):
        """Resume a paused job execution."""
        pass

    @abstractmethod
    def pause(self):
        """Pause the current job execution."""
        pass

    @abstractmethod
    def stop(self):
        """Stop the current job execution."""
        pass

    @abstractmethod
    def join(self):
        """Wait for job completion."""
        pass


class Job(rmtc.objects.Object, ABC):
    """
    Abstract base class for training jobs.

    The Job class represents a unit of training work that can be executed
    by a scheduler. It manages executors, tracks progress, and provides
    lifecycle control for training operations.
    """

    def __init__(
        self,
        tracker=None,
        run=None,
        job_id=None,
    ):
        """Initialize the Job with tracking and scheduling components."""
        super(Job, self).__init__()

        # references
        self.add_property("tracker", Tracker, tracker, member=False)
        self.add_property("run", rmtc.track.Run, run, member=False)

        # members
        self.add_property("job_id", str, job_id)

    @abstractmethod
    def start(self):
        """Start the job execution."""
        pass

    @abstractmethod
    def resume(self):
        """Resume a paused job execution."""
        pass

    @abstractmethod
    def pause(self):
        """Pause the current job execution."""
        pass

    @abstractmethod
    def stop(self):
        """Stop the current job execution."""
        pass

    @abstractmethod
    def add_executor(self, executor):
        """Add an executor to this job."""
        pass

    @abstractmethod
    def get_executors(self):
        """Get all executors associated with this job."""
        pass


class Executor(rmtc.objects.Object, ABC):
    """
    Abstract base class for training job executors.

    The Executor class defines the interface for components that perform
    the actual training work within a job. Executors are called with
    tracker and run context to perform training operations.
    """

    def __init__(
        self,
        job=None,
    ):
        """Initialize the Executor with job reference."""
        super(Executor, self).__init__()
        self.add_property("job", Job, job)

    @abstractmethod
    def __call__(self, tracker, run):
        """Execute training operations."""
        pass


class Trainer(rmtc.track.Trainer, ABC):
    """
    Abstract base class for model training implementations.

    The Trainer class extends the base Trainer with training-specific
    functionality including hyperparameter management and checkpoint
    scheduling. It provides the core interface for training operations.
    """

    def __init__(
        self,
        name=None,
        epochs=1,
        batch_size=1,
        checkpoint_interval=0,
        context=None,
        preprocess=None,
    ):
        """Initialize the Trainer with training parameters."""
        super(Trainer, self).__init__(
            name=name,
            epochs=epochs,
            batch_size=batch_size,
            checkpoint_interval=checkpoint_interval,
        )
        self.add_property("context", rmtc.system.Context, context)
        self.add_property(
            "preprocess", rmtc.process.Process, preprocess, direction=rmtc.objects.IN
        )

    @property
    def hyperparameters(self):
        """Get all trainer properties as hyperparameters dictionary."""
        params = {}
        for prop in self.properties:
            params[prop.name] = prop.value
        return params

    @abstractmethod
    def __call__(self, tracker, run, asset_manager, env_manager, collector=None):
        """Execute the training process."""
        pass

    def do_checkpoint(self, epoch):
        """
        Determine if a checkpoint should be created at the given epoch.
        This references the trainer checkpoint interval. An interval of 0 always
        creates a checkpoint
        """
        if epoch == self.epochs:
            return True
        return epoch % self.checkpoint_interval == 0
