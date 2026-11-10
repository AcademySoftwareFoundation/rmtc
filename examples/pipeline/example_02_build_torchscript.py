#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc import System
from rmtc.system import Config
from rmtc.core.ops.pipeline.torch.builders import TorchScriptBuilder
from rmtc.ops.pipeline import Pipeline

import argparse
parser              = argparse.ArgumentParser(
    description     = "Pipeline RMTC ONNX Example."
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
    pipelines       = [
        Pipeline(
            name            = "TorchScript",
            builders        =  [
                TorchScriptBuilder(),
            ]
        )
    ]
)

# get artifacts
print(f"Searching for solution {args.solution_name}")
solution            = rmtc_sys.get_solutions(f"{args.solution_name}", exact=False)[0]
run                 = rmtc_sys.get_best_run(solution=solution)
model               = run.model
weights             = run.result_weights
artifacts           = [model, weights]

# build derivations
print(f"Building: {artifacts}")
built               = rmtc_sys.build(artifacts, "TorchScript")

print(f"Built: {built}")
print(f"TorchScript Path: {built[0].uri}")

