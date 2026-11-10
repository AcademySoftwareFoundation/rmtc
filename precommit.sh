#!/bin/bash
#
# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

black ./src/python
pylint --clear-cache-post-run y --jobs=1 --rcfile ./.pylintrc ./src/python/

