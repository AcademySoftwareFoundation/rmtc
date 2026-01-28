# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import pytest
import sys
from os.path import abspath, dirname, join

# Get the common python directory and insert it into the python path
current_dir = dirname(abspath(__file__))
common_dir = abspath(join(current_dir, "../common"))
sys.path.insert(0, common_dir)


@pytest.fixture(scope="class", autouse=True)
def class_tmp_path(request, tmp_path_factory: pytest.TempdirFactory):
    """
    Provides a class-scoped temporary directory for unittest.TestCase classes.
    """
    tmp_dir = tmp_path_factory.mktemp("rmtc_test_data")
    request.cls.tmp_path = tmp_dir
    yield tmp_dir
