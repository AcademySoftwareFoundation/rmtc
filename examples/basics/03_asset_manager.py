#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import rmtc
import rmtc.track
from rmtc_core import System
from rmtc.system import Config
from rmtc.system import URI

import argparse
parser              = argparse.ArgumentParser(
    description     = "Asset Manager Publish Example."
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

# Create test artifacts
model               = rmtc_sys.create_model(rmtc.track.Model,
    name            = "Model", 
    uri             = URI(scheme="file", host="localhost", path="/test/path/model.mdl"),
)
dataset             = rmtc_sys.create_dataset(rmtc.track.Dataset,
    name            = "Dataset",
    uri             = URI(scheme="file", host="localhost", path="/test/path/"),     
)

# Publish them
published           = rmtc_sys.publish([model, dataset])
print(f"Published to: {[(artifact.name, artifact.uri) for artifact in published]}")