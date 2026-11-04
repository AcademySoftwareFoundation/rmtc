#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc import System
from rmtc.system import Config
import rmtc.core.track.tracing.reports as text_reports

import argparse
parser              = argparse.ArgumentParser(
    description     = "Report RMTC Example."
)
parser.add_argument("--entity",
    help            = "Name of entity",
    required        = True,
)
args                = parser.parse_args()


###############################################################################

rmtc_sys            = System(
    config          = Config(name="demo"),
)

entities = rmtc_sys.get_entities(name=args.entity, exact=False)
print(f"Building report for: {entities}")
report = rmtc_sys.trace_report(report=text_reports.MarkdownReport, entities=entities)
print(report)


