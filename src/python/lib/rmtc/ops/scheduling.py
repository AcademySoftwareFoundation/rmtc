# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project
"""
Scheduler for infer & train
"""
import enum
from abc import ABC, abstractmethod

from rmtc.system import RMTCException, Datetime, URI
from rmtc.system.objects import Object


class Status(enum.IntEnum):
    """Enumeration for execution states."""

    INVALID = 0
    READY = 1
    RUNNING = 2
    PAUSED = 3
    STOPPED = 4
    FINISHED = 5
    FAILED = 6

    def __str__(self):
        return self.name.upper()


class Executor(ABC):
    """
    A executor runs a process across a range and produces a set of artifacts.
    It represents the functional system of the entire process.
    Job represents the factional task of the executor - produced by the scehduler
    from a task

    Inits in a source context
    Executes immutably in another - returns results
    Then updates with the results back in the original context
    """

    @abstractmethod
    def init(self, rmtc_system):
        """
        Setup in context
        """
        pass

    @abstractmethod
    def run(self, rmtc_system, job_range=None) -> (float, [Object]):
        """
        Execute a range of inputs tuple: (start,stop)
        Executes out of context - different process, thread, machine
        Returns back a 'metric' of the task and the resulting objects
        """
        pass

    @abstractmethod
    def update(self, rmtc_system, index, results):
        """
        Deal with interim results in context
        """
        pass


class Task(Executor, ABC):
    """
    This is used to unify training & inference tasks
    """

    @abstractmethod
    def get_remaining(self):
        """
        How many operations in this task left
        Jobs may execute a portion of the operations
        """
        pass

    @abstractmethod
    def get_status(self):
        pass

    @abstractmethod
    def get_duration(self):
        pass

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def resume(self):
        pass

    @abstractmethod
    def pause(self):
        pass

    @abstractmethod
    def finish(self):
        pass

    @abstractmethod
    def is_complete(self):
        pass

    @abstractmethod
    def is_inflight(self):
        pass


class Scheduler(Object, ABC):
    """
    Abstract base class for training and inference job scheduling.
    Schedulers spawn jobs which execute ranges on the task.
    The work with the DB but they are not stored in the DB themselves
    """

    def __init__(
        self,
        rmtc_system,
        task=None,
        job=None,
        job_size=None,
    ):
        """Initialize the Scheduler with job components."""
        super(Scheduler, self).__init__()
        self.add_property("job", Job, job)
        self.add_property("job_size", int, job_size)
        self.add_property("task", Task, task, member=False)
        self._sys = rmtc_system
        self._active_time = Datetime()
        if self._sys is None:
            raise RMTCException("No system")

    @property
    def rmtc_system(self):
        return self._sys

    def create_job(self, object_type, **kwargs):
        """Construct a new job."""
        job = object_type(**kwargs)
        job.scheduler = self
        self.job = job
        return job

    def __call__(self):
        self.start()

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
    def wait(self):
        """Wait for job completion."""
        pass


class Tracker(Object, ABC):
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
        self.add_property("uri", URI, value=uri)

    @abstractmethod
    def start(self, artifact):
        """Start tracking for the specified artifact."""
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


class LogTracker(Tracker):

    def __init__(self, log):
        self._log = log

    def start(self, artifact):
        self._log.info("Starting tracking")

    def finish(self):
        self._log.info("Finished tracking")

    def log_debug(self, message, step=None):
        if step is not None:
            message = f"Step {step}: {message}"
        self._log.debug(message)

    def log_info(self, message, step=None):
        if step is not None:
            message = f"Step {step}: {message}"
        self._log.info(message)

    def log_warning(self, message, step=None):
        if step is not None:
            message = f"Step {step}: {message}"
        self._log.warning(message)

    def log_error(self, message, step=None):
        if step is not None:
            message = f"Step {step}: {message}"
        self._log.error(message)

    def log_image(self, name, image, step=None):
        pass


class Job(Object, ABC):
    """
    Abstract base class for distributed jobs
    """

    def __init__(
        self,
        task,
        rmtc_system,
        job_id=None,
        job_range=None,
    ):
        """Initialize the Job with tracking and scheduling components."""
        super(Job, self).__init__()
        self.add_property("job_id", str, job_id)
        self.add_property("task", Task, task, member=False)
        self.add_property("job_range", [int], job_range)
        self._sys = rmtc_system
        if self._sys is None:
            raise RMTCException("No system")

    @property
    def rmtc_system(self):
        return self._sys

    @abstractmethod
    def get_results(self):
        pass

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
    def wait(self):
        """Wait until finished"""
        pass
