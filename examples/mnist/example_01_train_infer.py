#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import argparse
import os
from pathlib import Path

import torch.nn as nn

import rmtc.core.track.entities.licenses.community as community_licenses
import rmtc.core.ops.artifacts.torch.models as torch_models
import rmtc.core.ops.artifacts.structured.datasets as structured_datasets
import rmtc.core.ops.train.torch.trainers as torch_trainers
import rmtc.core.ops.io.oiio.image as image_io
import rmtc.core.ops.io.torch.models as model_io
import rmtc.core.ops.io.filesystem.json as structured_io
import rmtc.core.ops.io.filesystem.folders as folder_io

import rmtc.ops.artifacts as artifacts
import rmtc.ops.assets as assets
import rmtc.ops.process as process
from rmtc.core.ops.scheduling.local import schedulers
from rmtc.core.ops.infer.simple import inferers
from rmtc.core.ops.process.torch.packagers.tensor import BatchedTorchTensor
from rmtc.track.entities import Party
from rmtc import System
from rmtc.system import Config, Version, DataType, URI, Device, FileURI


# Parse command line args
parser = argparse.ArgumentParser(
    description = "Run MNIST training and inference."
)
parser.add_argument(
    "--solution_path",
    help="Specify directory for the solution",
    default="./solution",
    required=True,
)
parser.add_argument(
    "--mnist_path",
    help="Specify directory containing MNIST EXR dataset",
    default="./data",
    required=True,
)
parser.add_argument(
    "--results_path",
    help="Specify directory to output results",
    default="./results",
    required=True,
)
args = parser.parse_args()


###############################################################################

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
        x = x.reshape(-1, 28 * 28 * 4)
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        return x

    def set_training(self, train=True):
        pass

def create_model(model_dir):
    mnist_model         = SimpleClassifierModel()
    model_path          = model_io.TorchPackage.package_model(
        model           = mnist_model, 
        package_name    = "MNIST",
        output_path     = Path(model_dir),
        externs         = ["__main__"],
        interns         = ["torch"],    
    )
    return model_path

###############################################################################

# Get the system
rmtc_sys            = System(
    config          = Config(name="demo"),
)

# Create Creative Commons license
cc_license          = rmtc_sys.get_create(
    community_licenses.OSS,
    name            = "Creative Commons Attribution-Share Alike 3.0", 
    version         = Version("3.0.0"),
    spdx            = "CC-BY-SA-3.0",
    uri             = URI("https://creativecommons.org/licenses/by-sa/3.0/"),
    parties         = [rmtc_sys.get_create(Party, "Creative Commons")],
)

# MNIST JSON Dataset
dataset             = rmtc_sys.create_dataset(
    structured_datasets.MappedAssets,
    name            = "MNIST Training Dataset",
    licenses        = [cc_license],
    columns         = ["image", "label"],
    uri             = FileURI(f"{args.mnist_path}/train/mnist_exr_dataset.json"),
    io              = structured_io.AssetValuesJSONFile(
        asset_type  = assets.Image,
        asset_io    = image_io.EXR()
    ),
)

# Export the model
model_dir           = "{}/mnist_model".format(os.getcwd())
model_path          = create_model(model_dir)

# Wrap model
model               = rmtc_sys.create_model(
    torch_models.TorchModel,
    name            = "MNIST Model",
    uri             = FileURI(model_path),
    io              = model_io.TorchPackage(     
        model_name  = "MNIST",
        package_name = "MNIST.pkl",
    ),    
    input_types      = [assets.Image],
    input_packager   = process.ProcessPackager(
        processors  = [
            process.ProcessStack(),    
        ],    
        packager    = BatchedTorchTensor(data_type=DataType.FLOAT32),
    ),
    output_types     = [assets.Values],
    output_packager  = BatchedTorchTensor(data_type=DataType.FLOAT32),
)

# publish - adds to DB and makes an asset_manager specific URI
rmtc_sys            .push()

# Solution
solution            = rmtc_sys.create_solution(
    name            = "Number Categorization",
    uri             = FileURI(args.solution_path),
    input_types     = [assets.Image],
    output_types    = [assets.Values],
    description     = "MNIST Solution",
)

# Run the training
run                 = rmtc_sys.train(
    solution        = solution,
    scheduler       = schedulers.LocalScheduler(rmtc_system=rmtc_sys),
    trainer         = torch_trainers.TorchRegression(
        lr          = 0.001, 
        batch_size  = 5,
        epochs      = 1,
        optimizer   = "adam",
        device     = Device.GPU,
    ),
    model           = model, 
    dataset         = dataset,
)
rmtc_sys            .push()

# we are going to run an inference session
session             = rmtc_sys.create_session()

# Get best run from solution
solution            = rmtc_sys.get_solutions("Number Categorization")[0]

# Run inference
inference           = rmtc_sys.infer(
    session         = session,
    solution        = solution,
        model       = run.model,
        weights     = run.result_weights,
    inputs          = rmtc_sys.create_dataset(
        artifacts.Dataset,
        columns     = ["image"],
        uri         = FileURI(f"{args.mnist_path}/test/exr"), 
        io          = folder_io.FolderIO(
            asset_type=assets.Image,
            asset_io=image_io.EXR(),
        )
    ),    
    outputs         = rmtc_sys.create_dataset(
        artifacts.Dataset,
        uri         = FileURI(args.results_path),
        columns     = ["label"],
        io          = folder_io.FolderIO(
            asset_type=assets.Values,
            asset_io=structured_io.ValuesJSONFile(),
        )
    ),    
    inferer         = inferers.BatchedInferer(),
    scheduler       = schedulers.LocalScheduler(rmtc_system=rmtc_sys),
)

# push
rmtc_sys            .push()

