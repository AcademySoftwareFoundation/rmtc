# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.system.environment import BaseEnvironmentManager


class PackageTracker(BaseEnvironmentManager):
    """
    Simple package tracker that shows what dependencies exist
    Does not manage the versions or any true envrionment function
    """

    def __init__(self, log):
        self._log = log
        self._packages = {}

    def add_packages(self, packages):
        packages_to_setup = set()
        for package in packages:
            if package.name not in self._packages.keys():
                self._packages[package.name] = 0
                packages_to_setup.add(package)
            self._packages[package.name] += 1
        self.setup_packages(packages_to_setup)
        return True

    def remove_packages(self, packages):
        packages_to_teardown = set()
        for package in packages:
            if package.name in self._packages.keys():
                self._packages[package.name] -= 1
                if self._packages[package.name] == 0:
                    self._packages.pop(package.name)
                    packages_to_teardown.add(package)
        self.teardown_packages(packages_to_teardown)
        return True

    def setup_packages(self, packages):
        return True

    def teardown_packages(self, packages):
        return True

    def setup(self, env_name):
        return True

    def teardown(self, env_name):
        return True

    def get_packages(self):
        return self._packages.keys()

    def package_exists(self, package):
        return package.name in self._packages.keys()
