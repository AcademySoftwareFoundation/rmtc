# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
The Driver GUI classes - this will likely need to be paritioned
"""

from Qt import QtWidgets


# create a node class object inherited from BaseNode.
class Driver(QtWidgets.QWidget):
    """
    This class provides the primary user interface for exploring the source
    and derivative relationships in the RMTC storage system.
    """

    def __init__(self, system):
        """Initialize the RMTC Driver main window."""
        super(Driver, self).__init__()
        self._system = system
