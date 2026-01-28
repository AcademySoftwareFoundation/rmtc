# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import glob
import json
import os
from pathlib import Path

import cv2
import numpy as np
import torch.nn as nn
import torchvision
import torchvision.datasets
import torchvision.transforms

import rmtc.artifacts as artifacts
import rmtc.process as process
import rmtc_core.artifacts.structured.datasets as structured_datasets
import rmtc_core.process.tensor.structure as structure_processors
import rmtc_core.artifacts.torch.models as torch_models
import rmtc_core.io.oiio.image as image_io
import rmtc_core.io.torch.models as model_io
import rmtc_core.infer.simple.inferers as inferers
import rmtc_core.track.licenses.community as community_licenses
import rmtc_core.train.local.schedulers as local_schedulers
import rmtc_core.train.torch.trainers as torch_trainers
import rmtc_core.io.filesystem.json as structured_io
import rmtc_core.artifacts.structured.datasets as structured_datasets
import rmtc_core.artifacts.filesystem.datasets as filesystem_datasets

from rmtc.system import URI, Context

from .abstract_rmtc_integration_test import AbstractRMTCIntegrationTest


def export_mnist_exrs(output_dir, train=True, data_dir="./data", max_count=None):
    """Save the MNIST dataset as EXR images and a corresponding json labels.

    Args:
        output_dir (str): Output directory path
        train (bool): If true, exports the training data, otherwise exports the test data
        data_dir (str): Directory containing downloaded MNIST data

    Returns:
        str: json filepath
    """
    # Load the MNIST dataset
    transform = torchvision.transforms.ToTensor()
    dataset = torchvision.datasets.MNIST(
        root=data_dir,
        train=train,
        download=True,
        transform=transform,
    )

    exr_output_dir = os.path.join(output_dir, "exr")
    if not os.path.exists(exr_output_dir):
        os.makedirs(exr_output_dir, exist_ok=True)

    export_data = []

    # Iterate through the dataset and save each image as EXR
    for i, (image_tensor, label) in enumerate(dataset):

        # early out
        if max_count is not None and i > max_count:
            break

        # Export PyTorch MNIST dataset as normalized floating point 3 channel 28x28 EXRs
        image_tensor = image_tensor.cpu()
        np_image = image_tensor.squeeze().numpy()
        np_image = np_image.astype(np.float32)
        np_image = np.squeeze(np_image)
        np_image = np.stack([np_image, np_image, np_image], axis=-1)

        # Export EXR - if not already
        output_path = os.path.join(
            exr_output_dir, "mnist_{:05d}_{}.exr".format(i, label)
        )
        if not os.path.exists(output_path):
            success = cv2.imwrite(output_path, np_image)
            if not success:
                raise RuntimeError(f"Could not create output file for {output_path}")

        rmtc_exr_uri = "file://localhost{}".format(os.path.abspath(output_path))

        # Convert label to integer logit tensor
        label_logits = [0.0] * 10
        label_logits[label] = 1.0
        export_data.append([rmtc_exr_uri, label_logits])

    # Save JSON file
    json_data = {}
    for exr_uri, label in export_data:
        json_data[exr_uri] = label
    json_file_path = os.path.join(output_dir, "mnist_exr_dataset.json")
    with open(json_file_path, "w") as json_file:
        json.dump(json_data, json_file, indent=4)

    return os.path.abspath(json_file_path)


def export_mnist_data(data_dir="./data", output_dir=""):
    """Export MNIST dataset.

    Args:
        data_dir (str): Directory containing downloaded MNIST data
        output_dir (str): Directory to export data to

    Returns:
        Tuple of str, str: JSON filepaths for the train, test data
    """
    train_path = os.path.join(output_dir, "mnist_exr/train")
    test_path = os.path.join(output_dir, "mnist_exr/test")

    # Export the 60,000 training images and labels
    train_json = export_mnist_exrs(
        train_path,
        train=True,
        data_dir=data_dir,
    )

    # Export the 10,000 testing images and labels
    test_json = export_mnist_exrs(
        test_path,
        train=False,
        data_dir=data_dir,
    )

    return train_json, test_json


def get_inferred_mnist_data(directory_path):
    """Generator that yields labels and predictions from inferred JSON files.

    Args:
        directory_path (str): Directory containing inferred JSON files

    Yields:
        list<Tuples(int, int)>: List of (label, prediction)
    """
    # Recursively get json files
    json_pattern = os.path.join(directory_path, "**", "*.json")
    json_files = glob.glob(json_pattern, recursive=True)

    for file_path in json_files:
        # The last digit in the file name is the label
        label = int(file_path.rsplit("_")[-1].split(".")[0])
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            logits = [0] * len(data.items())
            for key, value in data.items():
                logits[int(key)] = float(value)
            max_value = max(logits)
            max_index = int(logits.index(max_value))
            yield label, max_index


class SimpleClassifierModel(nn.Module):
    """Simple pytorch model for MNIST image classification"""

    def __init__(self):
        super(SimpleClassifierModel, self).__init__()
        # Input layer (flattened 28x28 4-channel images)
        self.fc1 = nn.Linear(28 * 28 * 4, 128)
        self.relu = nn.ReLU()
        # Output layer (Logits for digits 0-9)
        self.fc2 = nn.Linear(128, 10)

    def forward(self, x):
        # Flatten the image
        x = x.view(-1, 28 * 28 * 4)
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        return x

    def set_training(self, train=True):
        pass


class TestRefineModel(AbstractRMTCIntegrationTest):
    """Test model refinement using MNIST dataset"""

    def test_refine_model(self):
        """Test refining a model"""
        self.temp_dir = self.tmp_path
        directory_uri = f"file://localhost{self.temp_dir}"

        rmtc_sys = self.get_system()
        config = rmtc_sys.config

        # If specified in the config, use existing mnist data
        if "rmtc_testing" in config and "data_path" in config["rmtc_testing"]:
            mnist_data_dir = config["rmtc_testing"]["data_path"]
        else:
            mnist_data_dir = str(self.temp_dir / "data")

        # add mnist data path
        mnist_data_dir += "/mnist"

        rmtc_sys = self.get_system()

        # Create Creative Commons license
        cc_license = rmtc_sys.create_license(
            community_licenses.OSS,
            name="Creative Commons Attribution-Share Alike 3.0",
            uri=URI("https://creativecommons.org/licenses/by-sa/3.0/"),
            parties=["Creative Commons"],
        )

        # Export the MNIST dataset as EXRs and JSON labels
        train_json, test_json = export_mnist_data(
            data_dir=mnist_data_dir, output_dir=str(self.temp_dir)
        )

        # MNIST Dataset
        dataset = rmtc_sys.create_dataset(
            structured_datasets.MappedAssets,
            name="MNIST Training Dataset",
            licenses=[cc_license],
            uri=URI(f"file://localhost{train_json}"),
            io=structured_io.AssetValuesJSONFile(
                asset_type=artifacts.Image, asset_io=image_io.EXR()
            ),
        )

        # Export a basic MNIST model torch package
        mnist_model = SimpleClassifierModel()
        model_dir = self.temp_dir / "mnist_model"
        os.makedirs(model_dir, exist_ok=True)
        this_module_name = (
            f"integration.{os.path.splitext(os.path.basename(__file__))[0]}"
        )
        model_path = model_io.TorchPackage.package_model(
            model=mnist_model,
            package_name="MNIST",
            output_path=Path(model_dir),
            externs=[this_module_name],
        )

        # Wrap model
        model = rmtc_sys.create_model(
            torch_models.Torch,
            name="MNIST Model",
            uri=URI("file://localhost" + model_path),
            input_type=artifacts.Image,
            output_type=artifacts.Values,
            asset_to_input=process.ProcessStack(
                stack=[
                    structure_processors.Batch(),
                    structure_processors.Flatten(),
                ]
            ),
            asset_to_output=process.ProcessStack(
                stack=[
                    structure_processors.Batch(),
                    structure_processors.Flatten(),
                ]
            ),
            io=model_io.TorchPackage(
                model_name="MNIST",
                package_name="MNIST.pkl",
            ),
        )

        # Solution
        solution = rmtc_sys.create_solution(
            name="Number Categorisation",
            uri=URI(f"{directory_uri}/solution/test"),
            input_type=artifacts.Image,
            output_type=artifacts.Values,
            description="MNIST Solution",
        )

        rmtc_sys.push()

        # Run the training
        run = rmtc_sys.train(
            solution=solution,
            scheduler=local_schedulers.Simple(),
            trainer=torch_trainers.TorchRegression(
                lr=0.001,
                batch_size=5,
                epochs=1,
                optimizer="adam",
                context=Context.GPU,
            ),
            model=model,
            dataset=dataset,
        )
        rmtc_sys.push()

        # Basic DB validation
        mnist_dataset = rmtc_sys.get_datasets("MNIST")[0]
        self.assertEqual(mnist_dataset.name, "MNIST Training Dataset")
        rmtc_model = rmtc_sys.get_models("MNIST Model")[0]
        self.assertEqual(rmtc_model.name, "MNIST Model")

        # Generate inferences
        solution = rmtc_sys.get_solutions("Number Categorisation")[0]
        run = rmtc_sys.get_best_run(solution=solution)
        rmtc_sys.open().sync([run, run.model, run.result_weights])
        inference = rmtc_sys.infer(
            inferer=inferers.DatasetInferer(
                model=run.model,
                weights=run.result_weights,
                inputs=filesystem_datasets.Folder(
                    uri=URI(f"{directory_uri}/mnist_exr/test/exr"),
                    asset_type=artifacts.Image,
                    asset_io=image_io.EXR(),
                ),
                outputs=filesystem_datasets.Folder(
                    uri=URI(f"{directory_uri}/results"),
                    asset_io=structured_io.ValuesJSONFile(),
                ),
            ),
        )
        rmtc_sys.push()

        # Confirm we generated some inferences
        mnist_inferences = rmtc_sys.get_inferences(model=run.model)
        self.assertNotEqual(len(mnist_inferences), 0)

        # Validate predictions
        num_results = 0
        results_file = str(self.temp_dir / "results")
        correct = 0
        for label, prediction in get_inferred_mnist_data(results_file):
            num_results += 1
            if label == prediction:
                correct += 1
        self.assertTrue(num_results > 0)
        success_rate = correct / num_results * 100
        print(results_file)
        self.assertTrue(success_rate > 50.0)
