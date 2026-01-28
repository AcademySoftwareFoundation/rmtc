# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from abc import ABC, abstractmethod

from rmtc.track import Entity


class IIO(ABC):
    """
    Abstract base class for reading and writing artifacts.
    """

    @abstractmethod
    def read(self, artifact, uri):  # pylint: disable=unused-argument
        """
        Read data to the specified artifact from the URI.
        If URI is None, use the artifact URI.
        """
        return False

    @abstractmethod
    def write(self, artifact, uri):  # pylint: disable=unused-argument
        """
        Write data from the specified artifact to the URI.
        If URI is None, use the artifact URI.
        """
        return False

    @abstractmethod
    def is_uri_supported(self, uri):  # pylint: disable=unused-argument
        """
        Check if the given URI is valid for this reader/writer.
        Usually the scehem and the extension (if present) are compatible.
        """
        return False

    @abstractmethod
    def is_artifact_supported(self, artifact):  # pylint: disable=unused-argument
        """
        Check if the given artifact is valid for this reader/writer.
        """
        return False


class IO(Entity, IIO):

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "IO"
