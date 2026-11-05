# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from abc import ABC, abstractmethod

from rmtc.track.store import Entity


class BaseIO(ABC):
    """
    Abstract base class for reading and writing artifacts.

    This is a progressive writer - you keep writing until read or write return False
    Flush will write the whole artifact
    """

    @abstractmethod
    def get_artifact_type(self):
        """
        Return back the artifact type that this works with
        """
        pass

    @abstractmethod
    def get_scheme(self):
        """
        What scheme does this IO work with
        """
        pass

    @abstractmethod
    def create_name(self, artifact):
        """
        Construct a suitable filename for this artifact - not full path
        """
        pass

    @abstractmethod
    def is_uri_supported(self, uri):
        """
        Check if the given URI is valid for this reader/writer.
        Usually the scehem and the extension (if present) are compatible.
        """
        pass

    @abstractmethod
    def is_artifact_supported(self, artifact):
        """
        Check if the given artifact is valid for this reader/writer.
        """
        pass

    @abstractmethod
    def read(self, uri, artifact, asset_manager):
        """
        Read data to the specified artifact from the URI.
        If URI is None, use the artifact URI.
        """
        pass

    @abstractmethod
    def reset(self, artifact, asset_manager):
        """
        Write data from the specified artifact to the URI.
        If URI is None, use the artifact URI.
        """
        pass

    @abstractmethod
    def write(self, uri, artifact, asset_manager):
        """
        Write data from the specified artifact to the URI.
        If URI is None, use the artifact URI.
        """
        pass

    @abstractmethod
    def init(self, artifact, asset_manager):
        """
        Initialise the URI for the artifact from the asset manager
        """
        pass


class IO(Entity, BaseIO):

    def init(self, artifact, asset_manager):
        """
        Most IOs don't need to do this - so provide a default
        """
        return True

    def reset(self, artifact, asset_manager):
        return artifact.reset()

    # HACK : not all IOs support creation of URIs
    def create_name(self, artifact):
        return None

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "IO"

    def is_uri_supported(self, uri):
        return self.get_scheme() == uri.scheme

    def is_artifact_supported(self, artifact):
        """
        Check types by default
        """
        if artifact.uri.scheme != self.get_scheme():
            return False
        if not isinstance(artifact, self.get_artifact_type()):
            return False
        return True
