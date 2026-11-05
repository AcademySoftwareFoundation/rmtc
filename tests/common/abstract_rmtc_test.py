# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import unittest
import uuid

from rmtc import System
from rmtc.system import Config
from rmtc.system.objects import Object
from rmtc.system import Logger


class AbstractRMTCTest(unittest.TestCase):
    """Base class for RMTC tests"""

    def __init__(
        self, 
        methodName="runTest",
        cleanup=True
    ):
        super(AbstractRMTCTest, self).__init__(methodName)

        # Override the name to a unique store so we can
        # run multiple testing sessions concurrently
        self._overrides = {
            "rmtc_store": {
                "name": f"rmtc_test_{str(uuid.uuid4())}",
            },
        }
        self.config = Config(
            name="test",
            overrides=self._overrides,
        )

        # Database connection to manage locking for the lifetime of the test
        self._db_connection = None
        self._lock_timeout = 15000
        self._log = Logger()
        self._cleanup = cleanup

    @property
    def cleanup(self):
        return self._cleanup

    @cleanup.setter
    def cleanup(self, value):
        self._cleanup = value

    def setUp(self):
        """Runs before each test method in this class."""
        self.acquire_lock()
        self.addCleanup(self.release_lock)
        # the namer is process-wide (installed by every System) - reset it so
        # a test's namer never leaks into the next
        self.addCleanup(Object.set_namer, None)
        self.clear_database()

    def tearDown(self):
        """Runs after each test method in this class."""
        self.clear_database()

    def clear_database(self):
        """Delete the test graph"""
        if self._cleanup:
            self.get_system().delete_all()

    def get_system(self, **kwargs): # add all system args here
        """Get an instance of the RMTC System."""
        rmtc_sys = System(
            config=self.config,
            **kwargs,
        )
        return rmtc_sys

    def acquire_lock(self):
        # self._db_connection = self.get_system().open()
        # self._db_connection.lock(timeout=self._lock_timeout)
        pass

    def release_lock(self):
        # self._db_connection.unlock()
        # self._db_connection.close()
        # self._db_connection = None
        pass        
