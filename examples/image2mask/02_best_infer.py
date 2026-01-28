#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import os

from rmtc.system import URI
from rmtc_core import System
from rmtc.system import Config
from rmtc.process import ProcessStack

import rmtc_core.infer.filesystem.folders as folder_inferers
import rmtc_core.io.oiio.image as image_io
import rmtc_core.process.image.color as color_processors

import argparse
parser              = argparse.ArgumentParser(
    description     = "Image2Image RMTC Infer Example."
)
parser.add_argument("--input_path",
    help            = "Path of input images",
    required        = True,    
    default         = f"{os.getcwd()}/datasets/infer_images",
)
parser.add_argument("--results_path",
    help            = "Path to write results",
    required        = True,    
    default         = f"{os.getcwd()}/results",
)
parser.add_argument("--solution",
    help            = "Name of Image2Image solution",
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
    config          = Config(overrides={"rmtc_store":{"name": args.store_name}}),
)

solution            = rmtc_sys.get_solutions(f"{args.solution}")[0]
run                 = rmtc_sys.get_best_run(solution=solution)
inference           = rmtc_sys.infer(
    inferer         = folder_inferers.FolderInferer(
        input_uri   = URI(scheme="file", host="localhost", path=args.input_path), 
        output_uri  = URI(scheme="file", host="localhost", path=args.results_path),
        input_io    = image_io.EXR(),
        output_io   = image_io.EXR(),
        model       = run.model,
        weights     = run.result_weights,
        postprocess = ProcessStack(
            stack   = [
                color_processors.LinearNormalize(
                            scale_range=[0.0, 1.0],
                            data_min=0.3,
                            data_max=1.0,
                )
            ]
        ),
    )
)

rmtc_sys                 .push()
