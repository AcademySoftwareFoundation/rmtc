#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc_core import System
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
parser.add_argument("--store_name",
    help            = "Specify a store name",
    default         = "rmtc_examples",
)
args                = parser.parse_args()


###############################################################################

rmtc_sys            = System(
    config          = Config(overrides={"rmtc_store":{"name": args.store_name}}),
)

# get artifacts
solution            = rmtc_sys.get_solutions(f"{args.solution_name}")[0]
run                 = rmtc_sys.get_best_run(solution=solution)
model               = run.model
weights             = run.result_weights
artifacts           = [model, weights]

# build derivations
built               = rmtc_sys.build(artifacts)
print(f"Built: {built}")

# publish the artifacts
published           = rmtc_sys.publish(artifacts + built)
print(f"Published: {published}")

