# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


from rmtc.scheduling import Job, Executor


class AWSJob(Job):
    """
    AWS batch processing job wrapper for distributed training.

    The AWSJob class provides integration with AWS batch processing services,
    specifically designed to work with AWS OpenJD (Open Job Description)
    for scalable, distributed training workloads on AWS infrastructure.
    """

    def __init__(
        self,
        tracker=None,
        run=None,
        job_id=None,
    ):
        """Initialize AWSJob with AWS-specific configuration."""
        super(AWSJob, self).__init__(
            tracker=tracker,
            run=run,
            job_id=job_id,
        )

    def start(self):
        """Start AWS job execution (placeholder implementation)."""
        pass

    def resume(self):
        """Resume paused AWS job (placeholder implementation)."""
        pass

    def pause(self):
        """Pause running AWS job (placeholder implementation)."""
        pass

    def stop(self):
        """Stop running AWS job (placeholder implementation)."""
        pass


class AWSExecutor(Executor):
    """
    Executor for task execution on AWS infrastructure.

    The AWSExecutor class provides an execution interface for running
    training tasks on AWS compute resources. It integrates with AWS
    services to enable distributed, scalable execution of ML workloads
    with proper resource management and monitoring.
    """

    def __init__(
        self,
        job=None,
    ):
        """Initialize AWSExecutor with AWS-specific configuration."""
        super(AWSExecutor, self).__init__(
            job=job,
        )

    def __call__(self):
        """Execute task on AWS infrastructure (placeholder implementation)."""
        pass
