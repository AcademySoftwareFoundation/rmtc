# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


from rmtc.train import Scheduler, Job, Executor


class Simple(Scheduler):
    """
    Local training scheduler for single-machine execution without distribution.

    The Local scheduler provides a simple execution strategy for training jobs
    that run on a single machine without any distributed computing capabilities.
    It executes training tasks sequentially using local resources and provides
    basic job lifecycle management.
    """

    def __init__(
        self,
        tracker=None,
        run=None,
        env_manager=None,
        asset_manager=None,
    ):
        """Initialize Local scheduler with tracker, run, and environment."""
        super(Simple, self).__init__(
            tracker=tracker,
            run=run,
            env_manager=env_manager,
            asset_manager=asset_manager,
        )

    def start(self):
        """Start the local training execution."""

        # Create a local job
        self.job = LocalJob(
            run=self.run,
            job_id="local",
        )

        # Add an executor for the trainer function
        executor = FunctionExecutor()
        executor.set_function(
            self.run.trainer,
            tracker=self.tracker,
            run=self.run,
            asset_manager=self.asset_manager,
            env_manager=self.env_manager,
        )
        self.job.add_executor(executor)

        # Start
        self.run.start()
        self.tracker.start(run=self.run)
        self.job.start()

        model, weights, metric, checkpoints = self.job.results[0]

        # finish
        self.tracker.finish()
        self.run.finish(
            model=model,
            weights=weights,
            metric=metric,
            checkpoints=checkpoints,
        )

    def init(self):
        """Initialize scheduler resources (no-op for local execution)."""
        pass

    def resume(self):
        """Resume paused training (no-op for local execution)."""
        pass

    def pause(self):
        """Pause running training (no-op for local execution)."""
        pass

    def stop(self):
        """Stop running training (no-op for local execution)."""
        pass

    def join(self):
        """Wait for training completion (no-op for local execution)."""
        pass


class LocalJob(Job):
    """
    Local job implementation for sequential task execution.

    The LocalJob class provides a concrete implementation of the Job interface
    for local execution environments. It manages a collection of executors
    and runs them sequentially on the local machine, collecting results
    for downstream processing.
    """

    def __init__(
        self,
        tracker=None,
        run=None,
        job_id=None,
    ):
        """Initialize LocalJob with empty executor and result collections."""
        super(LocalJob, self).__init__(
            tracker=tracker,
            run=run,
            job_id=job_id,
        )
        self._executors = []
        self._results = []

    @property
    def results(self):
        """Get the list of results from completed executors."""
        return self._results

    def start(self):
        """Execute all registered executors sequentially and collect results."""
        # self.env_manager.setup(self.env)
        # Execute tasks sequentially
        for executor in self._executors:
            result = executor()
            self._results.append(result)

    def add_executor(self, executor):
        """Add an executor to the job's execution queue.

        Args:
            executor (Executor): Executor to add to the job.
        """
        executor.job = self
        self._executors.append(executor)

    def get_executors(self):
        """Get the list of registered executors."""
        return self._executors

    def resume(self):
        """Resume paused job execution (no-op for local jobs)."""
        pass

    def pause(self):
        """Pause job execution (no-op for local jobs)."""
        pass

    def stop(self):
        """Stop job execution (no-op for local jobs)."""
        pass


class FunctionExecutor(Executor):
    """
    Executor for deferred function calls with argument binding.

    The FunctionExecutor class provides a simple mechanism for deferring
    function execution until explicitly called. It stores a function
    reference along with its arguments and keyword arguments, enabling
    flexible task scheduling and execution patterns.

    This executor is particularly useful for wrapping training functions
    or other callable objects that need to be executed as part of a
    job's execution pipeline.
    """

    def __init__(
        self,
        job=None,
    ):
        """Initialize FunctionExecutor with no function set."""
        super(FunctionExecutor, self).__init__(
            job=job,
        )
        self._func = None
        self._args = []
        self._kwargs = {}

    def __call__(self):
        """Execute the stored function with bound arguments."""
        if self._func is None:
            raise RuntimeError("Executor has no executable")
        return self._func(*self._args, **self._kwargs)

    def set_function(self, func, *args, **kwargs):
        """Set the function and arguments to execute."""
        self._func = func
        self._args = args
        self._kwargs = kwargs.copy()
