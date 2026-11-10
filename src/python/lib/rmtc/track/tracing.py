# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from abc import ABC, abstractmethod

from rmtc.system import URI
from rmtc.track.store import Direction


class Watermarker(ABC):
    """
    Interface to define a watermarker on the given artifacts
    e.g. C2PA
    """

    @abstractmethod
    def is_supported(self, entities):
        """
        This watermark supports marking the given artifact
        """
        return False

    @abstractmethod
    def __call__(self, entities, **kwargs):
        """
        Watermark the incoming artifact
        """
        return entities


class Tracer(ABC):

    @abstractmethod
    def trace_sources(self, uris, recurse=False) -> list[URI]:
        """
        Trace upwards, to any asset manager URIs that this asset manager URI used
        """
        return set()

    @abstractmethod
    def trace_derivatives(self, uris, recurse=False) -> list[URI]:
        """
        Trace downwards, to any asset manager URIs that used this asset manager URI
        """
        return set()


class Report(ABC):
    """Report structure to generate an output in a given direction"""

    def __init__(self, rmtc_system, direction=Direction.SOURCES):
        self._system = rmtc_system
        self._direction = direction

    @property
    def system(self):
        """Get system."""
        return self._system

    @property
    def direction(self):
        """Which direction?"""
        return self._direction

    @abstractmethod
    def __call__(self, entities=None):
        """Override this to create reporting for the given entities"""
        pass
