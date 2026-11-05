#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc import System
from rmtc.system import FileURI
from rmtc.system import Config

from rmtc.track import entities
import rmtc.ops.assets as assets
import rmtc.core.track.entities.licenses.community as community_licenses
from rmtc.track.entities import Party

import argparse
parser              = argparse.ArgumentParser(
    description     = "Simple RMTC Example."
)
args                = parser.parse_args()


###############################################################################

rmtc_sys            = System(
    config          = Config(name="demo"),   
)

oss_license         = rmtc_sys.get_create(
    community_licenses.OSS,
    name            = "Apache-2.0", 
    uri             = FileURI("https://apache.org/licenses/LICENSE-2.0.html"),
    parties         = [rmtc_sys.get_create(Party, "Mozilla Foundation")],
)

model               = rmtc_sys.create_model(entities.Model,
    name            = "Foundation Model",
    uri             = FileURI("https://github.com/foundation_model"),
    author          = "Big Tech",
    licenses        = [oss_license],
)  

dataset             = rmtc_sys.create_dataset(entities.Dataset,
    name            = "Test Data",
    uri             = FileURI("file://localhost/testdata"),
    licenses        = [oss_license],
)  

solution            = rmtc_sys.create_solution(
    name            = "Test Solution",
    uri             = FileURI("/proj/rmtc/solutions/test"),
    input_types     = [assets.Image],
    output_types    = [assets.Image],
    description     = "Example Solution",
)

run                 = rmtc_sys.create_run(
    solution        = solution,
    uri             = FileURI("/proj/rmtc/solutions/test/runs"),
    name            = "Test Run 1",
)

rmtc_sys            .push()

