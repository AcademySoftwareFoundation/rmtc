# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


from abc import ABC, abstractmethod


class IEnvironmentManager(ABC):
    """
    Abstract base class for dependency environments.
    The factory system has
    Note: this is TBC and is subject to change.
    """

    @abstractmethod
    def setup(self, env):
        """Initialize the environment and prepare resources."""
        return False

    @abstractmethod
    def teardown(self, env):
        """Clean up environment resources and finalize."""
        return False

    @abstractmethod
    def get_packages(self):
        """Get a set of packages"""
        return set()


class NullEnv(IEnvironmentManager):

    def __init__(self, log, packages=None):
        self._log = log
        if packages is None:
            packages = set()
        self._packages = packages

    def setup(self, env):
        self._packages.update(env)
        return False

    def teardown(self, env):  # pylint: disable=unused-argument
        return False

    def get_packages(self):
        return self._packages
