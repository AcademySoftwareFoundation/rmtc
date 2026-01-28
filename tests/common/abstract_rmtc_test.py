# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import unittest

from rmtc_core import System
from rmtc.system import Config
from rmtc.objects import Object

from rmtc.system import Logger


class AbstractRMTCTest(unittest.TestCase):
    """Base class for RMTC tests"""

    def __init__(self, methodName="runTest"):
        super(AbstractRMTCTest, self).__init__(methodName)

        # Override the name to testing
        self._overrides = {
            "rmtc_store": {
                "name": "rmtc_test",
            },
            "rmtc_system": {
                "mode": "TESTING",
            },
        }
        self.config = Config(
            overrides=self._overrides,
        )

        # Database connection to manage locking for the lifetime of the test
        self._db_connection = None
        self._lock_timeout = 15000
        self._log = Logger()

    def setUp(self):
        """Runs before each test method in this class."""
        self.acquire_lock()
        self.addCleanup(self.release_lock)
        self.clear_database()

    def tearDown(self):
        """Runs after each test method in this class."""
        self.clear_database()

    def clear_database(self):
        """Delete the test graph"""
        self.get_system().delete_all()

    def get_system(self):
        """Get an instance of the RMTC System."""
        rmtc_sys = System(
            config=self.config,
        )
        return rmtc_sys

    def acquire_lock(self):
        self._db_connection = self.get_system().open()
        self._db_connection.lock(timeout=self._lock_timeout)

    def release_lock(self):
        self._db_connection.unlock()
        self._db_connection.close()
        self._db_connection = None
