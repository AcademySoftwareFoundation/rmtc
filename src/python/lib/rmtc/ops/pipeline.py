# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from abc import ABC, abstractmethod

from rmtc.ops.artifacts import Artifact
from rmtc.system import RMTCException, Logger, URI
from rmtc.track.entities import Run, Weights, Checkpoint


class BaseReaderWriter(ABC):

    @abstractmethod
    def is_uri_supported(self, uri):
        """
        Is the artifact supported by this manager
        """
        return False

    @abstractmethod
    def create_transient_uri(self, name):
        """
        Create a new root URI that is temporary
        """
        return None

    @abstractmethod
    def create_uri(self, artifact, root):
        """
        Derive the artifact URI beneath the given root URI.
        """
        return None

    @abstractmethod
    def prepare(self, uri):
        """
        Make the URI target writable by creating parent folders.
        Usually happens before the write itself.
        """
        return None

    @abstractmethod
    def delete_uri(self, uri):
        return None

    @abstractmethod
    def is_immutable(self):
        """Can this system actually write out"""
        pass

    @abstractmethod
    def init(self, artifacts):
        """Init the artifacts with URIs"""
        pass

    @abstractmethod
    def read(self, artifacts: list[Artifact], metadata: dict = None) -> bool:
        """Read in all the artifacts. If `metadata` is a dict, populate it in
        place with per-artifact publisher metadata, keyed by obj_id."""
        pass

    @abstractmethod
    def write(self, artifacts: list[Artifact]) -> bool:
        """Write out all the artifacts"""
        pass

    @abstractmethod
    def flush(self, artifacts: list[Artifact]) -> bool:
        """Write out all the artifacts AND reset"""
        pass

    @abstractmethod
    def reset(self, artifacts: list[Artifact]) -> bool:
        """Reset all the artifacts"""
        pass

    @abstractmethod
    def exists(self, uris: list[URI]) -> bool:
        pass


class ReaderWriter(BaseReaderWriter):
    """
    Helper asset manager base class
    Implements most of the interface but resolve
    """

    def __init__(self, env_manager, log, publisher, immutable=True):
        self._publisher = publisher
        self._log = log
        self._env_manager = env_manager
        self._immutable = immutable
        if publisher is None:
            raise RMTCException("No publisher passed in")
        if env_manager is None:
            raise RMTCException("No environment manager passed in")

    def is_immutable(self):
        return self._immutable

    @property
    def log(self):
        return self._log

    @property
    def env_manager(self):
        return self._env_manager

    @staticmethod
    def category_folder(entity):
        """Folder name for an entity category: eg. Runs -> runs"""
        folder = entity.category().lower()
        if not folder.endswith("s"):
            folder += "s"
        return folder

    @staticmethod
    def timestamp_segment(instantiated_at):
        """
        Path segment for instantiated_at identity stamp.
        ISO-8601 UTC with ':' and '+' substituted - some filesystems reject
        them. Uniform substitution keeps lexicographic order chronological.
        """
        return str(instantiated_at).replace(":", "-").replace("+", "-")

    def init(self, artifacts):
        """Init the artifact URIs and names (maybe)"""

        if not isinstance(artifacts, list):
            raise RMTCException("Require list of artifacts to init")

        for artifact in artifacts:

            if artifact.is_ephemeral():
                self._log.debug(f"Skipping ephemeral artifact {artifact}")
                continue

            # get io
            io = artifact.get_io()
            if io is None:
                raise RMTCException(f"Artifact missing IO {artifact}")

            # init
            if not io.init(artifact, self):
                raise RMTCException(f"Init failed on {artifact} using manager {self}")

            # check
            if not artifact.is_valid():
                raise RMTCException(f"Invalid {artifact}")

    def read(self, artifacts, metadata=None):
        """
        Read in all the artifacts. If metadata is a dict, it is populated
        in place with per-artifact metadata stored on the publisher, keyed by
        the artifact's object id.
        """

        if not isinstance(artifacts, list):
            raise RMTCException("Require list of artifacts to read")

        for artifact in artifacts:

            # check
            if not isinstance(artifact, Artifact):
                raise RMTCException(
                    f"Object {artifact} is not Artifact ({artifact.__class__})"
                )
            if metadata is not None:
                metadata[artifact.obj_id] = self._publisher.get_metadata(
                    [artifact.uri]
                )[0]

            if artifact.is_ephemeral():
                self._log.debug(f"Skipping ephemeral artifact {artifact}")
                continue

            # already read
            if artifact.is_valid():
                self._log.debug(f"Skipping valid artifact {artifact}")
                continue

            # log
            self._log.debug(f"Loading artifact: {artifact}")

            # get IO
            io = artifact.get_io()
            if io is None:
                raise RMTCException(f"Artifact missing IO {artifact}")

            # setup packages
            if len(artifact.get_dependencies()) > 0:
                self._log.debug(f"Adding dependencies: {artifact.get_dependencies()}")
            self.env_manager.add_packages(artifact.get_dependencies())

            # resolve
            uri = self._publisher.resolve([artifact.uri])[0]

            # read
            io.read(uri, artifact, self)

            # initialise post read
            artifact.init()  # post read init

            # check
            if not artifact.is_valid():
                raise RMTCException(f"Invalid {artifact}")

    def write(self, artifacts):
        """Write out all the artifacts"""

        if not isinstance(artifacts, list):
            raise RMTCException("Require list of artifacts to write")

        # initialise if not already
        self.init(artifacts)

        # write out the artifacts
        for artifact in artifacts:

            if artifact.is_ephemeral():
                self._log.debug(f"Skipping ephemeral artifact {artifact}")
                continue

            # check
            if not artifact.is_valid():
                self._log.debug(f"Skipping invalid artifact {artifact}")
                continue

            # get IO
            io = artifact.get_io()
            if io is None:
                raise RMTCException(f"Artifact missing IO {artifact}")

            # resolve and enforce - URIs should exist before write
            uri = self._publisher.resolve([artifact.uri])[0]
            if not io.is_uri_supported(uri):
                raise RMTCException(
                    f"Unsupported URI '{uri}' on {artifact} during write"
                )
            if self.exists([uri]):
                if self.is_immutable():
                    raise RMTCException(f"URI exists '{uri}' during immutable write")
                self._log.warning(f"Overwriting '{uri}'")

            # write out the artifact
            self.prepare(uri)
            io.write(uri, artifact, self)

    def reset(self, artifacts):
        """Reset any artifact tensors"""

        if not isinstance(artifacts, list):
            raise RMTCException("Require list of artifacts to reset")

        for artifact in artifacts:
            artifact.reset()
            self._env_manager.remove_packages(artifact.get_dependencies())

    def flush(self, artifacts):
        self.write(artifacts)
        self.reset(artifacts)


class Builder(ABC):

    @abstractmethod
    def is_supported(self, artifact):
        """
        This build supports building the given artifact
        """
        return False

    @abstractmethod
    def __call__(self, asset_manager, artifact, options=None):
        """
        Run the builder against each artifact, this builds a
        publishable variant - same functionality, same provenance, different technique.
        For example: TorchPackage to TorchScript or ONNX
        """
        return artifact


class Pipeline:
    """
    Processing pipeline that holds builders
    Converts assets to other assets
    """

    def __init__(self, name, builders, log=None, description=None):
        self._log = log or Logger()
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
            for builder in self._builders:
                if builder.is_supported(artifact):
                    results = builder(asset_manager, artifact)
                    for result in results:
                        result.add_ancestors([artifact])
                    built.update(results)
        return list(built)


class AssetManager:
    """
    Helper asset manager base class
    Implements most of the interface but resolve
    """

    def __init__(
        self,
        readerwriter,
        publisher,
        log,
    ):
        if readerwriter is None:
            raise RMTCException("No readerwriter passed in")
        if publisher is None:
            raise RMTCException("No publisher passed in")

        self._readerwriter = readerwriter
        self._publisher = publisher
        self._log = log

    @property
    def log(self):
        return self._log

    @property
    def readerwriter(self):
        return self._readerwriter

    @property
    def publisher(self):
        return self._publisher

    def is_supported(self, artifact):
        return self._readerwriter.is_uri_supported(artifact.uri)

    def create_transient_uri(self, name=None):
        return self._readerwriter.create_transient_uri(name=name)

    def create_uri(self, artifact, root=None, **kwargs):
        return self._readerwriter.create_uri(artifact, root, **kwargs)

    def delete_uri(self, uri):
        return self._readerwriter.delete_uri(uri=uri)

    def identity_mode(self, mode):
        return self._readerwriter.set_identity_mode(mode)

    def manage_versions_with_publisher(self, use_for_versioning):
        if not hasattr(self._publisher, "manage_versions"):
            raise RMTCException(
                f"Publisher '{self._publisher}' does not support manage_versions()"
            )
        return self._publisher.manage_versions(use_for_versioning)

    def init(self, artifacts):
        return self._readerwriter.init(artifacts)

    def read(self, artifacts: list[Artifact], metadata: dict = None) -> bool:
        return self._readerwriter.read(artifacts, metadata=metadata)

    def write(self, artifacts: list[Artifact], **kwargs) -> bool:
        return self._readerwriter.write(artifacts)

    def reset(self, artifacts: list[Artifact]) -> bool:
        return self._readerwriter.reset(artifacts)

    def exists(self, uris: list[URI]) -> bool:
        return self._readerwriter.exists(uris)

    def resolve(self, uris):
        return self._publisher.resolve(uris)

    def resolve_inverse(self, uris):
        return self._publisher.resolve_inverse(uris)

    def publish(self, entities, **kwargs):
        return self._publisher.publish(entities, **kwargs)

    def unpublish(self, entities):
        return self._publisher.unpublish(entities)

    def is_published(self, entities):
        return self._publisher.is_published(entities)

    def is_immutable(self):
        return self._publisher.is_immutable()

    def relocate(self, entity, uri):
        return self._publisher.relocate(entity, uri)

    def reserve(self, path):
        if not hasattr(self._publisher, "reserve"):
            raise RMTCException(
                f"Publisher '{self._publisher}' does not support reserve()"
            )
        return self._publisher.reserve(path)

    def result_sources(self, entity):
        """
        The (solution, model) a weights/checkpoint was produced for, from the
        most specific source.
        """
        run = entity.parent if isinstance(entity.parent, Run) else None
        # Use model directly if it exists
        model = entity.model
        # Fallback to run's model if it exists
        if model is None and run is not None:
            model = run.model
        # Use the solution directly if it exists
        solution = entity.solution
        # Fallback to the run then model's solution if they exist
        if solution is None and run is not None:
            solution = run.solution
        if solution is None and model is not None:
            solution = model.solution
        return solution, model

    def default_name(self, entity):
        """
        Name an entity that has no user provided name.
        System installs this as a process-wide namer on Object.
        Weights and checkpoints are named for what they are trained for:
        {solution}_{model}_{category}, leaving out unknown parts.
        Facilities can override this to encode their own naming conventions
        """
        if not isinstance(entity, (Weights, Checkpoint)):
            return entity.builtin_name()

        solution, model = self.result_sources(entity)

        parts = [part.name for part in (solution, model) if part is not None]
        if not parts:
            return entity.builtin_name()
        return "_".join(parts + [entity.category().lower()])
