#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc import System
from rmtc.system import Config

import argparse
parser              = argparse.ArgumentParser(
    description     = "Simple RMTC Example."
)
args                = parser.parse_args()


###############################################################################

rmtc_sys            = System(
    config          = Config(name="demo"),
)

store = rmtc_sys.track.store

# prompt
red = "\033[1;91m"
bld = "\033[1m"
grn = "\033[32m"
org = "\033[38;5;208m"
rst = "\033[0m"
print(f"{bld}{red}DELETE:{rst} {bld}{store.name}@{store.uri}{rst}?")
delete = False
response = input("Type 'yes' to confirm: ")
if response.lower() == 'yes':
    response = input("Are you sure?: ")
    if response.lower() == 'yes':
        delete = True

# Print
if delete:
    rmtc_sys.delete_all()
    print(f"{bld}{org}DELETED:{rst} {bld}{store.name}@{store.uri}{rst}")
else:
    print(f"{bld}{grn}CANCELLED{rst}")
