# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
The basic System & DOM classes, these specify how all the sub components
come together.
"""

import datetime
import enum

import rmtc.system

from rmtc import track
from rmtc.system import RMTCException
from rmtc.ops import infer
from rmtc.ops import train
from rmtc.ops import scheduling
from rmtc.system import Broadcaster


class Operations:
    """
    This class provides the primary entry point for RMTC and abstracts some of the
    processes for training, inference and storage.

    It manages connections to data stores and provides methods for database operations
    on various entity types.

    The storage system has been abstracted, some elements like password & user may
    not be applicable for all classes of storage (e.g. a file)
    """

    def __init__(
        self,
        tracking,
        asset_manager,
        log,
        tracker=None,
        env_manager=None,
        pipelines=None,
    ):
        # quick check on critical subsystems
        if log is None:
            raise rmtc.system.RMTCException("Invalid log - can't init")
        if tracking is None:
            raise rmtc.system.RMTCException("Invalid tracking system - can't init")
        if asset_manager is None:
            raise rmtc.system.RMTCException("Invalid asset manager - can't init")

        # warn if optional submodules are missing
        if env_manager is None:
            log.warning("Invalid env manager")
        if tracker is None:
            log.warning("Invalid tracker")
        if pipelines is None:
            log.warning("Invalid pipelines")

        self._tracking = tracking
        self._asset_manager = asset_manager
        self._env_manager = env_manager
        self._tracker = tracker
        self._log = log
        self._broadcaster = Broadcaster()
        self._pipelines = {}
        if pipelines is not None:
            for pipeline in pipelines:
                self._pipelines[pipeline.name] = pipeline

    def is_valid(self):
        if self._tracking is None:
            return False
        if self._tracker is None:
            return False
        if self._asset_manager is None:
            return False
        if self._env_manager is None:
            return False
        if self._broadcaster is None:
            return False
        return True

    @property
    def log(self):
        return self._log

    @property
    def broadcaster(self):
        return self._broadcaster

    @property
    def tracker(self):
        return self._tracker

    @property
    def env_manager(self):
        return self._env_manager

    @property
    def pipelines(self):
        return self._pipelines

    @property
    def asset_manager(self):
        """Get the asset manager."""
        return self._asset_manager

    def setup(self, packages):
        """Set up the system environment."""
        if self._env_manager is not None:
            self._env_manager.add_packages(packages)

    def teardown(self, packages):
        """Tear down the system environment."""
        if self._env_manager is not None:
            self._env_manager.remove_packages(packages)

    def build(self, artifacts, name):

        # TODO: this needs to be a task to be scheduled

        # build legit list of things to publish
        to_build = []
        for artifact in artifacts:
            if artifact is None:
                self._log.warning(f"Invalid entity in build list {artifacts}")
                continue
            to_build.append(artifact)

        built_artifacts = []
        if name in self._pipelines:
            pipeline = self._pipelines[name]
            self._log.info(f"Running pipeline: {name}")
            built_artifacts = pipeline(
                asset_manager=self._asset_manager,
                artifacts=artifacts,
            )
            self._tracking.add_entities(built_artifacts)
            self._log.info(f"Built: {len(built_artifacts)}")

        return built_artifacts

    def infer(
        self,
        solution,  # where to get model from
        inputs,  # dataset to infer with
        outputs,  # dataset to store result
        inferer,  # how to infer
        scheduler,  # how to execute
        model=None,  # specific model to use
        weights=None,  # overriding weights, takes from run if None
    ):
        """
        Execute inference using the provided inferer.
        This also adds the inference to the object store.
        """

        # need to get a model
        if model is None:
            if solution is None:
                raise RMTCException("No model or solution specified for inference")
            run = self._tracking.get_best_run(solution=solution)
            if run is None:
                raise RMTCException(f"No runs found in solution {solution}")
            model = run.model
            if weights is None:
                weights = run.result_weights
        if model is None:
            raise RMTCException("No model defined")

        # TODO: early out and check signatures match

        # check if is_compliant
        artifacts = [model, weights, inputs, outputs]
        if not solution.is_compliant(artifacts):
            raise rmtc.system.RMTCException(f"Infer rights mismatch: {solution}")

        # create name
        name = "Inference " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # infer
        inference = self._tracking.create_inference(
            infer.Inference,
            name=name,
            model=model,
            inputs=inputs,
            outputs=outputs,
            weights=weights,
            inferer=inferer,
            solution=solution,
        )
        scheduler.task = inference
        scheduler.tracker = self.tracker
        scheduler.asset_manager = self.asset_manager
        scheduler.env_manager = self.env_manager

        # update now
        self._tracking.push()

        # TODO : make this work async
        scheduler()

        return inference

    def train(
        self,
        solution,
        trainer,
        model,
        dataset,
        scheduler=None,
        checkpoint=None,
    ):
        """
        Execute a training run, adds the run to the given solution and
        kicks off the training. The operation is blocking and waits until the
        scheduler has completed.
        """
        # check if is_compliant
        artifacts = [model, dataset, checkpoint]
        if not solution.is_compliant(artifacts):
            raise rmtc.system.RMTCException(
                f"Train right mismatch: {solution} vs {artifacts}"
            )

        run = self._tracking.create_run(
            train.Run,
            name="Run",
            model=model,
            dataset=dataset,
            checkpoint=checkpoint,
            trainer=trainer,
            solution=solution,
        )
        run.uri = self._asset_manager.create_uri(run, solution.uri)
        scheduler.tracker = self.tracker
        scheduler.task = run
        scheduler.asset_manager = self.asset_manager
        scheduler.env_manager = self.env_manager

        # update now
        self._tracking.push()

        # TODO : make this work async
        scheduler()

        # return
        return run

    def refine(
        self,
        run,
        dataset,
        scheduler=None,
    ):
        """
        This takes a run and trains on from its last checkpoint with the given
        dataset. The result is a new run.
        """

        # bad run
        if run is None:
            raise rmtc.system.RMTCException("Invalid run for refine")

        # check if is_compliant
        artifacts = [dataset]
        if not run.solution.is_compliant(artifacts):
            raise rmtc.system.RMTCException(
                f"Train right mismatch: {run.solution} vs {artifacts}"
            )

        # does the run have any checkpoints
        if len(run.result_checkpoints) == 0:
            raise rmtc.system.RMTCException(f"No checkpoints to refine from {run}")

        # setup
        new_run = self._tracking.create_run(
            train.Run,
            name="Run",
            model=run.model,
            dataset=dataset,
            checkpoint=run.result_checkpoints[-1],
            trainer=run.trainer,
            solution=run.solution,
        )
        new_run.uri = self._asset_manager.create_uri(new_run, run.solution.uri)
        scheduler.tracker = self.tracker
        scheduler.run = new_run
        scheduler.asset_manager = self.asset_manager
        scheduler.env_manager = self.env_manager

        # update now
        self._tracking.push()

        # TODO : make this work async
        scheduler()

        # return
        return new_run

    def purge(self, solution, category):
        # TODO: mechanism to delete unused artifacts in a solution
        # clear out weights that are not used for inferences
        # or checkpoints that are not used to retrain with

        # get entities in the given category that are derivatives of the solution
        # but has no derivatives itself
        # gather them and delete

        return False
