#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import os

from rmtc.system import URI
import rmtc.artifacts as artifacts
import rmtc.process as process
import rmtc.track

from rmtc_core import System
from rmtc.system import Config
import rmtc_core.artifacts.torch.models as torch_models
import rmtc_core.artifacts.torch.weights as torch_weights
import rmtc_core.process.tensor.structure as structure_processors
import rmtc_core.process.image.color as color_processors
import rmtc_core.process.image.channels as channel_processors
import rmtc_core.io.torch.models as torch_model_io
import rmtc_core.io.torch.weights as torch_weights_io

import argparse
parser              = argparse.ArgumentParser(
    description     = "Pipeline RMTC Setup Example."
)
parser.add_argument("--weights_path",
    help            = "PyTorch Image2Image Weights Path",
    required        = True,
    default         = f"{os.getcwd()}/weights/weights.pt",
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
    default         = artifacts.ModelType.CLASSIFICATION,
)
parser.add_argument("--store_name",
    help            = "Specify a store name",
    default         = "rmtc_examples",
)
parser.add_argument("--solution_name",
    help            = "Name of solution",
    required        = True,    
    default         = "Test Solution",
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

# create model
model               = rmtc_sys.create_model(torch_models.Torch,
    name            = args.model_name, 
    uri             = URI(scheme="file", host="localhost", path=args.model_path),
    input_type      = artifacts.Image,
    output_type     = artifacts.Image,
    input_shape     = [-1, 3, -1, -1], #RGB/BCHW
    output_shape    = [-1, 1, -1, -1], #A/BCHW
    asset_to_input  = process.ProcessStack(
        stack=[
            color_processors.StatsNormalize(
                mean=[0.485, 0.456, 0.406], 
                std=[0.229, 0.224, 0.225]
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
    io              = torch_model_io.TorchPackage(
        model_name  = args.model_class_name,
        package_name = args.model_package,
    ),     
)

# create weights
weights = rmtc_sys.create_weights(torch_weights.TorchWeights,
    uri=URI(scheme="file", host="localhost", path=args.weights_path),
    io=torch_weights_io.TorchWeightsFile(),
)

# create a fake solution and run - link them up
solution            = rmtc_sys.create_solution(
    name            = args.solution_name,
    input_type      = artifacts.Image,
    output_type     = artifacts.Image,
)
run                 = rmtc_sys.create_run(
    solution        = solution,
    model           = model,
    result_weights  = weights
)
run.status          = rmtc.track.RunStatus.FINISHED

# push
rmtc_sys            .push()
