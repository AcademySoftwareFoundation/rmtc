#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import argparse

from rmtc.core.ops.pipeline.nuke.builders import CATBuilder
from rmtc import System
from rmtc.system import Config
from rmtc.ops.pipeline import Pipeline

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
            name            = "CAT",
            builders        =  [
                CATBuilder()
            ]
        )
    ]    
)

# get artifacts
solution            = rmtc_sys.get_solutions(f"{args.solution_name}", exact=False)[0]
run                 = rmtc_sys.get_best_run(solution=solution)
weights = run.result_weights
rmtc_sys.pull([weights])

# build derivations
built_artifacts     = rmtc_sys.build([weights], "CAT")

print(built_artifacts)
print(f"Torch script: {built_artifacts[0].uri.path}")
print(f"Cat file: {built_artifacts[1].uri.path}")
