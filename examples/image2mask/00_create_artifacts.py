#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import os

from rmtc.system import URI
import rmtc.artifacts as artifacts
import rmtc.track as track
import rmtc.process as process

from rmtc_core import System
from rmtc.system import Config
import rmtc_core.track.licenses.community as community_licenses
import rmtc_core.track.licenses.commercial as commercial_licenses
import rmtc_core.artifacts.torch.models as torch_models
import rmtc_core.process.tensor.structure as structure_processors
import rmtc_core.process.image.color as color_processors
import rmtc_core.process.image.channels as channel_processors
import rmtc_core.io.torch.models as torch_models_io
import rmtc_core.io.oiio.image as image_io
import rmtc_core.io.filesystem.folders as folder_io

import argparse
parser              = argparse.ArgumentParser(
    description     = "Image2Image RMTC Setup Example."
)
parser.add_argument("--model_path",
    help            = "PyTorch Image2Image Model Path",
    required        = True,
    default         = f"{os.getcwd()}/models/model.pt",
)
parser.add_argument("--model_name",
    help            = "PyTorch Model Name",
    required        = True,    
    default         = "Test Model",
)
parser.add_argument("--model_class_name",
    help            = "PyTorch Model Class Name",
    required        = True,    
    default         = "Model",
)
parser.add_argument("--model_package",
    help            = "PyTorch package pickle name",
    required        = True,    
    default         = "model.pkl",
)
parser.add_argument("--model_type",
    help            = "Model type",
    type            = lambda s: artifacts.ModelType[s.upper()],
    choices         = list(artifacts.ModelType),
    default         = artifacts.ModelType.REGRESSION,
)
parser.add_argument("--dataset_path",
    help            = "Correlated folder of EXRs",
    required        = True,    
    default         = f"{os.getcwd()}/datasets/correlated_images",
)
parser.add_argument("--dataset_name",
    help            = "Name of dataset",
    required        = True,    
    default         = "Test Dataset",
)
parser.add_argument("--solution_path",
    help            = "File path for solution",
    required        = True,    
    default         = f"{os.getcwd()}/solution",
)
parser.add_argument("--solution_name",
    help            = "Name of solution",
    required        = True,    
    default         = "Test Solution",
)
parser.add_argument("--store_name",
    help            = "Specify a store name",
    default         = "rmtc_examples",
)
args                = parser.parse_args()


###############################################################################

rmtc_sys            = System(
    config          = Config(
        overrides   = {
            "rmtc_store":{"name": args.store_name},
        },
    )
)

oss_license         = rmtc_sys.create_license(
    community_licenses.OSS,
    name            = "Apache-2.0", 
    uri             = URI("https://apache.org/licenses/LICENSE-2.0.html"),
    parties         = ["Mozilla Foundation"],
)

show_license         = rmtc_sys.create_license(
    commercial_licenses.Show,
    name            = "Show License", 
    parties         = ["Production Company"],
)

foundation_model    = rmtc_sys.create_model(
    track.Model,
    name            = "Foundation Image2Image Model",
    uri             = URI("https://huggingface.com/foundation_model"),
    author          = "Big Tech",
    licenses        = [oss_license],
)    

model               = rmtc_sys.create_model(torch_models.Torch,
    name            = args.model_name, 
    uri             = URI(scheme="file", host="localhost", path=args.model_path),
    input_type      = artifacts.Image,
    output_type     = artifacts.Image,
    ancestors       = [foundation_model],
    io              = torch_models_io.TorchPackage(
        model_name  = args.model_class_name,
        package_name = args.model_package,
    ),
    input_shape     = [-1, 3, -1, -1], #RGB/BCHW
    output_shape    = [-1, 1, -1, -1], #R/BCHW
    asset_to_input  = process.ProcessStack(
        stack=[
            color_processors.LinearToSRGB(),
            color_processors.StatsNormalize(
                mean=[0.485, 0.456, 0.406], 
                std=[0.229, 0.224, 0.225],
            ),
            channel_processors.TrimAlpha(),
            channel_processors.MoveChannelsFirst(),
            structure_processors.Batch(),  
            structure_processors.Flatten(),
        ]
    ),    
    asset_to_output = process.ProcessStack(
        stack=[
            channel_processors.ExtractChannel(),
            channel_processors.MoveChannelsFirst(), 
            structure_processors.Batch(),
            structure_processors.Flatten(),
        ]
    ),
)

dataset             = rmtc_sys.create_dataset(artifacts.Repository,
    name            = args.dataset_name,
    uri             = URI(scheme="file", host="localhost", path=args.dataset_path),
    licenses        = [show_license],
    io              = folder_io.CorrelatedFolderIO(
        asset_type  = artifacts.Image,
        asset_io    = image_io.EXR(),
    )
)

solution            = rmtc_sys.create_solution(
    name            = args.solution_name,
    uri             = URI(scheme="file", host="localhost", path=args.solution_path),
    input_type      = artifacts.Image,
    output_type     = artifacts.Image,
)

rmtc_sys            .push()