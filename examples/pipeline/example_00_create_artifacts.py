#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import os

from rmtc.system import URI
import rmtc.ops.artifacts as artifacts
import rmtc.ops.assets as assets
import rmtc.ops.process as process
import rmtc.track

from rmtc import System
from rmtc.system import Config
from rmtc.system import DataType
from rmtc.core.ops.process.torch.packagers.tensor import BatchedTorchTensor

import rmtc.core.ops.process.image.transform as transform_processors
import rmtc.core.ops.artifacts.torch.models as torch_models
import rmtc.core.ops.artifacts.torch.weights as torch_weights
import rmtc.core.ops.process.image.color as color_processors
import rmtc.core.ops.process.image.channels as channel_processors
import rmtc.core.ops.io.torch.models as torch_model_io
import rmtc.core.ops.io.torch.weights as torch_weights_io

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
parser.add_argument("--solution_name",
    help            = "Name of solution",
    required        = True,    
    default         = "Test Solution",
)
args                = parser.parse_args()


###############################################################################

rmtc_sys            = System(
    config          = Config(name="demo"),   
)

# To enable flexibility processors are passed a single large input structure:
# - samples - corresponds to a single entry with all inputs or outputs for a model satisfied
#    - elements - a specific input or output
#       - tensors - a list of the actual tensors for the input or output element
# * Every process can index specifically into this structure
# * The structure can be entirely reorganised - but must retain this 3 deep nesting
# * Processors can each be provided an index into the structure, any none-specified indices
#   imply processing each instance for example if you specify element=0
#   all samples with element index 0 are processed
# * For models that support batching - these can be collapsed during processs
 
# For example a model that estimates depth from an image and a camera position
# has the following initial structure:
# [ #sample 1
#     [ # image input
#         [H,W,4] # single RBGA tensor
#     ]
#     [ # camera input
#         [P,3], # camera position
#         [V,3], # camera direction
#     ]
# ]
# [ #sample 2
#     [ # image input
#         [H,W,4] # single RBGA tensor
#     ]
#     [ # camera input
#         [P,3], # camera position
#         [V,3], # camera direction
#     ]
# ]

# If a processor is ran that reorders the image to channels first
# and batches you get something like:
# [ #batch
#     [ # image input
#         [2,4,H,W] # single RBGA tensor
#     ]
#     [ # camera input
#         [2,P,3], # camera position
#         [2,V,3], # camera direction
#     ]
# ]

# Once the model is ran, you get the returned structure:
# [ #batch
#     [ # image output
#         [1,1,H,W] #depth
#     ]
# ]

# Once the output processor that reorders channels and unbatches, you get:
# [ #sample 1
#     [ # image output
#         [H,W,1] #depth
#     ]
# ]

#############
 
# For example a model that estimates depth from an image and a camera position
# has the following initial structure:
#     [ # camera input
#         [P,3], # camera position tensor
#         [V,3], # camera direction tensor
#     ]

# packager takes in the entire package and converts to the model input
# a variant output

# RMTC data block looks like this:
# [ #sample 1
#     [ # image input
#         [H,W,4] # single RBGA tensor
#     ]
#     [ # camera input
#         [P,3], # camera position
#         [V,3], # camera direction
#     ]
# ]
# [ #sample 2
#     [ # image input
#         [H,W,4] # single RBGA tensor
#     ]
#     [ # camera input
#         [P,3], # camera position
#         [V,3], # camera direction
#     ]
# ]

# the packager converts it to the calling function format
# e.g. a batched single tensor, a dict, a list of lists or
# this is a compromise as models can use anything

# create model
model               = rmtc_sys.create_model(torch_models.TorchModel,
    name            = args.model_name, 
    uri             = URI(scheme="file", host="localhost", path=args.model_path),

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
    output_names    = ["Mask"],
    output_types    = [assets.Image],
    output_packager = process.ProcessPackager(
        processors = [
            process.ProcessStack(
                stack=[
                    channel_processors.ExtractChannel(),
                    channel_processors.MoveChannelsFirst(), 
                ]
            ),
        ],        
        packager = BatchedTorchTensor(data_type=DataType.FLOAT32),
    ),
    io              = torch_model_io.TorchPackage(
        model_name  = args.model_class_name,
        package_name = args.model_package,
    ),
)

# create a fake solution and run - link them up
solution            = rmtc_sys.create_solution(
    name            = args.solution_name,
    input_types     = [assets.Image],
    output_types    = [assets.Image],
)
run                 = rmtc_sys.create_run(
    solution        = solution,
    model           = model,
)
run.status          = rmtc.ops.scheduling.Status.FINISHED

# create weights
weights             = run.create_weights(
    torch_weights.TorchWeights,
    model           = model,
    uri             = URI(scheme="file", host="localhost", path=args.weights_path),
    io              = torch_weights_io.TorchWeightsFile(),
)
print(run.result_weights)

# push
rmtc_sys            .push()
