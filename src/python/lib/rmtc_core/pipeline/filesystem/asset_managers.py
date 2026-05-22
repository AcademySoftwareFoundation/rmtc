# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.pipeline import AssetManager


class FilesystemManager(AssetManager):

    def __init__(
        self,
        log,
    ):
        super(FilesystemManager, self).__init__(log=log)

    def is_supported(self, artifact):
        uri = artifact.uri
        return uri.scheme == "file" and uri.host == "localhost"

    def is_published(self, artifacts):
        for artifact in artifacts:
            if not self.is_supported(artifact):
                return False
        return True

    def publish(self, artifacts):
        results = []
        for artifact in artifacts:
            if not self.is_supported(artifact):
                self.log.warning(
                    f"Unable to publish {artifact} as URI is invalid {artifact.uri}"
                )
                continue
            results.append(artifact)
        return results

    def get_widget_class(self):
        return None

    def trace_sources(self, uris):
        self.log.warning(f"Can't trace sources for {uris} in filesystem")
        return set()

    def trace_derivatives(self, uris):
        self.log.warning(f"Can't trace sources for {uris} in filesystem")
        return set()

    def resolve(self, uris):
        resolved_uris = []
        for uri in uris:
            if uri.scheme == "file" and uri.host == "localhost":
                resolved_uris.append(uri)
        return resolved_uris

    def resolve_inverse(self, uris):
        return self.resolve(uris)
