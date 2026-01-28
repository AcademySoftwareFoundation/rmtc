# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from abstract_rmtc_test import AbstractRMTCTest


class AbstractRMTCUnitTest(AbstractRMTCTest):
    """Base class for RMTC tests"""

    def __init__(self, methodName="runTest"):
        super(AbstractRMTCUnitTest, self).__init__(methodName)

        # Timeout after 5 min
        self._lock_timeout = 300000
