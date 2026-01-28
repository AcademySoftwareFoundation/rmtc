# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


from rmtc.track import License
from rmtc.system import URI


class Agreement(License):
    """
    Agreement license for custom licensing arrangements.

    The Agreement class represents custom agreements, contracts, or
    licensing arrangements that govern the use of data, models, or other
    ML assets.
    """

    def __init__(
        self,
        name="",
        uri=None,
        parties=None,
        date=None,
        start=None,
        finish=None,
        place="",
        reference="",
    ):
        """Initialize Agreement with comprehensive terms and documentation."""
        super(Agreement, self).__init__(
            name=name,
            parties=parties,
            start=start,
            finish=finish,
            date=date,
            jurisdiction=place,
            reference=reference,
        )
        self.add_property("uri", URI, value=uri)


class Patent(License):
    """Patent license for tracking intellectual property rights and usage."""

    def __init__(
        self,
        name="",
        code="",
        jurisdiction="",
        owner="",
        date=None,
        expiry=None,
        inventors=None,
    ):
        """Initialize Patent with IP details, ownership, and inventor information."""
        super(Patent, self).__init__(
            name=name,
            parties=[owner],
            jurisdiction=jurisdiction,
            start=date,
            finish=expiry,
        )
        self.add_property("inventors", [str], value=inventors)
        self.add_property("code", str, value=code)


class Show(License):
    """Show related license to control show access permissions."""

    def __init__(self, name="", parties=None, start=None, finish=None):
        """Initialize Show license with basic terms and validity period."""
        super(Show, self).__init__(
            name=name, parties=parties, start=start, finish=finish
        )
