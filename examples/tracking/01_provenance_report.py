#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc_core import System
from rmtc.system import Config
import rmtc_core.track.reports.text as text_reports

import argparse
parser              = argparse.ArgumentParser(
    description     = "Report RMTC Example."
)
parser.add_argument("--entity",
    help            = "Name of entity",
    required        = True,
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

report = rmtc_sys.create_report(report=text_reports.MarkdownReport, entity_names=[args.entity])
print(report)


