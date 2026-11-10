# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import json
import math

from torch import nn

import rmtc.ops.artifacts as artifacts
import rmtc.ops.assets as assets
import rmtc.ops.process as process
import rmtc.core.ops.artifacts.torch.models as torch_models
import rmtc.core.ops.io.filesystem.folders as folder_io
import rmtc.core.ops.io.filesystem.json as structured_io
import rmtc.core.ops.io.torch.models as model_io
import rmtc.core.ops.train.torch.trainers as torch_trainers
from rmtc.core.ops.infer.simple import inferers

from rmtc.system import DataType, Device, FileURI
from rmtc.core.ops.process.torch.packagers.tensor import BatchedTorchTensor

from rmtc.ops.artifacts import Dataset
from rmtc.ops.scheduling import Status
from rmtc.test.core import MockTrainer, MockInferer
from rmtc.core.ops.scheduling.local.schedulers import LocalScheduler, WorkerScheduler

from abstract_rmtc_test import AbstractRMTCTest


class AdderModel(nn.Module):

    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(2, 1)

    def forward(self, x):
        return self.fc(x)

    def set_training(self, train=True):
        pass


class TestInferTrain(AbstractRMTCTest):

    def test_infer(self):

        # create mini setup
        rmtc_sys            = self.get_system()
        solution            = rmtc_sys.create_solution()
        model               = rmtc_sys.create_model()
        asset               = rmtc_sys.create_asset()
        inputs              = rmtc_sys.create_dataset(Dataset, assets=[asset]*10)
        outputs             = rmtc_sys.create_dataset()

        # register mock inferer (required for pushing to DB)
        inferer             = MockInferer()

        # run inference
        scheduler           = rmtc_sys.create_scheduler(LocalScheduler)
        inference           = rmtc_sys.infer(
            inferer         = inferer,
            solution        = solution,
            model           = model,
            inputs          = inputs,
            outputs         = outputs,
            scheduler       = scheduler,
        )
        self.assertTrue(inference.is_complete())
        self.assertTrue(inferer.ran)

    def test_train(self):

        # create mini setup
        rmtc_sys            = self.get_system()
        solution            = rmtc_sys.create_solution(uri=FileURI("/local1/tmp"))
        model               = rmtc_sys.create_model()
        asset               = rmtc_sys.create_asset()
        dataset             = rmtc_sys.create_dataset(Dataset, assets=[asset]*10)

        # register mock trainer (required for pushing to DB)
        trainer             = MockTrainer()

        # run train
        scheduler           = rmtc_sys.create_scheduler(LocalScheduler)
        run                 = rmtc_sys.train(
            trainer         = trainer,
            model           = model,
            solution        = solution,
            dataset         = dataset,
            scheduler       = scheduler,
        )
        self.assertTrue(run.is_complete())
        self.assertTrue(trainer.ran)

    def test_infer_worker(self):

        # create mini setup
        rmtc_sys            = self.get_system()
        solution            = rmtc_sys.create_solution()
        model               = rmtc_sys.create_model()
        inputs              = rmtc_sys.create_dataset(Dataset,)
        outputs             = rmtc_sys.create_dataset(Dataset)

        # register mock inferer (required for pushing to DB)
        inferer             = MockInferer()

        # run inference
        scheduler           = rmtc_sys.create_scheduler(WorkerScheduler)
        inference           = rmtc_sys.infer(
            inferer         = inferer,
            solution        = solution,
            model           = model,
            inputs          = inputs,
            outputs         = outputs,
            scheduler       = scheduler,
        )
        self.assertTrue(inference.is_complete())
        self.assertEqual(inference.status, Status.FINISHED)

    def test_train_adder(self):
        """
        Run a full CPU based train & infer pass on a micro model
        """

        # create system
        rmtc_sys            = self.get_system()

        # package the model
        model_dir           = self.tmp_path / "model"
        model_path          = model_io.TorchPackage.package_model(
            model           = AdderModel(),
            package_name    = "Adder",
            output_path     = model_dir,
            externs         = [AdderModel.__module__],
            interns         = ["torch"],
        )

        # create the model
        model               = rmtc_sys.create_model(
            torch_models.TorchModel,
            name            = "Adder",
            uri             = FileURI(model_path),
            io              = model_io.TorchPackage(
                model_name  = "Adder",
                package_name = "Adder.pkl",
            ),
            input_types     = [assets.Values],
            input_packager  = process.ProcessPackager(
                processors  = [process.ProcessStack()],
                packager    = BatchedTorchTensor(data_type=DataType.FLOAT32),
            ),
            output_types    = [assets.Values],
            output_packager = process.ProcessPackager(
                processors  = [process.ProcessStack()],
                packager    = BatchedTorchTensor(data_type=DataType.FLOAT32),
            ),
        )

        # create the solution
        solution            = rmtc_sys.create_solution(
            name            = "Adder",
            uri             = FileURI(self.tmp_path / "solution"),
            input_types     = [assets.Values],
            output_types    = [assets.Values],
        )

        # push to DB
        rmtc_sys.push()

        # create training dataset
        dataset             = rmtc_sys.create_dataset(
            artifacts.Dataset,
            name            = "Sums",
            columns         = ["inputs", "output"],
        )
        for i in range(16):
            a, b = float(i), float(i % 4)
            dataset.add_row(
                [
                    rmtc_sys.create_asset(assets.Values, values=[a, b]),
                    rmtc_sys.create_asset(assets.Values, values=[a + b]),
                ]
            )
        self.assertEqual(len(dataset), 16)

        # run train
        trainer             = torch_trainers.TorchRegression(
            lr              = 0.01,
            batch_size      = 4,
            epochs          = 1,
            optimizer       = "adam",
            criterion       = "mse",
            device          = Device.CPU,
        )
        scheduler           = rmtc_sys.create_scheduler(LocalScheduler)
        run                 = rmtc_sys.train(
            trainer         = trainer,
            solution        = solution,
            model           = model,
            dataset         = dataset,
            scheduler       = scheduler,
        )

        # check the weights were built
        asset_manager = rmtc_sys.ops.asset_manager
        self.assertTrue(run.is_complete())
        self.assertIsNotNone(run.result_weights)
        weights_uri = asset_manager.resolve([run.result_weights.uri])
        self.assertTrue(asset_manager.exists(weights_uri))
        self.assertFalse(math.isnan(run.metric))

        # fetch the trained model from the DB using a fresh system
        rmtc_sys            = self.get_system()
        solution            = rmtc_sys.get_solutions("Adder")[0]
        model               = rmtc_sys.get_models("Adder")[0]
        best_run            = rmtc_sys.get_best_run(solution=solution)
        self.assertIsNotNone(best_run)
        weights             = best_run.result_weights
        self.assertIsNotNone(weights)

        # create inference inputs
        inputs_dir          = self.tmp_path / "inputs"
        inputs_dir.mkdir()
        for i in range(4):
            (inputs_dir / f"{i:04}.json").write_text(
                json.dumps({"0": float(i), "1": 1.0}), encoding="utf-8"
            )
        inputs              = rmtc_sys.create_dataset(
            artifacts.Dataset,
            name            = "InferInputs",
            columns         = ["inputs"],
            uri             = FileURI(inputs_dir),
            io              = folder_io.FolderIO(
                asset_type  = assets.Values,
                asset_io    = structured_io.ValuesJSONFile(),
            ),
        )

        # create inference outputs
        outputs             = rmtc_sys.create_dataset(
            artifacts.Dataset,
            name            = "InferOutputs",
            columns         = ["output"],
        )

        # run inference
        inferer             = inferers.DatasetInferer(device=Device.CPU)
        scheduler           = rmtc_sys.create_scheduler(LocalScheduler)
        inference           = rmtc_sys.infer(
            inferer         = inferer,
            solution        = solution,
            model           = model,
            weights         = weights,
            inputs          = inputs,
            outputs         = outputs,
            scheduler       = scheduler,
        )

        # check the inference completed
        self.assertTrue(inference.is_complete())
        self.assertEqual(inference.remaining, 0)
        self.assertEqual(len(inference.outputs), 4)
        for row in inference.outputs:
            value = row[0].tensors[0]
            self.assertEqual(value.shape, (1,))
            self.assertTrue(math.isfinite(float(value[0])))
