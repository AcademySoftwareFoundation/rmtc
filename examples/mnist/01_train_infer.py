#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import argparse
import os
from pathlib import Path

import torch.nn as nn

import rmtc.artifacts as artifacts
import rmtc.process as process
import rmtc_core.track.licenses.community as community_licenses
import rmtc_core.artifacts.torch.models as torch_models
import rmtc_core.process.tensor.structure as structure_processors
import rmtc_core.process.image.color as color_processors
import rmtc_core.process.image.channels as channels_processors
import rmtc_core.process.image.augment as augment_processors
import rmtc_core.train.local.schedulers as local_schedulers
import rmtc_core.train.torch.trainers as torch_trainers
import rmtc_core.io.oiio.image as image_io
import rmtc_core.io.torch.models as model_io
import rmtc_core.infer.simple.inferers as inferers
import rmtc_core.io.filesystem.json as structured_io
import rmtc_core.artifacts.structured.datasets as structured_datasets
import rmtc_core.artifacts.filesystem.datasets as filesystem_datasets
import rmtc_core.infer.filesystem.folders as folder_inferers

from rmtc.system import URI, Context
from rmtc_core import System
from rmtc.system import Config


# Parse command line args
parser = argparse.ArgumentParser(
    description = "Run MNIST training and inference."
)
parser.add_argument(
    "--store_name",
    help="Specify a store name",
    default="rmtc_examples",
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
        x = x.view(-1, 28 * 28 * 4)
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        return x

    def set_training(self, train=True):
        pass

def create_model(model_dir):
    mnist_model         = SimpleClassifierModel()
    os.makedirs(model_dir, exist_ok=True)
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
    config          = Config(
        overrides   = {
            "rmtc_store":{"name": args.store_name},
        },
    )
)

# Export the model
model_dir           = "{}/mnist_model".format(os.getcwd())
model_path          = create_model(model_dir)

# Create Creative Commons license
cc_license          = rmtc_sys.create_license(
    community_licenses.OSS,
    name            = "Creative Commons Attribution-Share Alike 3.0", 
    uri             = URI("https://creativecommons.org/licenses/by-sa/3.0/"),
    parties         = ["Creative Commons"],
)

# MNIST JSON Dataset
dataset             = rmtc_sys.create_dataset(structured_datasets.MappedAssets,
    name            = "MNIST Training Dataset",
    licenses        = [cc_license],    
    uri             = URI(scheme="file", host="localhost", path=f"{args.mnist_path}/train/mnist_exr_dataset.json"),
    io              = structured_io.AssetValuesJSONFile(
        asset_type  = artifacts.Image,
        asset_io    = image_io.EXR()
    ),
)

# Wrap model
model               = rmtc_sys.create_model(torch_models.Torch,
    name            = "MNIST Model",
    uri             = URI("file://localhost" + model_path),
    io              = model_io.TorchPackage(     
        model_name  = "MNIST",
        package_name = "MNIST.pkl",
    ),     
    input_type      = artifacts.Image,
    output_type     = artifacts.Values,
    asset_to_input = process.ProcessStack(
        stack=[
            structure_processors.Batch(),
            structure_processors.Flatten(),
        ]
    ),
    asset_to_output = process.ProcessStack(
        stack=[
            structure_processors.Batch(),
            structure_processors.Flatten(),
        ]
    ),
)

# publish - adds to DB and makes an asset_manager specific URI
rmtc_sys            .push()

# Solution
solution            = rmtc_sys.create_solution(
    name            = "Number Categorisation",
    uri             = URI(scheme="file", host="localhost", path=f"{args.solution_path}"),
    input_type      = artifacts.Image,
    output_type     = artifacts.Values,
    description     = "MNIST Solution",
)

# Run the training
run                 = rmtc_sys.train(
    solution        = solution,
    scheduler       = local_schedulers.Simple(),
    trainer         = torch_trainers.TorchRegression(
        lr          = 0.001, 
        batch_size  = 5,
        epochs      = 1,
        optimizer   = "adam",
        context     = Context.GPU,
    ),
    model           = model, 
    dataset         = dataset,
)
rmtc_sys            .push()

# Get best run from solution
solution            = rmtc_sys.get_solutions("Number Categorisation")[0]
run                 = rmtc_sys.get_best_run(solution=solution)

# Run inference
inference           = rmtc_sys.infer(
    # inferer         = folder_inferers.FolderInferer(
    #     input_uri   = URI(scheme="file", host="localhost", path=f"{args.mnist_path}/test/exr"), 
    #     output_uri  = URI(scheme="file", host="localhost", path=f"{args.results_path}"),
    #     input_io    = image_io.EXR(),
    #     output_io   = structured_io.ValuesJSONFile(),
    #     model       = run.model,
    #     weights     = run.result_weights,
    # )
    inferer         = inferers.DatasetInferer(
        model       = run.model,
        weights     = run.result_weights,
        inputs      = filesystem_datasets.Folder(
            uri     = URI(scheme="file", host="localhost", path=f"{args.mnist_path}/test/exr"),
            asset_type = artifacts.Image,
            asset_io = image_io.EXR(),
        ),
        outputs     = filesystem_datasets.Folder(
            uri     = URI(scheme="file", host="localhost", path=f"{args.results_path}"),
            asset_io = structured_io.ValuesJSONFile(),
        ),
    ),
)

# Push it
rmtc_sys            .push()
