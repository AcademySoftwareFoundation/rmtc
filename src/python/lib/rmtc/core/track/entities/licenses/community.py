# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


from rmtc.track.entities import License


class OSS(License):
    """Open Source Software license for tracking OSS usage and compliance."""

    def __init__(
        self,
        name=None,
        uri=None,
        parties=None,
        version=None,
        spdx=None,
    ):
        """Initialize OSS license with global jurisdiction and URI reference."""
        super(OSS, self).__init__(
            name=name,
            parties=parties,
            jurisdictions=None,
            version=version,
            uri=uri,
        )
        self.add_property("spdx", str, spdx)
