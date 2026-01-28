#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.system import Context
from rmtc_core import System
from rmtc.system import Config
import rmtc.process as process
import rmtc_core.process.tensor.structure as structure_processors
import rmtc_core.process.image.color as color_processors
import rmtc_core.process.image.channels as channels_processors
import rmtc_core.process.image.augment as augment_processors
import rmtc_core.train.local.schedulers as local_schedulers
import rmtc_core.train.torch.trainers as torch_trainers

import argparse
parser              = argparse.ArgumentParser(
    description     = "Image2Image RMTC Train Example."
)
parser.add_argument("--model",
    help            = "Model Name",
    required        = True,    
    default         = "Test Model",
)
parser.add_argument("--dataset",
    help            = "Name of dataset",
    required        = True,    
    default         = "Test Dataset",
)
parser.add_argument("--solution",
    help            = "Name of solution",
    required        = True,    
    default         = "Test Solution",
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
parser.add_argument("--optimizer",
    help            = "Optimizer name",
    default         = "adam",
)
parser.add_argument("--lr",
    help            = "Learning Rate",
    default         = 0.006,
)
parser.add_argument("--rotation",
    help            = "Random rotation angle for data augmentation",
    default         = 360.0,
)
parser.add_argument("--store_name",
    help            = "Specify a store name",
    default         = "rmtc_examples",
)
args                = parser.parse_args()


###############################################################################

rmtc_sys            = System(
    config          = Config(overrides={"rmtc_store":{"name": args.store_name}}),
)
solution            = rmtc_sys.get_solutions(f"{args.solution}")[0]
model               = rmtc_sys.get_models(f"{args.model}")[0]
dataset             = rmtc_sys.get_datasets(f"{args.dataset}")[0]

print(f"Solution: {solution}")
print(f"Model: {model}")
print(f"Dataset: {dataset}")

run                 = rmtc_sys.train(
    solution        = solution,
    scheduler       = local_schedulers.Simple(),
    trainer         = torch_trainers.TorchRegression(
        lr          = args.lr, 
        batch_size  = args.batch,
        repeat_data = args.repeat,
        accumulation_steps = args.accumulation_steps,
        epochs      = args.epochs,
        optimizer   = args.optimizer,
        context     = Context.GPU,
        preprocess  = process.ProcessStack(
            stack=[
                augment_processors.Flip(
                    probability=(0.1, 0.1),
                ),
                augment_processors.Rotate(
                    max_angle=args.rotation,
                    angle=None,
                ),
                augment_processors.Scale(
                    scale_min=(0.8, 0.8),
                    scale_max=(1.2, 1.2),
                ),
                augment_processors.Translate(
                    max_x=0.1,
                    max_y=0.1,
                ),
            ]
        ),
        random_seed = 123456,
    ),
    model           = model, 
    dataset         = dataset,
)

rmtc_sys.push()