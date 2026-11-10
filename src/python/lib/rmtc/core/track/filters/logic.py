# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Tracking storage interface - contains all the core
entity types that we expect to store and their properties.
"""

from rmtc.system import Operator
from rmtc.track.entities import Filter


class Truth(Filter):
    """Either passes or fails according to a given bool value"""

    def __init__(
        self,
        truth=None,
    ):
        super(Truth, self).__init__()
        self.add_property(
            "truth",
            bool,
            truth,
        )

    def __call__(self, entities):
        return self.truth


class LogicFilter(Filter):
    """Passes if the logical operation on the given set of filters is true"""

    def __init__(
        self,
        filters=None,
        operator=None,
    ):
        super(LogicFilter, self).__init__()
        self.add_property(
            "filters",
            [Filter],
            filters,
        )
        self.add_property(
            "operator",
            Operator,
            operator,
        )

    def __call__(self, entities):

        if self.operator == Operator.AND:
            return all(f(entities) for f in self.filters)
        if self.operator == Operator.NAND:
            return not all(f(entities) for f in self.filters)
        if self.operator == Operator.OR:
            return any(f(entities) for f in self.filters)
        if self.operator == Operator.NOR:
            return not any(f(entities) for f in self.filters)
        if self.operator == Operator.XOR:
            return sum(1 for f in self.filters if f(entities)) == 1
        if self.operator == Operator.XNOR:
            return len({bool(f(entities)) for f in self.filters}) <= 1
        return False
