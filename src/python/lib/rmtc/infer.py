# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Inference systems and representations.
"""


from abc import ABC, abstractmethod

import rmtc.system
import rmtc.artifacts
import rmtc.track

from rmtc.artifacts import Weights, Collection
from rmtc.system import Context


class Inference(rmtc.track.Inference):
    """
    Simple wrapper for inferences within the infer module
    """

    pass


class Inferer(rmtc.objects.Object, ABC):
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
        asset_manager=None,
        env_manager=None,
        model=None,
        weights=None,
        batch_size=1000,
        env=None,
        context=Context.GPU,
        postprocess=None,
    ):
        """Initialize the Inferer with model and optional weights."""
        super(Inferer, self).__init__()
        self.add_property("model", rmtc.artifacts.Model, model, member=False)
        self.add_property(
            "weights",
            Weights,
            weights,
            member=False,
        )
        self.add_property("env", [rmtc.system.Package], env)
        self.add_property("batch_size", int, batch_size)
        self.add_property("context", Context, context)
        self.add_property(
            "postprocess", rmtc.process.Process, postprocess, direction=rmtc.objects.IN
        )
        self._model_instance = None
        self._asset_manager = asset_manager
        self._env_manager = env_manager

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

    def reset(self):
        """
        Reset the inferer state and clean up resources.

        Resets the internal model instance and clears cached data to free
        memory and prepare for fresh inference operations. This method should
        be called when the inferer is no longer needed or when switching
        between different inference sessions.
        """
        self._model_instance.reset()
        self._model_instance = None

    def _run_batch(self, batch):
        """Run the model against a batch of assets"""
        self.asset_manager.read(batch)
        assets = self._model_instance(batch)
        self.asset_manager.reset(batch)
        for src, dst in zip(batch, assets):
            dst.name = src.name
        return assets

    def run(self, inputs, outputs=None):
        """
        Execute inference on the provided assets.

        The input takes assets from row[0],
        the output populates assets in row[0].

        The inference is batched in rows, meaning no complete
        list of assets are kept in memory.
        """

        # TODO : manage the env
        self._env_manager.setup(self.env)

        # validate
        if inputs is None:
            raise rmtc.system.RMTCException("Invalid dataset on run")

        # if no output dataset then create a collection - simple list
        if outputs is None:
            outputs = Collection(
                name=f"Result:{self.model}-{self.weights}-{self.inputs}"
            )

        # read model
        if self._model_instance is None and self.model is not None:
            self._model_instance = self.model.duplicate()
            self._model_instance.move(self.context)
            self.asset_manager.read([self._model_instance])
        if self._model_instance is None or not self._model_instance.is_valid():
            raise rmtc.system.RMTCException(f"Invalid model {self._model_instance}")

        # weights
        if self.weights is not None:
            self.asset_manager.read([self.weights])
            self._model_instance.load_weights(self.weights)

        # input dataset - only the dataset, not the assets
        self.asset_manager.read([inputs])
        if inputs is None or not inputs.is_valid():
            raise rmtc.system.RMTCException(f"Invalid dataset {inputs}")

        # iterate through the dataset in batches
        input_assets = []
        for row in inputs:
            input_asset = row[0]
            input_asset.move(self.context)
            input_assets.append(input_asset)
            if len(input_assets) >= self.batch_size:
                output_assets = self._run_batch(input_assets)
                input_assets = []
                for output_asset in output_assets:
                    outputs.add_row([output_asset, None])

        # process any left
        if len(input_assets) > 0:

            # execute
            output_assets = self._run_batch(input_assets)

            # run a post process
            if self.postprocess is not None:
                for asset in output_assets:
                    asset.process(self.postprocess)

            # add to output
            for asset in output_assets:
                outputs.add_row([asset, None])

        # setup metric either from weights, or model
        metric = 1.0
        if self.weights is not None:
            metric = self.weights.metric
        else:
            metric = self.model.metric

        # create inference
        inference = Inference(
            model=self.model,
            weights=self.weights,
            metric=metric,
            inputs=inputs,
            result=outputs,
        )

        # cleanup
        inputs.reset()
        self.reset()

        return inference

    @abstractmethod
    def __call__(self):
        """
        Execute the inferer's specific inference logic.

        Abstract method that must be implemented by subclasses to define
        the specific inference behavior. This method is called by the
        framework to perform the actual inference operations.
        """
        return None
