# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import itertools

from rmtc.ops.infer import Inferer
from rmtc.ops.artifacts import Dataset
from rmtc.ops.process import Process
from rmtc.system.objects import IN
from rmtc.system import Device, RMTCException


class DatasetInferer(Inferer):
    """
    Simple dataset to dataset inference
    """

    def __init__(
        self,
        device=Device.GPU,
    ):
        """Initialize DatasetInferer with model, paths, and file handlers."""
        super(DatasetInferer, self).__init__(
            device=device,
        )

    def run(
        self,
        inference,
        asset_manager,
        input_range,
    ) -> (float, (Dataset)):
        """
        Execute inference on the provided datasets
        """

        # validate
        if inference is None:
            raise RMTCException("Invalid inference on infer")
        inputs = inference.inputs
        outputs = inference.outputs.duplicate()

        if inputs is None:
            raise RMTCException("Invalid input dataset on infer")
        if outputs is None:
            raise RMTCException("Invalid output dataset on infer")

        # move to device ahead of read
        inputs.move(self.device)
        outputs.move(self.device)

        # read the datasets
        asset_manager.read([inputs])
        model = self.get_model_instance(inference, asset_manager)

        # iterate through the dataset in batches
        batch = []
        generator = Dataset.generate_rows([inputs])
        if input_range[1] > input_range[0]:
            generator = itertools.islice(generator, input_range[0], input_range[1])
        for row in generator:
            batch.append(row)

        # load inputs and process
        for row in batch:
            asset_manager.read(row)

        # run
        results = model(batch)

        # reset
        for row in batch:
            asset_manager.reset(row)

        # add to the outputs
        for row in results:
            row = outputs.fill_row(row)

        # setup metric either from weights, or model
        metric = 1.0
        if inference.weights is not None:
            metric = inference.weights.metric
        else:
            metric = inference.model.metric

        return (metric, [outputs])


class BatchedInferer(Inferer):
    """
    Simple dataset to dataset inference
    """

    def __init__(
        self,
        batch_size=1,
        device=Device.GPU,
        pre_process=None,
        post_process=None,
    ):
        """Initialize DatasetInferer with model, paths, and file handlers."""
        super(BatchedInferer, self).__init__(
            device=device,
        )
        self.add_property(
            "pre_process",
            [Process],
            pre_process,
            direction=IN,
        )
        self.add_property(
            "post_process",
            [Process],
            post_process,
            direction=IN,
        )
        self.add_property("batch_size", int, batch_size)

    def run(
        self,
        inference,
        asset_manager,
        input_range,
    ):
        """
        Execute inference on the provided datasets
        """

        # validate
        if inference is None:
            raise RMTCException("Invalid inference on infer")
        inputs = inference.inputs
        if inputs is None:
            raise RMTCException("Invalid input dataset on infer")

        # construct a new temporary output - this is written out by the
        # ranged scheduler
        outputs = inference.outputs.duplicate()

        # move to device ahead of read
        # TODO : race condition if dataset is being used in multiple places?
        inputs.move(self.device)
        outputs.move(self.device)

        # read the datasets - this doesn't load any asset tensors, just builds up the datasets
        # e.g. loads the CSV file list of other assets etc. puts the dataset into a state where
        # we can iterate
        asset_manager.read([inputs])
        if not inputs.is_valid():
            raise RMTCException(f"Invalid input {inputs}")
        model = self.get_model_instance(inference, asset_manager)

        # iterate through the dataset in batches
        batch = []
        generator = Dataset.generate_rows([inputs])
        if input_range[1] > input_range[0]:
            generator = itertools.islice(generator, input_range[0], input_range[1])
        for row in generator:

            # accumulate
            batch.append(row)

            # run when accumulated batch size
            if len(batch) >= self.batch_size:
                self._run_batch(batch, model, outputs, asset_manager)
                batch = []

        # run remainder batches
        if batch:
            self._run_batch(batch, model, outputs, asset_manager)

        # setup metric either from weights, or model
        metric = 1.0
        if inference.weights is not None:
            metric = inference.weights.metric
        else:
            metric = inference.model.metric

        return (metric, [outputs])

    def _run_batch(self, batch, model, outputs, asset_manager):
        # load inputs and process
        for row in batch:
            asset_manager.read(row)
            if self.pre_process:
                for asset, process in zip(row, self.pre_process):
                    asset.process(process)

        # run
        results = model(batch)

        # reset
        for row in batch:
            asset_manager.reset(row)

        # add to the outputs
        for row in results:
            if self.post_process:
                for asset, process in zip(row, self.post_process):
                    asset.process(process)
            row = outputs.fill_row(row)


class ParametricInferer(Inferer):
    """
    This inferer takes a dataset which is passed into the model as parameters
    """

    pass


class RecurrentInferer(Inferer):
    """
    This inferer uses the last inference result as a secondary input to the model
    """

    pass
