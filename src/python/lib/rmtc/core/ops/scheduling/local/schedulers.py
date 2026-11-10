# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import subprocess
import signal
import sys
import shutil
import tempfile
import json
from pathlib import Path

from rmtc.system import RMTCException
from rmtc.core.system.serializers.json import JSONSerializer
from rmtc.ops.scheduling import Job, Scheduler


class WorkerJob(Job):
    """
    Incomplete implementation to represent a subprocess worker
    Uses JSON to comms between processes
    This should not use the DB as a go between
    """

    # TODO: this is incomplete

    def __init__(
        self,
        task=None,
        job_id=None,
        job_range=None,
        rmtc_system=None,
    ):
        super(WorkerJob, self).__init__(
            task=task,
            rmtc_system=rmtc_system,
            job_id=job_id,
            job_range=job_range,
        )
        self._process = None
        self._results_file = None
        self._artifact_uri = None
        self._temp_folder = None
        self._results = None
        self._serializer = JSONSerializer(rmtc_system.factory, rmtc_system.objects)

    def get_results(self):

        # if cached
        if self._results is not None:
            return self._results

        # must finish first
        self.wait()
        if self._process.returncode != 0:
            raise RMTCException("Failed to complete process")

        # deserialise data
        data = json.loads(self._results_file.read_text())
        metric = data["metric"]
        artifacts = self._serializer.deserialize(json.dumps(data["artifacts"]))
        # HACK : deserialization clears the database flags, force the flags
        for artifact in artifacts:
            artifact.mark_for_create()
            artifact.mark_for_update()
        self.rmtc_system.ops.asset_manager.read(artifacts)
        self._results = (metric, artifacts)

        return self._results

    def start(self):

        # get the task
        if self.task is None:
            raise RMTCException("No task")

        # ensure an existing job is stopped
        if self._process is not None:
            raise RMTCException(f"Process underway for {self.task}")

        # build absolute path to neighbouring worker
        worker_path = Path(__file__).parent.joinpath("worker.py").resolve()

        # create temp locations to pass data
        # assets must be stored via the asset manager - not disk, as the IO
        # objects they have are asset manager specific
        asset_manager = self.rmtc_system.ops.asset_manager
        folder_name = f"task-{self.task.obj_id}-{self.job_id}"
        self._artifact_uri = asset_manager.create_transient_uri(name=folder_name)
        self._temp_folder = Path(tempfile.mkdtemp(folder_name))
        self._results_file = self._temp_folder / "results.json"

        # cache system names
        store_name = self.rmtc_system.track.store.name
        config_name = self.rmtc_system.config.name

        # start the subprocess and catch issues
        args = [
            sys.executable,
            worker_path,
            "--job_id",
            str(self.job_id),
            "--job_range",
            str(self.job_range),
            "--task_id",
            str(self.task.obj_id),
            "--config_name",
            str(config_name),
            "--store_name",
            str(store_name),
            "--artifact_uri",
            str(self._artifact_uri),
            "--results_file",
            str(self._results_file),
        ]
        try:
            self._process = subprocess.Popen(  # pylint: disable=consider-using-with
                args
            )
        except OSError as e:
            raise RMTCException(f"Error in worker spawn {e}") from e

    def wait(self):
        if self._process is not None:
            self._process.wait()

    def resume(self):
        if self._process is not None:
            self._process.send_signal(signal.SIGCONT)

    def pause(self):
        if self._process is not None:
            self._process.send_signal(signal.SIGSTOP)

    def stop(self):

        # clean up the process
        if self._process is not None:
            self._process.terminate()
            self._process.wait()
            self._process = None

        # remove all the temporary files
        if self._results_file is not None:
            self._results_file.unlink(missing_ok=True)
            self._results_file = None
        if self._artifact_uri is not None:
            self.rmtc_system.ops.asset_manager.delete_uri(self._artifact_uri)
            self._artifact_uri = None
        if self._temp_folder is not None:
            shutil.rmtree(self._temp_folder, ignore_errors=True)
        self._temp_folder = None


class WorkerScheduler(Scheduler):
    """
    Spawn a subprocess worker to run the task
    Requires pushing & pulling from DB
    """

    def __init__(
        self,
        task=None,
        rmtc_system=None,
    ):
        """Initialize Local scheduler with tracker, task, and environment."""
        super(WorkerScheduler, self).__init__(
            task=task,
            rmtc_system=rmtc_system,
        )

    def start(self):

        if self.rmtc_system is None:
            raise RMTCException("No system")

        # setup task
        self.task.init(self.rmtc_system)

        # work out job size
        total = self.task.get_remaining()
        size = total if self.job_size <= 0 else self.job_size

        # create all the jobs
        jobs = []
        for start in range(0, total, size):
            end = min(start + size, total)
            job = self.create_job(
                WorkerJob,
                job_id=f"{self.task.name}_{(len(jobs)+1):04}",
                job_range=(start, end),
                task=self.task,
                rmtc_system=self.rmtc_system,
            )
            jobs.append(job)

        # start the task
        self.task.start()

        # start in sequence
        for i, job in enumerate(jobs):
            job.start()
            try:
                self.task.update(
                    rmtc_system=self.rmtc_system, index=i, results=job.get_results()
                )
            finally:
                job.stop()

        # finish
        self.task.finish()

    def resume(self):
        self.job.resume()

    def pause(self):
        self.job.pause()

    def stop(self):
        self.job.stop()

    def wait(self):
        self.job.wait()


class LocalJob(Job):
    """
    Local job implementation that runs synchronously
    on the local machine
    """

    def __init__(
        self,
        task,
        rmtc_system,
        job_id=None,
        job_range=None,
    ):
        super(LocalJob, self).__init__(
            task=task,
            rmtc_system=rmtc_system,
            job_id=job_id,
            job_range=job_range,
        )
        self._results = None

    def get_results(self):
        return self._results

    def start(self):
        self._results = self.task.run(
            rmtc_system=self.rmtc_system,
            run_range=self.job_range,
        )

    def wait(self):
        """Local job is blocking anyway"""
        pass

    def resume(self):
        """Local job is blocking anyway"""
        pass

    def pause(self):
        """Local job is blocking anyway"""
        pass

    def stop(self):
        """Local job is blocking anyway"""
        pass


class LocalScheduler(Scheduler):
    """
    Local scheduler for single-machine execution without distribution.
    """

    def __init__(
        self,
        task=None,
        rmtc_system=None,
        job_size=None,
        flush=False,
    ):
        """Initialize Local scheduler with tracker, task, and environment."""
        super(LocalScheduler, self).__init__(
            task=task,
            rmtc_system=rmtc_system,
            job_size=job_size,
        )
        self.add_property("flush", bool, flush)

    def start(self):

        if self.rmtc_system is None:
            raise RMTCException("No system")

        # setup task
        self.task.init(self.rmtc_system)

        # work out job size
        total = self.task.get_remaining()
        size = total if self.job_size <= 0 else self.job_size

        # create all the jobs
        jobs = []
        for start in range(0, total, size):
            end = min(start + size, total)
            job = self.create_job(
                LocalJob,
                job_id=f"{self.task.name}_{(len(jobs)+1):04}",
                job_range=(start, end),
                task=self.task,
                rmtc_system=self.rmtc_system,
            )
            jobs.append(job)

        # start the task
        self.task.start()

        # start in sequence
        for i, job in enumerate(jobs):
            job.start()
            self.task.update(
                rmtc_system=self.rmtc_system, index=i, results=job.get_results()
            )
            if self.flush:
                self.rmtc_system.ops.asset_manager.flush(job.get_results()[1])

        # finish
        self.task.finish()

    def resume(self):
        raise NotImplementedError()

    def pause(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def wait(self):
        raise NotImplementedError()
