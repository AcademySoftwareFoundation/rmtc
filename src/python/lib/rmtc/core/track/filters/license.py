# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Tracking storage interface - contains all the core
entity types that we expect to store and their properties.
"""

from itertools import combinations

from rmtc.system.objects import IN
from rmtc.track.entities import Filter, Right, License, Artifact, Solution


class RightsFilter(Filter):
    """Passes if the entities permit the set of given rights"""

    def __init__(
        self,
        rights=None,
    ):
        super(RightsFilter, self).__init__()
        self.add_property(
            "rights",
            [Right],
            rights,
            direction=IN,
            member=False,
        )

    def __call__(self, entities):
        """The given rights are permitted by the license of all the artifacts"""
        artifact_licenses = set()
        for artifact in entities:
            if isinstance(artifact, Artifact):
                artifact_licenses.update(set(artifact.licenses))
        for artifact_license in artifact_licenses:
            if not artifact_license.is_permitted(
                self.rights,
            ):
                return False
        return True


class JurisdicationFilter(Filter):
    pass


class PartyFilter(Filter):
    pass


class ComplianceFilter(Filter):
    """Passes if the entities are compliant with the given licenses"""

    def __init__(self, licenses=None):
        super(ComplianceFilter, self).__init__()
        self.add_property(
            "licenses",
            [License],
            licenses,
        )

    def __call__(self, entities):
        """The entities are all compliant with the licenses"""
        artifact_licenses = set()
        for artifact in entities:
            if isinstance(artifact, Artifact):
                artifact_licenses.update(set(artifact.licenses))
        for a, b in combinations(artifact_licenses, 2):
            if not a.is_compliant(b):
                return False
        return True


class SolutionCompliant(Filter):
    """Passes if the entities are compliant with existing solution entities"""

    def __init__(self, solution=None):
        super(SolutionCompliant, self).__init__()
        self.add_property(
            "solution",
            Solution,
            solution,
        )

    def __call__(self, entities):
        """The incoming license are compatible with the existing licenses used in the solution"""
        return ComplianceFilter(entities=self.solution.artifacts)(entities)
