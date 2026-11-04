#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.track import entities
import rmtc.ops.artifacts as artifacts
import rmtc.ops.assets as assets
import rmtc.ops.process as process

from rmtc import System
from rmtc.system import Config, URI, DataType, FileURI
from rmtc.core.ops.process.torch.packagers.tensor import BatchedTorchTensor
from rmtc.track.entities import Party

import rmtc.core.track.entities.licenses.community as community_licenses
import rmtc.core.track.entities.licenses.commercial as commercial_licenses
import rmtc.core.ops.artifacts.torch.models as torch_models
import rmtc.core.ops.process.image.color as color_processors
import rmtc.core.ops.process.image.transform as transform_processors
import rmtc.core.ops.process.image.channels as channel_processors
import rmtc.core.ops.io.torch.models as torch_models_io

import argparse
parser              = argparse.ArgumentParser(
    description     = "Image2Image RMTC Setup Example."
)
parser.add_argument("--model_path",
    help            = "PyTorch Image2Image Model Path",
    required        = True,
)
parser.add_argument("--model_name",
    help            = "PyTorch Model Name",
    required        = True,    
)
parser.add_argument("--model_class_name",
    help            = "PyTorch Model Class Name",
    required        = True,    
)
parser.add_argument("--model_package",
    help            = "PyTorch package pickle name",
    required        = True,    
)
parser.add_argument("--model_type",
    help            = "Model type",
    type            = lambda s: artifacts.ModelType[s.upper()],
    choices         = list(artifacts.ModelType),
    default         = artifacts.ModelType.REGRESSION,
)
parser.add_argument("--solution_name",
    help            = "Name of solution",
    required        = True,    
)
parser.add_argument("--solution_path",
    help            = "URI of solution",
    required        = True,    
)
args                = parser.parse_args()


###############################################################################

rmtc_sys            = System(
    config          = Config(name="demo"),   
)

oss_license         = rmtc_sys.get_create(
    community_licenses.OSS,
    name            = "Apache-2.0", 
    uri             = URI("https://apache.org/licenses/LICENSE-2.0.html"),
    parties         = [rmtc_sys.get_create(Party, "Mozilla Foundation")],
)

show_license         = rmtc_sys.get_create(
    commercial_licenses.Show,
    name            = "Show License", 
    parties         = [rmtc_sys.get_create(Party, "Production Company")],
)

foundation_model    = rmtc_sys.create_model(
    entities.Model,
    name            = "Foundation Image2Image Model",
    uri             = URI("https://huggingface.com/foundation_model"),
    author          = "Big Tech",
    licenses        = [oss_license],
)    

model               = rmtc_sys.create_model(
    torch_models.TorchModel,
    name            = args.model_name, 
    uri             = FileURI(args.model_path),
    ancestors       = [foundation_model],
    io              = torch_models_io.TorchPackage(
        model_name  = args.model_class_name,
        package_name = args.model_package,
    ),

    input_names     = ["Image"],
    input_types     = [assets.Image],
    input_packager  = process.ProcessPackager(
        processors  = [
            process.ProcessStack(
                stack=[
                    transform_processors.Resize(width=776, height=776),
                    color_processors.LinearToSRGB(),
                    color_processors.StatsNormalize(
                        mean=[0.485, 0.456, 0.406], 
                        std=[0.229, 0.224, 0.225],
                    ),
                    channel_processors.TrimAlpha(),
                    channel_processors.MoveChannelsFirst(),
                ]
            ),
        ],        
        packager = BatchedTorchTensor(data_type=DataType.FLOAT32),
    ),

    output_names    = ["Image"],
    output_types    = [assets.Image],
    output_packager = process.ProcessPackager(
        processors = [
            process.ProcessStack(
                stack=[
                    transform_processors.Resize(width=776, height=776),
                    channel_processors.ExtractChannel(),
                    channel_processors.MoveChannelsFirst(), 
                ]
            ),
        ],        
        packager = BatchedTorchTensor(data_type=DataType.FLOAT32),
    ),
)

solution            = rmtc_sys.create_solution(
    name            = args.solution_name,
    uri             = FileURI(args.solution_path),
    input_types     = [assets.Image],
    output_types    = [assets.Image],
)

rmtc_sys            .push()
