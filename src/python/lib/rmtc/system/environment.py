# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


from abc import ABC, abstractmethod


class BaseEnvironmentManager(ABC):
    """
    Interface for environment & package management
    You can setup an environment in 2 ways:
    * Adding named/version packages
    * Manager specific string identifier that encompasses a whole env
    The aim is that artifacts are fully resolvable once the environment is setup
    """

    @abstractmethod
    def add_packages(self, packages):
        """Add a package to the environment"""
        return False

    @abstractmethod
    def remove_packages(self, packages):
        """Remove a package from the environment"""
        return False

    @abstractmethod
    def get_packages(self):
        """Get a set of packages"""
        return []

    @abstractmethod
    def package_exists(self, package):
        """Get a set of packages"""
        return []

    @abstractmethod
    def setup(self, env_name):
        """
        Using an arbitrary environment identifier, initialise
        """
        return False

    @abstractmethod
    def teardown(self, env_name):
        """
        Using an arbitrary environment identifier, remove
        """
        return False
