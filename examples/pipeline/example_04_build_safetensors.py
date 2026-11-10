#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc import System
from rmtc.system import Config
from rmtc.core.ops.pipeline.safetensors.builders import SafetensorsWeightsBuilder
from rmtc.ops.pipeline import Pipeline

import argparse
parser              = argparse.ArgumentParser(
    description     = "Pipeline RMTC safetensors Example."
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
            name            = "Safetensors",
            builders        =  [
                SafetensorsWeightsBuilder(),
            ]
        )
    ]    
)

# get artifacts
entities            = rmtc_sys.get_solutions(f"{args.solution_name}", exact=False)
print(entities)
solution            = entities[0]
run                 = rmtc_sys.get_best_run(solution=solution)
weights             = run.result_weights
artifacts           = [weights]

# build derivations
print(f"Building {artifacts}")
built               = rmtc_sys.build(artifacts, "Safetensors")
print(f"Built: {built}")
print(f"Safetensors Path: {built[0].uri}")
