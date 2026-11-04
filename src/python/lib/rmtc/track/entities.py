# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Tracking storage interface - contains all the core
entity types that we expect to store and their properties.
"""


import enum

from abc import ABC, abstractmethod
from rmtc.system.containers import PaddedTableIterator, RowMajorIterator
from rmtc.system import Datetime, URI, Package, Type, Version, RMTCException
from rmtc.system.objects import IN, OUT
from rmtc.track.store import Entity


class Environment(Entity):
    """
    A collection of packages and meta info
    Allows for a named environment to be invoked rather than explict packages
    """

    def __init__(
        self,
        name=None,
        packages=None,
        identifier=None,
        timestamp=None,
    ):
        super(Environment, self).__init__(name=name)
        self.add_property("packages", [Package], packages)
        self.add_property("identifier", str, identifier, identifier)
        self.add_property("timestamp", Datetime, timestamp)

    @classmethod
    def category(cls):
        return "Environment"


class Session(Entity):
    """
    A DCC or tooling session that produces inferences.

    Permits a link back to the tool and batch up inferences for publishing.

    Session may hold multiple models & weight inferences from differing locations.

    Imagine a workflow chaining 10 models and ran 30 times, the inferences are collected
    under this session - possibly batched and written on close of the session, periodically
    or after each inference.  A realtime
    system ran 1000s of times a minute may only record the final inference on save/publish.

    The motive is to allow full context and reproducibility for inferences,
    not just prompt information, this may also require environment information
    to contextualise the tool.

    You may want to subclass Session to your own particular needs
    e.g. a periodic collection Session or a Comfy session with workflow so you can open
    it directly from within your tooling.
    """

    def __init__(
        self,
        name=None,
        inferences=None,
        packages=None,
        uri=None,
        identifier=None,
        timestamp=None,
    ):
        super(Session, self).__init__(name=name)
        self.add_property(
            "inferences", [Inference], inferences, member=False, direction=OUT
        )
        self.add_property(
            "packages", Environment, packages, member=False, direction=OUT
        )
        self.add_property("uri", URI, uri, direction=OUT)
        self.add_property("identifier", str, identifier)
        self.add_property("timestamp", Datetime, timestamp)

    @classmethod
    def category(cls):
        return "Session"


class Jurisdiction(Entity):
    """
    Representation of a jurisdiction location that is shared
    They are unique
    These would be pre-populated into the DB
    """

    def __init__(
        self,
        name=None,
    ):
        super(Jurisdiction, self).__init__(name=name)

    @classmethod
    def category(cls):
        return "Jurisdiction"


class Party(Entity):
    """
    Representation of a person or legal entity.  They are unique.
    """

    def __init__(
        self,
        name=None,
    ):
        super(Party, self).__init__(name=name)

    @classmethod
    def category(cls):
        return "Party"


class Tag(Entity):
    """
    Entity representing a label or category marker. They are unique.
    """

    def __init__(
        self,
        name=None,
    ):
        """Initialize the Tag with optional name."""
        super(Tag, self).__init__(name=name)

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Tag"


class Right(Entity):

    def __init__(
        self,
        name=None,
    ):
        super(Right, self).__init__(name=name)

    @classmethod
    def category(cls):
        return "Right"


class Filter(Entity):

    def __init__(
        self,
        name=None,
    ):
        super(Filter, self).__init__(name=name)

    @abstractmethod
    def __call__(self, entities):
        return False

    @classmethod
    def category(cls):
        return "Filter"


class Solution(Entity):
    """
    Entity representing a complete machine learning solution.

    A Solution encapsulates a complete ML workflow including models, training
    runs, input/output specifications, and metadata. It provides methods for
    finding the best performing run and managing solution components.

    It is possible to refer to a solution and have a system dynmically find
    an execute a run. The solution also holds the input/output type signature
    to provide additional semantics when marshalling data from an inferable.

    Imagine a Maya plugin using the types to setup the translation nodes, then
    on startup, pulling all runs from the solution and using the best rated.

    Solutions are fundamental entities, owned by the store.
    """

    def __init__(
        self,
        name=None,
        version=None,
        context=None,
        uri=None,
        input_names=None,
        input_types=None,
        output_names=None,
        output_types=None,
        description=None,
        externals=None,
        filters=None,
        location=None,
        origin=None,
        last_audit=None,
    ):
        """Initialize the Solution with metadata and type specifications."""
        super(Solution, self).__init__(name=name, context=context, externals=externals)

        # Filters to check if artifacts can be used in this solution
        self.add_property(
            "filters",
            [Filter],
            filters,
            member=False,
            direction=IN,
        )

        # Where this solution came from
        self.add_property(
            "location",
            Jurisdiction,
            location,
            direction=IN,
            member=False,
        )
        self.add_property(
            "origin",
            Party,
            origin,
            direction=IN,
            member=False,
        )

        self.add_property(
            "version",
            Version,
            version,
        )

        # Location to store artifacts
        self.add_property(
            "uri",
            URI,
            uri,
        )

        # Brief description
        self.add_property(
            "description",
            str,
            description,
        )

        # Model and data signature
        self.add_property(
            "input_names",
            [str],
            input_names,
        )
        self.add_property(
            "input_types",
            [Type],
            input_types,
            default=[Type(type_class=Asset)],
        )
        self.add_property(
            "output_names",
            [str],
            output_names,
        )
        self.add_property(
            "output_types",
            [Type],
            output_types,
            default=[Type(type_class=Asset)],
        )

        # Has this solution been audited for compliance
        self.add_property("last_audit", Datetime, last_audit, direction=OUT)

    def is_compliant(self, artifacts):
        """Check against the filter rules"""
        artifacts = [artifact for artifact in artifacts if artifact is not None]
        for rule in self.filters or []:
            if not rule(artifacts):
                return False
        return True

    def create_run(self, object_type=None, **kwargs):
        """Construct weights, add it to the run and return"""
        if object_type is None:
            object_type = Run
        run = object_type(**kwargs)
        run.parent = self
        run.solution = self
        return run

    def create_inference(self, object_type=None, **kwargs):
        """Construct weights, add it to the run and return"""
        if object_type is None:
            object_type = Inference
        inference = object_type(**kwargs)
        inference.parent = self
        inference.solution = self
        return inference

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Solution"


class Run(Entity):
    """
    Entity representing a machine learning training run.

    A Run encapsulates a complete training execution including inputs (models,
    datasets, checkpoints), configuration (trainer), execution state, and
    outputs (result model, weights, checkpoints). It manages the training
    lifecycle from initialization through completion and tracks metrics.

    They are owned by Solutions and own the result_weights and result_checkpoints.

    Note: input models and datasets should likely become a map of values.
    """

    def __init__(
        self,
        name=None,
        context=None,
        model=None,
        dataset=None,
        validation=None,
        test=None,
        checkpoint=None,
        result_model=None,
        result_weights=None,
        result_checkpoints=None,
        solution=None,
        externals=None,
        metric=1.0,
        epochs=0,
        uri=None,
        version=None,
    ):
        """Initialize the Run with training components and configuration."""
        super(Run, self).__init__(name=name, context=context, externals=externals)

        # references
        self.add_property("model", Model, model, member=False, direction=IN)
        self.add_property("dataset", Dataset, dataset, member=False, direction=IN)
        self.add_property("validation", Dataset, validation, member=False, direction=IN)
        self.add_property("test", Dataset, test, member=False, direction=IN)
        self.add_property(
            "checkpoint",
            Checkpoint,
            checkpoint,
            member=False,
            direction=IN,
        )
        self.add_property("solution", Solution, solution, member=False, direction=IN)
        self.add_property("version", Version, version)
        self.add_property("uri", URI, uri)  # where are things saved to

        # members
        self.add_property("metric", float, metric)
        self.add_property("epochs", int, epochs)  # how many ran epochs
        self.add_property(
            "result_checkpoints",
            [Checkpoint],
            result_checkpoints,
            member=True,
            direction=OUT,
        )
        self.add_property(
            "result_weights", Weights, result_weights, member=True, direction=OUT
        )
        self.add_property(
            "result_model", Model, result_model, member=True, direction=OUT
        )

    def create_weights(self, object_type=None, **kwargs):
        """Construct weights, add it to the run and return"""
        if object_type is None:
            object_type = Weights
        weights = object_type(**kwargs)
        weights.parent = self
        weights.metric = self.metric
        if kwargs.get("name") is None:
            weights.name = weights.default_name()
        self.result_weights = weights
        return weights

    def create_checkpoint(self, object_type=None, **kwargs):
        """Construct a checkpoint, add it to the run and return"""
        if object_type is None:
            object_type = Checkpoint
        checkpoint = object_type(**kwargs)
        checkpoint.parent = self
        checkpoint.epoch = self.epochs
        checkpoint.metric = self.metric
        if kwargs.get("name") is None:
            checkpoint.name = checkpoint.default_name()
        self.add_result_checkpoints([checkpoint])
        return checkpoint

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Run"


class LicenseStatus(enum.IntEnum):

    INVALID = 0
    ACTIVE = 1
    REVOKED = 2

    def __repr__(self):
        return self.name.upper()


class License(Entity):
    """
    Entity representing a license for data or model usage.

    The License entity encapsulates  terms, parties, validity periods,
    and jurisdictional information for licensing agreements. It tracks which
    models and datasets are governed by this license and provides derivative
    relationship queries.

    Licenses are shared and are fundamental entities owned by the store.
    """

    def __init__(
        self,
        name=None,
        version=None,
        parties=None,
        start=None,
        finish=None,
        date=None,
        jurisdictions=None,
        externals=None,
        uri=None,
        grants=None,
        excludes=None,
        requires=None,
        status=LicenseStatus.ACTIVE,
        explicit=None,
        notes=None,
    ):
        """Initialize the License with terms and validity periods."""
        super(License, self).__init__(name=name, externals=externals)

        # references
        self.add_property(
            "grants",
            [Right],
            grants,
            member=False,
            direction=IN,
        )
        self.add_property(
            "excludes",
            [Right],
            excludes,
            member=False,
            direction=IN,
        )
        self.add_property(
            "requires",
            [Right],
            requires,
            member=False,
            direction=IN,
        )

        # members
        self.add_property("version", Version, version)
        self.add_property("date", Datetime, date)
        self.add_property("start", Datetime, start)
        self.add_property("finish", Datetime, finish)
        self.add_property("revoked", Datetime, None)
        self.add_property("uri", URI, uri)
        self.add_property("status", LicenseStatus, status)
        self.add_property("notes", [str], notes)
        self.add_property("explicit", bool, explicit)
        self.add_property("parties", [Party], parties, member=False, direction=IN)
        self.add_property(
            "jurisdictions", [Jurisdiction], jurisdictions, member=False, direction=IN
        )

        if not start:
            self.start = Datetime()
        if not finish:
            self.finish = Datetime()
        if not date:
            self.date = Datetime()

    @property
    def permits(self):
        required = set(self.requires)
        granted = set(self.grants)
        return list(granted | required)

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "License"

    def is_permitted(self, rights):
        """
        Check rights list is permitted by the license
        Note: the license may grant more rights than being asked for

        2 methods for checking if rights are permitted:
        * What is not explicitly denied is implicitly allowed - permissive
        * What is not explicitly allowed is implicitly denied - restrictive

        If being explicit - all rights MUST be present in what is granted by the license
        Required rights must always be present in given rights list
        Excluded rights must always be absent from the rights list
        """

        # license must be active
        if not self.is_active():
            return False

        # an empty rights list is a valid input as it may pass
        if rights is None:
            rights = set()

        # make our list properties into sets
        rights = set(rights)
        required = set(self.requires)
        grants = set(self.grants)
        excluded = set(self.excludes)

        # rights must be expliclty granted if the license is restrictive
        if self.explicit:
            if not rights.issubset(grants):
                return False

        # all requires must be present
        if not required.issubset(rights):
            return False

        # all rights must not be in excludes
        if not rights.isdisjoint(excluded):
            return False

        # all good
        return True

    def is_valid(self):
        """Is this license a coherent valid license"""

        # time is invalid
        if self.start is not None and self.finish is not None:
            if self.start == self.finish:
                return False

        # what is granted and what is excluded must be mutally exclusive
        if not set(self.excludes).isdisjoint(set(self.requires) | set(self.grants)):
            return False

        return True

    def is_compatible(self, other_license):
        """
        A license is compatible if it doesn't permit what this license excludes

        If this license is explicit - then the other license must permit at least
        what this license permits
        """

        # licenses must be active
        if not self.is_active():
            return False
        if not other_license.is_active(location=self.location, party=self.party):
            return False

        # if this license is explict, then the other license must permit what we permit
        if self.explicit:
            if not set(self.other_license.permits).issubset(set(self.permits)):
                return False

        # requires and excludes must be mutually exclusive
        if not set(self.permits).isdisjoint(set(other_license.excludes)):
            return False
        if not set(self.excludes).isdisjoint(set(other_license.permits)):
            return False

        return True

    def within_lifetime(self, time=None):
        if time is None:
            time = Datetime()
        if self.start is not None and time < self.start:
            return False
        if self.finish is not None and time >= self.finish:
            return False
        return True

    def in_jurisdication(self, location):
        return location in self.jurisdictions

    def valid_party(self, party):
        return party in self.parties

    def is_active(self, time=None, party=None, location=None):
        """License is internally valid, not revoked, within lifetime and from this jurisdiction"""
        if not self.is_valid():
            return False
        if self.is_revoked():
            return False
        if party is not None:
            if not self.with_party(party=party):
                return False
        if location is not None:
            if not self.within_jurisdiction(location=location):
                return False
        if time is not None:
            if not self.within_lifetime(time=time):
                return False
        return True

    def is_revoked(self):
        return self.status == LicenseStatus.REVOKED

    def revoke(self, timestamp=None):
        if not self.is_revoked():
            if timestamp is None:
                timestamp = Datetime()
            self.revoked = timestamp
            self.status = LicenseStatus.REVOKED


class Inference(Entity):
    """
    Entity representing a model inference execution and results.

    The Inference entity captures the execution of a trained model on input
    data, including the model, weights used, performance metrics, and output
    results. It provides provenance tracking for inference operations.

    This is the bridge between the training sessions and the on-disk assets
    we use in production. There will likely be a large volume of these inferences.

    Inferences are fundamental entities, owned by the store.
    """

    def __init__(
        self,
        name=None,
        context=None,
        model=None,
        weights=None,
        inputs=None,
        outputs=None,
        metric=1.0,
        externals=None,
        solution=None,
    ):
        """Initialize the Inference with model, weights, and results."""
        super(Inference, self).__init__(
            name=name,
            context=context,
            externals=externals,
        )

        # references
        self.add_property("model", Model, model, member=False, direction=IN)
        self.add_property("inputs", Dataset, inputs, member=False, direction=IN)
        self.add_property("weights", Weights, weights, member=False, direction=IN)
        self.add_property("solution", Solution, solution, member=False, direction=IN)

        # members
        self.add_property("metric", float, metric, direction=OUT)
        self.add_property("outputs", Dataset, outputs, member=True, direction=OUT)

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Inference"


class Artifact(Entity, ABC):
    """
    Abstract base class for licensed digital artifacts.

    The Artifact class provides a foundation for managing digital assets with
    licensing, authorship, and provenance tracking. Artifacts are immutable -
    identity is the name plus the creation time, and an altered artifact is a
    new entity linked back through ancestors. Each artifact can have an
    equivalent variant - the same content in a differing format, for example an
    ONNX representation of a PyTorch model.
    """

    def __init__(
        self,
        name=None,
        uri=None,
        version=None,
        licenses=None,
        origin=None,
        location=None,
        author=None,
        context=None,
        tags=None,
        dependencies=None,
        ancestors=None,
        variants=None,
        externals=None,
        solution=None,
    ):
        """Initialize the Artifact with metadata and relationships."""
        super(Artifact, self).__init__(
            name=name,
            context=context,
            externals=externals,
        )

        # licenses for this artifact
        self.add_property("licenses", [License], licenses, member=False, direction=IN)

        # arbitrary tags
        self.add_property("tags", [Tag], tags, member=False, direction=IN)

        # sources for this artifact
        self.add_property(
            "ancestors", [Artifact], ancestors, member=False, direction=IN
        )

        # organisation that made this artifact - e.g WetaFX
        self.add_property("origin", Party, origin, member=False, direction=IN)

        # location where this artifact was made - e.g. NZ/WLG
        self.add_property(
            "location", Jurisdiction, location, member=False, direction=IN
        )

        self.add_property("version", Version, version, required=True, direction=IN)

        # owning solution
        self.add_property("solution", Solution, solution, member=False, direction=IN)

        # members
        self.add_property(
            "dependencies", [Package], dependencies, direction=IN
        )  # what packages this might need in the env
        self.add_property(
            "author", str, author, direction=OUT
        )  # arbitrary string for who made it
        self.add_property(
            "uri", URI, uri, required=True, direction=OUT
        )  # data location in the asset manager
        self.add_property(
            "variants", [Artifact], variants, member=True, direction=OUT
        )  # provenance equiv. versions

    def set_solution(self, solution):
        """Add artifacts only if is_compliant"""
        if solution.is_compliant([self]):
            self.solution = solution  # it points backward for scaling
            return True
        return False


class Resource(Artifact):

    def __init__(
        self,
        name=None,
        uri=None,
        version=None,
        licenses=None,
        context=None,
        tags=None,
        ancestors=None,
        variants=None,
        externals=None,
    ):
        super(Resource, self).__init__(
            name=name,
            uri=uri,
            version=version,
            licenses=licenses,
            tags=tags,
            context=context,
            ancestors=ancestors,
            variants=variants,
            externals=externals,
        )

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Resource"


class Model(Artifact):
    """
    Entity representing a machine learning model artifact.

    The Model class extends Artifact to represent ML models with input/output
    type specifications, performance metrics, and dataset associations. It
    tracks model lineage and provides queries for related training runs.

    Models are a fundamental type and owned by the store, though they can be
    referenced by solutions.
    """

    def __init__(
        self,
        name=None,
        model_id=None,
        context=None,
        uri=None,
        version=None,
        licenses=None,
        origin=None,
        author=None,
        input_names=None,
        input_types=None,
        output_names=None,
        output_types=None,
        dependencies=None,
        ancestors=None,
        variants=None,
        externals=None,
    ):
        """Initialize the Model with type specifications and metadata."""
        super(Model, self).__init__(
            name=name,
            context=context,
            uri=uri,
            version=version,
            licenses=licenses,
            origin=origin,
            author=author,
            dependencies=dependencies,
            ancestors=ancestors,
            variants=variants,
            externals=externals,
        )

        # members
        self.add_property("model_id", str, model_id, required=True, direction=OUT)
        self.add_property("metric", float, 1.0, required=True, direction=OUT)
        self.add_property(
            "input_names",
            [str],
            input_names,
            direction=IN,
        )
        self.add_property(
            "input_types",
            [Type],
            input_types,
            default=[Type(type_class=Asset)],
            direction=IN,
        )
        self.add_property(
            "output_names",
            [str],
            output_names,
            direction=IN,
        )
        self.add_property(
            "output_types",
            [Type],
            output_types,
            default=[Type(type_class=Asset)],
            direction=IN,
        )

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Model"


class Checkpoint(Artifact):
    """
    Entity representing a model checkpoint artifact.

    The Checkpoint class extends Artifact to represent saved model states
    during training. Checkpoints capture model parameters at specific points
    in training and can be used to resume training or for inference.

    Checkpoints are owned by runs.
    """

    def __init__(
        self,
        name=None,
        context=None,
        uri=None,
        model=None,
        version=None,
        licenses=None,
        dependencies=None,
        externals=None,
        metric=1.0,
        epoch=0,
    ):
        """Initialize the Checkpoint with model and run associations."""
        super(Checkpoint, self).__init__(
            name=name,
            context=context,
            uri=uri,
            version=version,
            licenses=licenses,
            dependencies=dependencies,
            externals=externals,
        )

        # externals
        self.add_property("model", Model, model, member=False, direction=IN)

        # members
        self.add_property("metric", float, metric, required=True, direction=OUT)
        self.add_property("epoch", int, epoch, direction=OUT)

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Checkpoint"


class Weights(Artifact):
    """
    Entity representing trained model weights artifact.

    The Weights class extends Artifact to represent trained neural network
    parameters or model weights. These are typically the result of training
    runs and can be loaded into models for inference or further training.

    Weights created by runs are owned by them, otherwise they are fundamental
    entities owned by the store.
    """

    def __init__(
        self,
        name=None,
        context=None,
        uri=None,
        version=None,
        licenses=None,
        origin=None,
        author=None,
        model=None,
        metric=1.0,
        epoch=0,
        dependencies=None,
        externals=None,
    ):
        """Initialize the Weights with model association and performance metric."""
        super(Weights, self).__init__(
            name=name,
            context=context,
            uri=uri,
            version=version,
            licenses=licenses,
            origin=origin,
            author=author,
            dependencies=dependencies,
            externals=externals,
        )

        # references)
        self.add_property("model", Model, model, member=False, direction=IN)

        # members
        self.add_property("metric", float, metric, required=True, direction=OUT)
        self.add_property("epoch", int, epoch, direction=OUT)

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Weights"


class Group(Entity):
    """
    A group of entities
    """

    def __init__(
        self,
        name=None,
        context=None,
        items=None,
        externals=None,
    ):
        """Initialize"""
        super(Group, self).__init__(
            name=name,
            context=context,
            externals=externals,
        )
        self.add_property("items", [Entity], items, member=False, direction=IN)

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Group"

    def __len__(self):
        return len(self.items)

    def __getitem__(self, key):
        return self.items[key]

    def __setitem__(self, key, value):
        self.items[key] = value


class Dataset(Artifact):
    """
    This is a mulitpurpose dataset class to represent a set of items
    for training or inference.

    I can be either:
    * A list of assets which it owns entirely
    * A list of references to other datasets which it pulls it's assets from
    * A URI which defers assets to a subclass, in which case the asset list is empty

    These are separate because the source & deriviatives vary depending
    on which it uses - having a flat list of polymorphic items would result
    in akward provenance tracing, where the item type would indiciate which
    direction you would trace.
    """

    def __init__(
        self,
        name=None,
        context=None,
        uri=None,
        version=None,
        licenses=None,
        origin=None,
        author=None,
        assets=None,
        datasets=None,
        dependencies=None,
        externals=None,
    ):
        """Initialize the Dataset with items and metadata."""
        super(Dataset, self).__init__(
            name=name,
            context=context,
            uri=uri,
            version=version,
            licenses=licenses,
            origin=origin,
            author=author,
            dependencies=dependencies,
            externals=externals,
        )

        # references
        self.add_property("datasets", [Dataset], datasets, member=False, direction=IN)

        # members
        self.add_property(
            "assets",
            [Asset],
            assets,
            direction=OUT,
            member=False,
        )

    def __getitem__(self, index):
        if isinstance(index, int):
            return self.assets[index]
        return super(Dataset, self).__getitem__(index)

    def __iter__(self):
        """
        Create an iterator that iterates over the assets then the datasets depth first
        Note that if there are assets - each asset row is paired with a None
        """
        dataset_iterators = []
        for dataset in self.datasets:
            dataset_iterators.append(dataset.__iter__())
        asset_iterator = PaddedTableIterator(
            self.assets, 0
        )  # need to return rows of asset lists
        return RowMajorIterator([asset_iterator] + dataset_iterators)

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Dataset"


class Watermark(Entity):
    """
    Representation of a provenance watermark embedded into an asset
    These hold arbitrary POD properties
    """

    def __init__(
        self,
        name=None,
    ):
        super(Watermark, self).__init__(name=name)
        # TODO : make entry list 'native' in some way
        self.add_property("entry_names", [str])

    def add_entry(self, name, value):
        if not value.__class__ in [str, int, float]:
            raise RMTCException(
                f"Failed to add watermark entry {name} as {value} is not a POD type"
            )
        self.add_property(name, value.__class__, value, member=True)
        self.add_entry_names([name])

    @property
    def entries(self):
        props = []
        for name in self.entry_names:
            props.append(self.properties[name])
        return props

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Watermark"


class Asset(Artifact):
    """
    Entity representing a data asset or file artifact.

    The Asset class extends Item to represent individual data files, images,
    documents, or other digital assets. Assets can be standalone or produced
    by inference operations, providing flexible data management capabilities.

    Assets are volatile during training and deleted shortly after creation,
    during inference, assest are persistant and owned by the inference.

    Note: though assets derive from artifact for the purpose of managing
    within the entity structure, they cannot be pushed or pulled from the database
    """

    def __init__(
        self,
        name=None,
        context=None,
        uri=None,
        version=None,
        licenses=None,
        origin=None,
        author=None,
        dependencies=None,
        externals=None,
        watermarks=None,
    ):
        """Initialize the Asset with optional inference association."""
        super(Asset, self).__init__(
            name=name,
            context=context,
            uri=uri,
            version=version,
            licenses=licenses,
            origin=origin,
            author=author,
            dependencies=dependencies,
            externals=externals,
        )
        self.add_property("watermarks", [Watermark], watermarks, direction=OUT)

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Asset"

    def is_tracked(self):
        """
        Assets are never pushed to the DB - we don't store Ops assets
        """
        return False
