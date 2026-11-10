# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import os
import tempfile
from pathlib import Path

from rmtc.ops.pipeline import ReaderWriter
from rmtc.system import FileURI, RMTCException


class DiskReaderWriter(ReaderWriter):

    IDENTITY_MODES = ("instantiated_at", "version")

    def __init__(
        self,
        log,
        env_manager,
        publisher,
        immutable=True,
        root=None,
        identity_mode="instantiated_at",
    ):
        super(DiskReaderWriter, self).__init__(
            log=log,
            env_manager=env_manager,
            publisher=publisher,
            immutable=immutable,
        )

        # A root path reduces the scope of the file system manager for security & protection
        # so you could have multiple filesystems
        # with differing settings and mutability and visibility
        # the manager will only support relative paths to this root
        self._root = None
        if root is not None:
            self._root = root
        self.set_identity_mode(identity_mode)

    @property
    def identity_mode(self):
        return self._identity_mode

    def set_identity_mode(self, identity_mode):
        if identity_mode not in self.IDENTITY_MODES:
            raise RMTCException(f"Invalid identity mode '{identity_mode}'")
        self._identity_mode = identity_mode

    def is_uri_supported(self, uri):
        if uri is None:
            raise RMTCException("Invalid URI")
        if not uri.is_valid():
            return False
        if uri.scheme != "file":
            return False
        if uri.host != "localhost":
            return False
        if self._root is not None:
            if not uri.path.is_relative_to(self._root):
                return False
        return True

    def exists(self, uris):
        for uri in uris:
            if uri is not None:
                if os.path.exists(str(uri.path)):
                    return True
        return False

    def identity_segment(self, artifact):
        """
        Path/filename identity for an artifact - instantiated_at or version,
        whichever this readerwriter is configured to use.
        """
        if self._identity_mode == "version":
            if artifact.version is None or not artifact.version.is_valid():
                raise RMTCException(
                    f"Cannot derive identity for {artifact} with"
                    f"identity_mode='version' and unset/invalid version"
                )
            return str(artifact.version)
        return self.timestamp_segment(artifact.instantiated_at)

    def create_transient_uri(self, name):
        return FileURI(path=Path(tempfile.mkdtemp(name)))

    def create_uri(self, artifact, root):
        """
        Derive the artifact URI beneath the root.
        Container entities with no IO get identity as a bare directory
        segment: root/category/<identity>. Leaf entities with an IO splice
        identity into the filename instead, so a category folder holds many
        files side by side: root/category/<name>-<identity><suffix>.
        """
        if root is None or not root.is_valid():
            raise RMTCException(f"Invalid root URI '{root}'")
        path = root.path
        path /= self.category_folder(artifact)

        io = artifact.get_io
        io = io() if callable(io) else None
        namer = io.create_name if io is not None else None
        name = namer(artifact) if callable(namer) else None

        identity = self.identity_segment(artifact)
        if name:
            stem, suffix = os.path.splitext(name)
            path /= f"{stem}-{identity}{suffix}"
        else:
            path /= identity

        # is_relative_to is lexical, so parent traversal needs its own check
        if ".." in path.parts or not path.is_relative_to(root.path):
            raise RMTCException(f"Derived path '{path}' escapes root '{root}'")
        return FileURI(path=path)

    def prepare(self, uri):
        """Create the parent containers for the URI target"""
        uri.path.parent.mkdir(parents=True, exist_ok=True)

    def delete_uri(self, uri):
        if uri is None:
            raise RMTCException("Invalid uri")
        if self.is_immutable():
            raise RMTCException(f"Deleting file {uri} disallowed due to immutability")
        if uri.path == "/":
            raise RMTCException(f"Attempting to delete root {uri}")
        if self.exists([uri]):
            if uri.path.is_dir():
                try:
                    uri.path.rmdir()
                except OSError:
                    pass
            else:
                uri.path.unlink()
