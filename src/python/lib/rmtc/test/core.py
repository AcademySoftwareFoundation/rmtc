# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.track.entities import Model, Weights, Checkpoint
from rmtc.ops.artifacts import Dataset
from rmtc.ops.train import Trainer
from rmtc.ops.infer import Inferer


class MockTrainer(Trainer):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_property("ran", bool, False)

    def run(
        self,
        tracker,
        run,
        asset_manager,
        dataset_range,
    ) -> (float, [Model, Weights, Checkpoint]):
        self.ran = True
        return (0.0, [Model(), Weights(), Checkpoint()])


class MockInferer(Inferer):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_property("ran", bool, False)

    def run(
        self,
        inference,
        asset_manager,
        input_range,
    ) -> (float, [Dataset]):
        self.ran = True
        output = inference.inputs.duplicate()
        return (0.0, [output])
