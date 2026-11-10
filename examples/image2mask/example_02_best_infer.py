#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.system import URI, FileURI
from rmtc import System
from rmtc.system import Config
from rmtc.ops import artifacts
from rmtc.ops import assets
from rmtc.core.ops.infer.simple import inferers 
from rmtc.core.ops.scheduling.local import schedulers

import rmtc.core.ops.io.oiio.image as image_io
import rmtc.core.ops.io.filesystem.folders as folder_io

import argparse
parser              = argparse.ArgumentParser(
    description     = "Image2Image RMTC Infer Example."
)
parser.add_argument("--inputs_path",
    help            = "Path of input images",
    required        = True,    
)
parser.add_argument("--outputs_path",
    help            = "Path to write outputs",
    required        = True,    
)
parser.add_argument("--solution_name",
    help            = "Name of Image2Image solution",
    required        = True,    
)
args                = parser.parse_args()


###############################################################################

rmtc_sys            = System(
    config          = Config(name="demo"),   
)

# create a session to hold this inference
session             = rmtc_sys.create_session(name="Demo Session")

# find solution
solution            = rmtc_sys.get_solutions(args.solution_name)[0]
run                 = rmtc_sys.get_best_run(solution=solution)

# run
inference           = rmtc_sys.infer(
    session         = session,
    solution        = solution,
    model           = run.model,
    weights         = run.result_weights,
    inputs          = artifacts.Dataset(
        uri         = FileURI(path=args.inputs_path), 
        columns     = ["Plate"],
        io          = folder_io.FolderIO(
            asset_type=assets.Image,
            asset_io=image_io.EXR(),
        )
    ),    
    outputs         = artifacts.Dataset(
        columns     = ["Mask"],
        uri         = FileURI(path=args.outputs_path),
        io          = folder_io.FolderIO(
            asset_type=assets.Image,
            asset_io=image_io.EXR(),
        )
    ),
    inferer         = inferers.DatasetInferer(),
    scheduler       = schedulers.LocalScheduler(rmtc_system=rmtc_sys),
)

# we ran the inference - write it out
rmtc_sys.write([inference.outputs])

# close the session
rmtc_sys            .push()
