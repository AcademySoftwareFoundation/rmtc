# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project
"""
Placeholder for shared scheduler between infer & train
"""

from abc import ABC, abstractmethod
import rmtc.objects


class Scheduler(rmtc.objects.Object, ABC):

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


class Tracker(rmtc.objects.Object, ABC):

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


class Executor(rmtc.objects.Object, ABC):

    @abstractmethod
    def __call__(self):
        """Execute the stored function with bound arguments."""
        pass
