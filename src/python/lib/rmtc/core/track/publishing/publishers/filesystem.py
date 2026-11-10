# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from packaging.version import InvalidVersion

from rmtc.track.publishing import Publisher
from rmtc.system import RMTCException, Version, FileURI


class DiskPublisher(Publisher):

    def __init__(
        self,
        log,
        immutable=True,
        root=None,
    ):
        self._log = log
        self._immutable = immutable
        self._root = root

    def is_immutable(self):
        return self._immutable

    def is_supported(self, entities):
        for entity in entities:
            if entity.uri is None or not entity.uri.is_valid():
                return False
            if entity.uri.scheme != "file":
                return False
            if entity.uri.host != "localhost":
                return False
            if self._root is not None:
                if not entity.uri.path.is_relative_to(self._root):
                    return False
        return True

    def relocate(self, entity, uri):
        if self.is_immutable():
            raise RMTCException(
                f"Cannot move entity {entity} in an immutable publishing system"
            )
        if uri is None or not uri.is_valid():
            raise RMTCException("Invalid uri")
        if uri.path.exists():
            self._log.warning(f"Overwriting file {uri} with {entity}")
        old_uri = entity.uri
        old_uri.path.rename(uri.path)
        entity.uri = uri

    def is_published(self, entities):
        for entity in entities:
            if entity is None:
                raise RMTCException("Invalid entity")
            if entity.uri is None:
                return False
            if not entity.uri.is_valid():
                return False
            if not entity.uri.path.exists():
                return False
        return True

    def reserve(self, path):
        """
        Reserve a version using the suffix:

        If a file path is entered you get: /path/to/file-X.0.0.ext, where X+=1
        If a folder is entered you get: /path/to/folder/X.0.0, where X+=1
        """
        if path is None:
            raise RMTCException("Invalid path")

        if path.suffix != "":
            version = Version(major=1)
            while True:
                suffix = path.suffix
                name = path.stem
                parts = name.split("-")  # assumes <name>-<version>.<ext>
                if len(parts) == 2:
                    name = parts[0]
                    version = Version(parts[1]).bump_major()
                candidate = path.parent / f"{name}-{version}{suffix}"
                if not candidate.exists():
                    candidate.parent.mkdir(parents=True, exist_ok=True)
                    candidate.touch()
                    return (FileURI(path=candidate), version)
                path = candidate
        else:
            versions = [Version()]
            if path.exists():
                for child in path.iterdir():
                    if child.is_dir():
                        try:
                            versions.append(Version(child.name))
                        except (RMTCException, InvalidVersion):
                            continue
            versions.sort()
            version = versions[-1].bump_major()
            allocated = path / str(version)
            allocated.mkdir(parents=True, exist_ok=True)
            return (FileURI(path=allocated), version)

    def publish(self, entities, **kwargs):
        results = []
        for entity in entities:
            if entity is None:
                raise RMTCException("Invalid entity")
            if not self.is_supported([entity]):
                self._log.warning(
                    f"Unable to publish {entity} as URI is invalid {entity.uri}"
                )
                continue
            results.append(entity)
        return results

    def resolve(self, uris):
        resolved_uris = []
        for uri in uris:
            if uri is None:
                raise RMTCException("Invalid uri")
            if uri.scheme == "file" and uri.host == "localhost":
                resolved_uris.append(uri)
            else:
                resolved_uris.append(None)
        return resolved_uris

    def resolve_inverse(self, uris):
        return self.resolve(uris)

    def unpublish(self, entities):
        raise NotImplementedError()
