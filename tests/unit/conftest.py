# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import sys
from os.path import abspath, dirname, join

# Get the common python directory and insert it into the python path
current_dir = dirname(abspath(__file__))
common_dir = abspath(join(current_dir, "../common"))
sys.path.insert(0, common_dir)
