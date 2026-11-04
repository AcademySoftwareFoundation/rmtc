#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc import System
from rmtc.system import Config, Device, FileURI
from rmtc.ops import artifacts, process, assets
from rmtc.core.ops.process.image import transform as transform_processors
from rmtc.core.ops.scheduling.local import schedulers
from rmtc.core.ops.train.torch import trainers as torch_trainers
from rmtc.core.ops.scheduling.torch.trackers import TensorBoard
from rmtc.core.ops.io.filesystem import folders as folder_io
from rmtc.core.ops.io.oiio import image as image_io

import argparse
parser              = argparse.ArgumentParser(
    description     = "Image2Image RMTC Train Example."
)
parser.add_argument("--model",
    help            = "Model Name",
    required        = True,    
)
parser.add_argument("--dataset_name",
    help            = "Name of dataset",
    required        = True,    
)
parser.add_argument("--dataset_path",
    help            = "Correlated folder of EXRs",
    required        = True,    
)
parser.add_argument("--solution_name",
    help            = "Name of solution",
    required        = True,    
)
parser.add_argument("--epochs",
    help            = "Epoch count",
    default         = 5,
)
parser.add_argument("--batch",
    help            = "Batch size",
    default         = 5,
)
parser.add_argument("--repeat",
    help            = "Repeat data samples",
    default         = 0,
)
parser.add_argument("--accumulation_steps",
    help            = "Accumulate gradient across batches to simulate larger batch size",
    default         = 1,
)
parser.add_argument("--tracker_path",
    help            = "Tracker URI",
)
parser.add_argument("--optimizer",
    help            = "Optimizer name",
    default         = "adam",
)
parser.add_argument("--lr",
    help            = "Learning Rate",
    default         = 0.006,
)
parser.add_argument("--rotation",
    help            = "Random rotation angle for data transformation",
    default         = 360.0,
)
args                = parser.parse_args()


###############################################################################

rmtc_sys            = System(
    config          = Config(name="demo"),
    tracker         = TensorBoard(uri=FileURI(args.tracker_path))
)
solution            = rmtc_sys.get_solutions(f"{args.solution_name}")[0]
model               = rmtc_sys.get_models(f"{args.model}")[0]
show_license        = rmtc_sys.get_licenses("Show License")[0]

dataset             = rmtc_sys.create_dataset(artifacts.Dataset,
    name            = args.dataset_name,
    columns         = ["plate", "mask"],
    uri             = FileURI(args.dataset_path),
    licenses        = [show_license],
    io              = folder_io.CorrelatedFolderIO(
        asset_type  = assets.Image,
        asset_io    = image_io.EXR(),
    )
)

run                 = rmtc_sys.train(
    solution        = solution,
    scheduler       = schedulers.LocalScheduler(rmtc_system=rmtc_sys),
    trainer         = torch_trainers.TorchRegression(
        lr          = args.lr, 
        batch_size  = args.batch,
        repetitions = args.repeat,
        accumulation_steps = args.accumulation_steps,
        epochs      = args.epochs,
        optimizer   = args.optimizer,
        device     = Device.GPU,
        pre_process  = [
            process.ProcessStack(
                stack=[
                    transform_processors.Flip(
                        probability=(0.1, 0.1),
                    ),
                    transform_processors.Rotate(
                        max_angle=args.rotation,
                        angle=None,
                    ),
                    transform_processors.Scale(
                        scale_min=(0.8, 0.8),
                        scale_max=(1.2, 1.2),
                    ),
                    transform_processors.Translate(
                        max_x=0.1,
                        max_y=0.1,
                    ),
                ]
            ),
        ],
        random_seed = 123456,
    ),
    model           = model, 
    dataset         = dataset,
)

rmtc_sys.push()