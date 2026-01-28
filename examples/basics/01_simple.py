#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc import artifacts, track
from rmtc.system import URI
from rmtc_core import System
from rmtc.system import Config

import rmtc_core.track.licenses.community as community_licenses

import argparse
parser              = argparse.ArgumentParser(
    description     = "Simple RMTC Example."
)
parser.add_argument("--store_name",
    help            = "Specify a store name",
    default         = "rmtc_examples",
)
args                = parser.parse_args()


###############################################################################

rmtc_sys            = System(
    config          = Config(
        overrides   = {
            "rmtc_store":{"name": args.store_name},
        },
    )
)

oss_license         = rmtc_sys.create_license(community_licenses.OSS,
    name            = "Apache-2.0", 
    uri             = URI("https://apache.org/licenses/LICENSE-2.0.html"),
    parties         = ["Mozilla Foundation"],
)

model               = rmtc_sys.create_model(track.Model,
    name            = "Foundation Model",
    uri             = URI("https://github.com/foundation_model"),
    author          = "Big Tech",
    licenses        = [oss_license],
)  

dataset             = rmtc_sys.create_dataset(track.Dataset,
    name            = "Test Data",
    uri             = URI("file://localhost/testdata"),
    licenses        = [oss_license],
)  

solution            = rmtc_sys.create_solution(
    name            = "Test Solution",
    uri             = URI("/proj/rmtc/solutions/test"),
    input_type      = artifacts.Image,
    output_type     = artifacts.Image,
    description     = "Example Solution",
)
solution            .add_models([model])
solution            .add_datasets([dataset])

run                 = rmtc_sys.create_run(
    solution        = solution,
    name            = "Test Run 1",
)

rmtc_sys            .push()

