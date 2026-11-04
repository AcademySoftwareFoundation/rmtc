#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

#run rmtc-server
from rmtc import System
from rmtc.system import URI
from rmtc.track.entities import License
from rmtc.core.interface.rest.client import Client
from rmtc.system import Config
from rmtc.track.entities import Party

import argparse
parser              = argparse.ArgumentParser(
    description     = "API RMTC Examples."
)
args                = parser.parse_args()


###############################################################################

rmtc_sys            = System(
    config          = Config(name="demo"),   
)

oss_license         = rmtc_sys.get_create(
    License,
    name            = "Apache-2.0", 
    uri             = URI("https://apache.org/licenses/LICENSE-2.0.html"),
    parties         = [rmtc_sys.get_create(Party, "Mozilla Foundation")],
)

rmtc_sys            .push()

client              = Client(URI("http://127.0.0.1:9000"), rmtc_system=rmtc_sys)
results             = client.get_entities(name="Apache-2.0")
for license in results:
    print(f"{license.name}: {license.uri} ({license.status.name})")
    print(f"  parties: {[party.name for party in license.parties]} (stubs - only the name is sent)")
