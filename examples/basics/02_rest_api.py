#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

#run rmtc-server
from rmtc.system import URI
from rmtc.track import License
from rmtc_core import System
from rmtc.system import Config
from rmtc_core.interface.rest.flask import Client

import argparse
parser              = argparse.ArgumentParser(
    description     = "API RMTC Examples."
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

oss_license         = rmtc_sys.create_license(License,
    name            = "Apache-2.0", 
    uri             = URI("https://apache.org/licenses/LICENSE-2.0.html"),
    parties         = ["Mozilla Foundation"],
)

rmtc_sys            .push()

client              = Client(URI("http://127.0.0.1:5000"), system=rmtc_sys)
results             = client.get_entities(name="Apache-2.0")
print(results)