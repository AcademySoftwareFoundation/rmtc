# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Tracking storage interface - contains all the core
entity types that we expect to store and their properties.
"""

from rmtc.track.entities import Filter


class StackFilter(Filter):
    """Runs each filter in turn, returns false on the first failure"""

    def __init__(
        self,
        filters=None,
    ):
        super(StackFilter, self).__init__()
        self.add_property(
            "filters",
            [Filter],
            filters,
        )

    def __call__(self, entities):
        for f in self.filters:
            if not f(entities):
                return False
        return True
