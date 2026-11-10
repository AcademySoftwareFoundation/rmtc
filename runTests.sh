#!/bin/bash

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

# You will need to be in an environment with rmtc and pytest to run tests

echo "Running all unit tests";

# NOTE - stdout and prints only appear if there is an error
pytest
