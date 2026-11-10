# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


from rmtc.ops.scheduling import Job


class AWSJob(Job):
    """
    AWS batch processing job wrapper for distributed training.

    The AWSJob class provides integration with AWS batch processing services,
    specifically designed to work with AWS OpenJD (Open Job Description)
    for scalable, distributed training workloads on AWS infrastructure.
    """

    def __init__(
        self,
        task=None,
        job_id=None,
        job_range=None,
        rmtc_system=None,
    ):
        """Initialize AWSJob with AWS-specific configuration."""
        super(AWSJob, self).__init__(
            task=task,
            rmtc_system=rmtc_system,
            job_id=job_id,
            job_range=job_range,
        )

    def start(self):
        """Start AWS job execution (placeholder implementation)."""
        raise NotImplementedError()

    def resume(self):
        """Resume paused AWS job (placeholder implementation)."""
        raise NotImplementedError()

    def pause(self):
        """Pause running AWS job (placeholder implementation)."""
        raise NotImplementedError()

    def stop(self):
        """Stop running AWS job (placeholder implementation)."""
        raise NotImplementedError()
