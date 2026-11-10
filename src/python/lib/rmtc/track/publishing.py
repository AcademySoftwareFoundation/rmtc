# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from abc import ABC, abstractmethod


class Publisher(ABC):

    @abstractmethod
    def resolve(self, uris):
        pass

    @abstractmethod
    def resolve_inverse(self, uris):
        pass

    def get_metadata(self, uris):
        """
        Return extra metadata stored on the publisher for each URI.
        """
        return [None for _ in uris]

    @abstractmethod
    def publish(self, entities, **kwargs):
        """
        Move the artifact into this asset manager
        This may adjust the URI and the IO object
        """
        return []

    @abstractmethod
    def unpublish(self, entities):
        """
        Remove from this asset manager
        """
        return False

    @abstractmethod
    def is_published(self, entities):
        """
        Are these artifacts pubilshed in this asset manager
        """
        return False

    @abstractmethod
    def is_immutable(self):
        """
        Can we publish over or change things
        """
        return False

    @abstractmethod
    def is_supported(self, entities):
        """
        Is the artifact supported by this manager
        """
        return False

    @abstractmethod
    def relocate(self, entity, uri):
        """
        Move the entity to the given URI
        """
        pass
