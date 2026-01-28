# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from abc import ABC, abstractmethod

from rmtc.track import Direction
from rmtc.system import RMTCException, URI


class IAssetManager(ABC):

    @abstractmethod
    def publish(self, artifacts):
        """
        Take an artifact, convert the URI to one native for this scheme
        and replace the IO object with an instance that uses this asset manager
        to resolve URIs

        Return the list of successfully published artifacts
        """
        return []

    @abstractmethod
    def build(self, artifacts, pipeline_name=None):
        """
        Execute pipline of artifacts and return back comformed artifacts
        these should be regarded as variants
        """
        pass

    @abstractmethod
    def is_published(self, artifacts):
        """
        Are these artifacts pubilshed?
        """
        return False

    @abstractmethod
    def trace_sources(self, uris):
        """
        Trace upwards, to any asset manager URIs that this asset manager URI used
        """
        return set()

    @abstractmethod
    def trace_derivatives(self, uris):
        """
        Trace downwards, to any asset manager URIs that used this asset manager URI
        """
        return set()

    @abstractmethod
    def resolve(self, uris):
        """
        Resolve an asset manager URI to an RMTC URI (disk)
        e.g. given a file URI find the OpenAssetIO URI
        """
        return [URI()]

    @abstractmethod
    def resolve_inverse(self, uris):
        """
        Resolve an RMTC URI (disk) to an asset manager URI
        e.g. given a file URI find the OpenAssetIO URI
        """
        return [URI()]

    @abstractmethod
    def is_supported(self, artifact):
        """
        Is the artifact supported by this manager
        """
        return False

    @abstractmethod
    def read(self, artifacts):
        """Read in all the artifacts"""
        return False

    @abstractmethod
    def write(self, artifacts):
        """Write out all the artifacts"""
        return False

    @abstractmethod
    def reset(self, artifacts):
        """Reset all the artifacts"""
        return False

    @abstractmethod
    def get_widget_class(self):
        """UI component for managing publish settings"""
        return None


class IBuilder(ABC):

    @abstractmethod
    def is_supported(self, artifact):
        """
        This build supports building the given artifact
        """
        return False

    @abstractmethod
    def __call__(self, asset_manager, artifact):
        """
        Run the builder against each artifact, this builds a
        publishable variant - same functionality, same provenance, different technique.
        For example: TorchPackage to TorchScript or ONNX
        """
        return artifact


class Pipeline:

    def __init__(self, log, name, builders, description=None):
        self._log = log
        self._name = name
        self._builders = builders
        self._description = description

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return self._description or ""

    def __call__(self, asset_manager, artifacts):
        built = set()
        for artifact in artifacts:
            if artifact.class_category in self._builders:
                for builder in self._builders[artifact.class_category]:
                    results = builder(asset_manager, artifact)
                    for result in results:
                        result.add_ancestors([artifact])
                    built.update(results)
        return list(built)


class AssetManager(IAssetManager):

    def __init__(self, log):
        self._log = log
        self._options = None
        self._pipelines = {}

    @property
    def log(self):
        return self._log

    @property
    def pipelines(self):
        return self._pipelines

    def add_pipeline(self, pipeline):
        self._pipelines[pipeline.name] = pipeline

    def remove_pipeline(self, pipeline):
        self._pipelines.remove(pipeline.name)

    def build(self, artifacts, pipeline_name=None):
        built = []
        if pipeline_name is None:
            for pipeline in self._pipelines.values():
                results = pipeline(
                    asset_manager=self,
                    artifacts=artifacts,
                )
                built.extend(results)
        elif pipeline_name in self._pipelines:
            results = self._pipelines[pipeline_name](
                asset_manager=self,
                artifacts=artifacts,
            )
            built.extend(results)
        return built

    def trace(self, artifacts, direction):
        """Trace up and down according to direction"""
        uris = [artifact.uri for artifact in artifacts]
        if direction == Direction.SOURCES:
            return self.trace_sources(uris)
        return self.trace_derivatives(uris)

    def reset(self, artifacts):
        """Reset any artifacts"""
        for artifact in artifacts:
            artifact.reset()

    def read(self, artifacts):
        """Read in all the artifacts"""
        uris = [artifact.uri for artifact in artifacts]
        resolved_uris = self.resolve(uris)
        for artifact, uri in zip(artifacts, resolved_uris):
            io = artifact.io
            if io is None:
                self._log.warning(
                    f"Artifact {artifact} is self reading, deprecated - use IO"
                )
                artifact.read(self)
            else:
                io.read(artifact, uri)
            if not artifact.is_valid():
                raise RMTCException(f"Read failed on {artifact} using manager {self}")

    def write(self, artifacts):
        """Write out all the artifacts"""
        uris = [artifact.uri for artifact in artifacts]
        resolved_uris = self.resolve(uris)
        for artifact, uri in zip(artifacts, resolved_uris):
            if uri is None:
                self._log.warning(f"Artifact {artifact} uri is invalid")
                continue
            if not artifact.is_valid():
                raise RMTCException(
                    f"Cannot write invalid {artifact} using manager {self}"
                )
            io = artifact.io
            if io is None:
                self._log.warning(
                    f"Artifact {artifact} is self writing, deprecated - use IO"
                )
                artifact.write(self)
            else:
                io.write(artifact, uri)
