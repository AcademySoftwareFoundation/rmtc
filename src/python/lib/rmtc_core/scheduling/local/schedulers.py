# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.scheduling import Scheduler


class ImmediateScheduler(Scheduler):

    def init(self):
        """Initialize the scheduler for job execution."""
        pass

    def start(self):
        """Start the scheduled job execution."""
        pass

    def resume(self):
        """Resume a paused job execution."""
        pass

    def pause(self):
        """Pause the current job execution."""
        pass

    def stop(self):
        """Stop the current job execution."""
        pass

    def join(self):
        """Wait for job completion."""
        pass
