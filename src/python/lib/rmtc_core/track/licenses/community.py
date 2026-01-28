# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


from rmtc.track import License
from rmtc.system import URI


class OSS(License):
    """Open Source Software license for tracking OSS usage and compliance."""

    def __init__(self, name="", uri=None, parties=None):
        """Initialize OSS license with global jurisdiction and URI reference."""
        super(OSS, self).__init__(name=name, parties=parties, jurisdiction="Global")
        self.add_property("uri", URI, value=uri)
