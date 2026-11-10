#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc import System
from rmtc.system import Config

import argparse
parser              = argparse.ArgumentParser(
    description     = "Pipeline RMTC Publish Example."
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

# get artifacts
solution            = rmtc_sys.get_solutions(f"{args.solution_name}")[0]
run                 = rmtc_sys.get_best_run(solution=solution)
model               = run.model
weights             = run.result_weights
artifacts           = [model, weights]
print(artifacts)

# publish the artifacts
published           = rmtc_sys.publish(artifacts)
print(f"Published: {published}")

