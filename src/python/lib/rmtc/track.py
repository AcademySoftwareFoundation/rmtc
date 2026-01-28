# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Tracking storage interface - contains all the core
entity types that we expect to store and their properties.
"""


import enum
import re

from abc import ABC, abstractmethod
from pathlib import Path

import rmtc.system
from rmtc.containers import PaddedTableIterator, IteratorIterator
from rmtc.system import Datetime, Version, URI, Package, Type, Broadcaster
from rmtc.objects import Object, IN, OUT


class EntityMessage(enum.IntEnum):

    CREATED = 0
    UPDATED = 1
    SYNCED = 2
    DELETED = 3


class Direction(enum.IntEnum):
    """Enumeration for expansion of reports"""

    INVALID = 0
    SOURCES = 1
    DERIVATIVES = 2
    BOTH = 3

    def __str__(self):
        return self.name.upper()


class Report(ABC):
    """Report structure to generate an output in a given direction"""

    def __init__(self, system, direction=Direction.SOURCES):
        self._system = system
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


class MergeType(enum.IntEnum):
    """Enumeration for entity merge strategies."""

    INVALID = 0  # Does nothing, ignore
    LATEST = 1  # Whichever was last updated
    EARLIEST = 2  # Whichever was updated earlier
    THIS = 3  # Incoming entity always overridden
    OTHER = 4  # This entity always overridden

    def __str__(self):
        return self.name.upper()


class Entity(Object, ABC):
    """
    Abstract base class for RMTC entities.

    An entity is a deferred item in the store that wraps an object.
    These are created by stores around an object which must be a
    derivation of one of the supported entity types.

    Entities provide lazy loading, synchronization tracking, and merge
    capabilities for persistent objects in the RMTC system. They maintain
    timestamps for creation and updates, and track their synchronization
    state with the underlying store.
    """

    def __init__(
        self,
        name=None,
        obj_id=None,
        project=None,
    ):
        """Initiailize"""
        super(Entity, self).__init__(name=name, obj_id=obj_id)
        self.add_property("project", str, project, required=True)

        self._store = None  # the store the id is valid for
        self._requires_create = True  # does this require creating - defaults to TRUE
        self._requires_update = False  # does this require updates
        self._requires_sync = False  # is this in sync with the DB
        self._requires_delete = False  # is this to be removed
        self._timestamp = Datetime()  # the last edit time

    @property
    def store(self):
        """Get the store managing this entity."""
        return self._store

    @property
    def timestamp(self):
        return self._timestamp

    @timestamp.setter
    def timestamp(self, value):
        self._timestamp = value

    @store.setter
    def store(self, value):
        """Set the store managing this entity."""
        self._store = value

    def property_accessed(self, prop):
        """Handle property Access, check if can JIT sync"""
        super(Entity, self).property_accessed(prop)
        if not prop.required:
            if self.requires_sync():
                if self.store and self.store.jit:
                    self.store.jit(self)

    def property_updated(self, prop):
        """Handle property change by marking entity as dirty."""
        super(Entity, self).property_updated(prop)
        self._timestamp = Datetime()
        self.mark_for_update()

    def mark_for_sync(self):
        """Mark entity for future syncing - e.g. after fetch."""
        self._requires_sync = True

    def requires_sync(self):
        """Check if entity is synchronized with store."""
        return self._requires_sync

    def reset_sync(self):
        """Reset flag to indicate synchronized with store."""
        self._requires_sync = False
        self.broadcaster(EntityMessage.SYNCED, self)

    def mark_for_delete(self):
        """Mark entity for future syncing - e.g. after fetch."""
        self._requires_delete = True

    def requires_delete(self):
        """Check if entity is synchronized with store."""
        return self._requires_delete

    def reset_delete(self):
        """Reset flag to indicate synchronized with store."""
        self._requires_delete = False
        self.broadcaster(EntityMessage.DELETED, self)

    def mark_for_update(self):
        """Mark entity for update and update Datetime."""
        self._requires_update = True

    def requires_update(self):
        """Check if entity has changes to update in the store."""
        return self._requires_update

    def reset_update(self):
        """Reset update flag, entity is updated in store."""
        self._requires_update = False
        self.broadcaster(EntityMessage.UPDATED, self)

    def mark_for_create(self):
        self._requires_create = True

    def requires_create(self):
        return self._requires_create

    def reset_create(self):
        self._requires_create = False
        self.broadcaster(EntityMessage.CREATED, self)

    def merge(self, other, strategy=MergeType.LATEST):
        """
        Merge another entity into this one.
        How do we update properties from a matching entity.
        This potentially overrides properties on the passed in item
        """
        if strategy == MergeType.LATEST:
            if other.timestamp > self.timestamp:
                for prop in other.properties:
                    self.properties[prop] = other.properties[prop].value
            self.update()
        if strategy == MergeType.EARLIEST:
            if other.timestamp < self.timestamp:
                for prop in other.properties:
                    other.properties[prop].value = self.properties[prop]
            self.update()
        if strategy == MergeType.OTHER:
            for prop in other.properties:
                self.properties[prop] = other.properties[prop].value
            self.update()
        if strategy == MergeType.THIS:
            for prop in other.properties:
                other.properties[prop].value = self.properties[prop]
            self.update()
        return self

    @property
    def class_category(self):
        """Get the string name of the entity type."""
        return self.__class__.category()

    @classmethod
    def category(cls):
        """Get the string name of the entity type."""
        return None

    def trace(self, direction, connection=None):
        """Trace up and down according to direction"""
        if direction == Direction.SOURCES:
            return self.trace_sources(connection)
        return self.trace_derivatives(connection)

    def trace_sources(self, connection):
        """
        Get source entities that this entity depends on.
        This is a combination of owned items and items that are used to
        create this entity. Anything upstream. The connection is required
        because we don't store the whole trace locally.
        """

        # sync first
        connection.sync([self])

        # pull any sources in
        ids = connection.queries.get_sources([self])
        entities = set(connection.fetch(ids))

        # update with any local data
        for prop in self.properties.values():
            if prop.is_object() and prop.is_input():
                entities.update(prop.array_value)

        return list(entities)

    def trace_derivatives(self, connection):
        """
        Get derivative entities that depend on this entity.
        Entities don't hold all the info required - e.g. a model doesn't
        know what inferences used it, but an inference knows the model.
        In those cases you do a back trace with the connection.
        """

        # sync first
        connection.sync([self])

        # pull any sources in
        ids = connection.queries.get_derivatives([self])
        entities = set(connection.fetch(ids))

        # update with any local data
        for prop in self.properties.values():
            if prop.is_object() and prop.is_output():
                entities.update(prop.array_value)

        return list(entities)

    def trace_related(self, connection):
        """
        Get source entities that this entity depends on.
        This is a combination of owned items and items that are used to
        create this entity. Anything upstream. The connection is required
        because we don't store the whole trace locally.
        """

        # sync first
        connection.sync([self])

        # pull any sources in
        ids = connection.queries.get_related([self])
        entities = set(connection.fetch(ids))

        # update with any local data
        for prop in self.properties.values():
            if prop.is_object():
                entities.update(prop.array_value)

        return list(entities)


class Connection(ABC):
    """
    Abstract base class for store connections.

    The Connection class provides the interface for interacting with
    persistent storage systems. It manages entity lifecycle operations
    including creation, updates, synchronization, and retrieval.

    Connections handle the translation between in-memory entities and
    their persistent representations, providing caching and optimization
    for database operations.
    """

    def __init__(self, store=None, queries=None):
        """Initialize the Connection with store and configuration."""
        self._store = store
        self._queries = queries
        self._store.log.debug(  # pylint: disable=no-member
            f"Created connection to: {self._store}"
        )

    def __del__(self):
        """Destructor - cleanup connections when object is destroyed."""
        self.close()

    @property
    def store(self):
        """Get the store instance for this connection."""
        return self._store

    @property
    def queries(self):
        """Get the query configuration or cache."""
        return self._queries

    @abstractmethod
    def lock(self, timeout=60000):
        pass

    @abstractmethod
    def unlock(self):
        pass

    @abstractmethod
    def create_entities(self, entities):
        """Create entities in the store."""
        return []

    @abstractmethod
    def update_entities(self, entities):
        """Update entities in the store from local DOM.
        Entity MUST exist in the store beforehand.
        """
        return False

    @abstractmethod
    def sync_entities(self, entities):
        """Update local DOM by reading entities from the store"""
        return False

    @abstractmethod
    def fetch_entities(self, ids):
        """Fetch entities by their IDs."""
        return []

    @abstractmethod
    def close(self):
        """Close the connection and release resources."""
        pass

    @abstractmethod
    def delete_all(self):
        """Delete all entities from the store."""
        pass

    @abstractmethod
    def delete_entities(self, entities):
        """Delete entities in the store."""
        pass

    def delete(self, entities):
        """Delete an entity and remove it from the store"""
        entities_to_delete = []

        # Some entities are lists
        flattened = []
        for entity in entities:
            if isinstance(entity, list):
                for sub_entity in entity:
                    flattened.append(sub_entity)
            else:
                flattened.append(entity)
        for entity in flattened:
            if not entity.requires_delete():
                continue
            if entity is None:
                continue
            if entity.store != self.store:
                continue
            entities_to_delete.append(entity)
        self.delete_entities(entities_to_delete)
        for entity in entities_to_delete:
            entity.reset_delete()
        return entities_to_delete

    def create(self, entities):
        """
        Create entities in the store with caching.

        Creates entities in the store and binds them to this store instance.
        Skips entities that already exist in the store and returns their IDs.
        """
        entities_to_create = set()
        # Some entities are lists
        flattened = []
        for entity in entities:
            if isinstance(entity, list):
                for sub_entity in entity:
                    flattened.append(sub_entity)
            else:
                flattened.append(entity)

        for entity in flattened:
            if not entity.requires_create():
                continue
            if entity is None:
                continue
            entities_to_create.add(entity)
        self.create_entities(entities_to_create)
        for entity in entities_to_create:
            entity.reset_create()
        return list(entities_to_create)

    def fetch(self, ids):
        """
        Fetch entities by IDs with caching.

        This is a partial 'READ', for later full syncing.

        Constructs partial entities from database IDs, using cached entities
        when available and fetching missing ones from the store.
        """
        entities = []
        ids_to_fetch = set()
        for obj_id in ids:
            if obj_id == 0:
                raise rmtc.system.RMTCException("No ID specified for fetch")
            entity = self.store.get_entity(obj_id)
            if entity is not None:
                entities.append(entity)
            else:
                ids_to_fetch.add(obj_id)
        new_entities = self.fetch_entities(ids_to_fetch)
        for entity in new_entities:
            entity.reset_update()
            entity.reset_create()
            entity.mark_for_sync()
        entities.extend(new_entities)
        return entities

    def update(self, entities):
        """
        Updates entities that have changes (are dirty) in the store.
        """
        entities_to_update = set()

        # Some entities are lists
        flattened = []
        for entity in entities:
            if isinstance(entity, list):
                for sub_entity in entity:
                    flattened.append(sub_entity)
            else:
                flattened.append(entity)

        for entity in flattened:
            if entity is None:
                continue
            if not entity.requires_update():
                continue
            if entity.store != self.store:
                continue
            entities_to_update.add(entity)
        if not self.update_entities(entities_to_update):
            raise rmtc.system.RMTCException(f"Failed to update {entities_to_update}")
        for entity in entities_to_update:
            entity.reset_update()
        return list(entities_to_update)

    def sync(self, entities):
        """
        Synchronize entities with complete store data.

        Equivalent to 'READ' however this clashes with reader/writer concepts.

        Reads the complete entity contents from the store and marks them
        as synchronized. Skips entities that are already synchronized.
        """
        entities_to_sync = set()

        # Some entities are lists
        flattened = []
        for entity in entities:
            if isinstance(entity, list):
                for sub_entity in entity:
                    flattened.append(sub_entity)
            else:
                flattened.append(entity)

        for entity in flattened:
            if not entity.requires_sync():
                continue
            if entity is None:
                continue
            if entity.store != self.store:
                continue
            entities_to_sync.add(entity)
        if not self.sync_entities(entities_to_sync):
            raise rmtc.system.RMTCException(f"Failed to sync {entities_to_sync}")
        for entity in entities_to_sync:
            entity.reset_sync()
        return list(entities_to_sync)

    def get_lock(self, lock_key=None):
        """
        Get a store lock.

        This is typically a lightweight atomic lock that is not intended for
        extended usage, but is instead used for short transactions. It is important
        to ensure the lock is released after use, including handling any cases where
        code may error or exit unexpectedly.
        """
        pass

    def release_lock(self, lock_key=None):
        """Release the store lock."""
        pass


class Sync(ABC):
    """
    JIT Sync is a just in time syncing strategy that delegates to a store a mechanism
    to create a pre-authorised connection so an entity can sync itself.

    This occurs if someone is accessing an entity property that is not yet pulled
    from the storage system - normally this would be invalid, however with ISync
    it is synced before accessing and the value is valid.

    HOWEVER - it is not batched, the connection is created and destroyed on access,
    it can be terribly inefficient and it is better to sync intentionally via entity
    batches. As a result it is advised to issue a warning if this is called.

    If a store does not provided a ISync delegate, then nothing happens.

    It simply is a last line of defence that creates a friendlier API.
    """

    def __init__(self, system):
        self._system = system

    def __call__(self, entity):
        self._system.pull([entity])


class StoreMessage(enum.IntEnum):

    ADDED = 0
    REMOVED = 1
    CLEARED = 2
    SYNCED = 3
    UPDATED = 4
    DELETED = 5
    FETCHED = 6


class Store(ABC):
    """
    Abstract base class for entity storage systems.

    Stores can be files or databases or sub elements of each. Names of stores
    are used to distinguish between sub storage systems.

    The Store class provides the interface for persistent storage of RMTC
    entities. It manages entity lifecycle, caching, and provides connection
    management for database operations. Stores maintain a local cache of
    entities and ensure consistency between in-memory and persistent state.
    """

    def __init__(
        self,
        name=None,
        factory=None,
        uri=None,
        log=None,
        jit=None,
        mode=rmtc.system.Mode.PRODUCTION,
    ):
        """Initialize the Store with factory, URI, and configuration."""

        # check
        if not uri or not uri.valid():
            raise rmtc.system.RMTCException(f"A store must have a valid URI, got {uri}")
        if log is None:
            raise rmtc.system.RMTCException(f"A store must have a valid Log, got {log}")
        if factory is None:
            raise rmtc.system.RMTCException(
                f"A store must have a valid Factory, got {factory}"
            )
        if len(name) == 0:
            raise rmtc.system.RMTCException(
                f"A store must have a valid name, got {name}"
            )

        # assign
        self._factory = factory
        self._entities = {}
        self._uri = uri
        self._mode = mode
        self._name = name
        self._log = log
        self._jit = jit
        self._broadcaster = Broadcaster()

    def __repr__(self):
        return f"{self.name}@{self.uri}"

    @property
    def broadcaster(self):
        return self._broadcaster

    @property
    def name(self):
        """Get the name."""
        return self._name

    @property
    def mode(self):
        """Get testing mode status."""
        return self._mode

    @property
    def uri(self):
        """Get the store URI."""
        return self._uri

    @property
    def factory(self):
        """Get the entity factory."""
        return self._factory

    @property
    def log(self):
        """Get the logger."""
        return self._log

    @property
    def jit(self):
        return self._jit

    @abstractmethod
    def connect(self, username, password):
        """Create and return connection to the store."""
        pass

    @property
    def entities(self):
        """Get the cached entities dictionary."""
        return self._entities.values()

    def get_entity(self, obj_id):
        """Get cached entity by ID."""
        if obj_id is not None:
            if obj_id in self._entities:
                return self._entities[obj_id]
        return None

    def clear(self):
        """Clear all cached entities and reset their store references."""
        for entity in self._entities.values():
            entity.store = None
        self._entities = {}
        self._broadcaster(StoreMessage.CLEARED)

    def add_entity(self, obj_id, entity):
        """Add entity to the store with the specified ID."""
        entity.obj_id = obj_id
        entity.store = self
        self._entities[entity.obj_id] = entity
        self._broadcaster(StoreMessage.ADDED, [entity])

    def remove_entity(self, entity):
        """Remove entity from store and clear its store references."""
        if entity.store is not self:
            return
        del self._entities[entity.obj_id]
        self._broadcaster(StoreMessage.REMOVED, [entity])
        entity.store = None


class Queries(ABC):
    """
    Abstract base class for database query operations.

    The Queries class provides a standardized interface for retrieving
    entities from the database using various search criteria. It supports
    querying by entity type, relationships, and properties.
    """

    def __init__(self, connection=None):
        """Initialize Queries with database connection."""
        self._connection = connection

    @property
    def connection(self):
        """Get the database connection."""
        return self._connection

    @abstractmethod
    def get_entities(self, name="", category=""):
        """Get entities by name and type filters."""
        return []

    @abstractmethod
    def get_runs(
        self,
        name=None,
        model=None,
        dataset=None,
        checkpoint=None,
        trainer=None,
        result_checkpoint=None,
        result_weights=None,
        solution=None,
    ):
        """Get training runs by various criteria."""
        return []

    @abstractmethod
    def get_models(self, name="", version="", model_license=None):
        """Get models by name, version, and license."""
        return []

    @abstractmethod
    def get_datasets(self, name="", version="", dataset_license=None):
        """Get datasets by name, version, and license."""
        return []

    @abstractmethod
    def get_solutions(self, name=""):
        """Get solutions by name pattern."""
        return []

    @abstractmethod
    def get_licenses(self, name="", version=""):
        """Get licenses by name and version patterns."""
        return []

    @abstractmethod
    def get_inferences(self, name=None, weights=None, model=None, asset=None):
        """Get inferences by weights, model, or asset."""
        return []

    @abstractmethod
    def get_assets(self, uri=None, name=None, asset_license=None, version=None):
        """Get assets by URI, name, license, and version."""
        return []

    @abstractmethod
    def get_descendents(self, entities):
        """Get the descedents that have the given entities as ancestors"""
        return []

    @abstractmethod
    def get_sources(self, entities):
        """Get any upstream entities"""
        pass

    @abstractmethod
    def get_derivatives(self, entites):
        """Get any downstream entities"""
        return []

    @abstractmethod
    def get_related(self, entities):
        """Get any related entities"""
        return []

    @abstractmethod
    def get_timestamps(self, entities):
        """Get a datetime timestamp of the last time entity was updated"""
        return []


class Tag(Entity):
    """
    Entity representing a label or category marker.

    Tags are fundamental entities owned by the store.

    Tags are not currently implemented
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


class Permission(Entity):
    """
    Entity representing a Permission
    """

    def __init__(
        self,
        name=None,
    ):
        super(Permission, self).__init__(name=name)

    @classmethod
    def category(cls):
        return "Permission"


class Trainer(Entity):
    """
    Entity representing training configuration and parameters.

    The Trainer entity encapsulates training hyperparameters and configuration
    for machine learning model training. It defines batch size, epochs,
    checkpointing intervals, and relationships to training runs.

    Each Run owns its trainer - there is a 1:1 relationship.
    """

    def __init__(
        self,
        name=None,
        project=None,
        batch_size=50,
        epochs=1000,
        checkpoint_interval=5,
        context=rmtc.system.Context.GPU,
    ):
        """Initialize the Trainer with training parameters."""
        super(Trainer, self).__init__(name=name, project=project)

        # members
        self.add_property("batch_size", int, batch_size, direction=IN)
        self.add_property("epochs", int, epochs, direction=IN)
        self.add_property("checkpoint_interval", int, checkpoint_interval, direction=IN)
        self.add_property("context", rmtc.system.Context, context)

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Trainer"


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
        project=None,
        uri=URI(),
        input_type=None,
        output_type=None,
        description=None,
    ):
        """Initialize the Solution with metadata and type specifications."""
        super(Solution, self).__init__(name=name, project=project)

        # references
        self.add_property("models", [Model], member=False, direction=IN)
        self.add_property("datasets", [Dataset], member=False, direction=IN)

        # members
        self.add_property("description", str, description, direction=OUT)
        self.add_property("uri", URI, uri, direction=OUT)
        self.add_property(
            "input_type",
            Type,
            input_type,
            default=Type(type_class=rmtc.artifacts.Asset),
            direction=OUT,
        )
        self.add_property(
            "output_type",
            Type,
            output_type,
            default=Type(type_class=rmtc.artifacts.Asset),
            direction=OUT,
        )

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Solution"


class RunStatus(enum.IntEnum):
    """Enumeration for training run execution states."""

    INVALID = 0
    READY = 1
    RUNNING = 2
    PAUSED = 3
    STOPPED = 4
    FINISHED = 5
    FAILED = 6

    def __str__(self):
        return self.name.upper()


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
        project=None,
        trainer=None,
        model=None,
        dataset=None,
        checkpoints=None,
        result_weights=None,
        result_checkpoints=None,
        solution=None,
    ):
        """Initialize the Run with training components and configuration."""
        super(Run, self).__init__(name=name, project=project)

        # references
        self.add_property("model", Model, model, member=False, direction=IN)
        self.add_property("dataset", Dataset, dataset, member=False, direction=IN)
        self.add_property(
            "checkpoints",
            [Checkpoint],
            checkpoints,
            member=False,
            direction=IN,
        )
        self.add_property("solution", Solution, solution, member=False, direction=IN)

        # members
        self.add_property("status", RunStatus)
        self.add_property("duration", float, 0.0)
        self.add_property("started", Datetime)
        self.add_property("metric", float, 1.0)
        self.add_property("epoch", int, 0)
        self.add_property(
            "trainer",
            Trainer,
            trainer,
            direction=OUT,
        )
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

        self._start_time = Datetime()
        self.init()

    def create_weights(self, object_type=None, **kwargs):
        """Construct weights, add it to the run and return"""
        if object_type is None:
            object_type = Weights
        weights = object_type(**kwargs)
        self.result_weights = weights
        return weights

    def create_checkpoint(self, object_type=None, **kwargs):
        """Construct a checkpoint, add it to the run and return"""
        if object_type is None:
            object_type = Checkpoint
        checkpoint = object_type(**kwargs)
        self.add_result_checkpoints([checkpoint])
        return checkpoint

    def create_trainer(self, object_type=None, **kwargs):
        if object_type is None:
            object_type = Trainer
        trainer = object_type(**kwargs)
        self.trainer = trainer
        return trainer

    def create_uri(self, category, name=None):
        """
        Create a URI for storing run artifacts in organized folders.

        Creates a hierarchical folder structure under the solution URI for
        organizing run outputs by category. Sanitizes names to ensure
        filesystem compatibility.
        """
        invalid_regex = r'[\+<>:"/\|?*]'
        category = re.sub(invalid_regex, "_", category)
        run_name = re.sub(invalid_regex, "_", self.name)
        artifact_folder = self.solution.uri.path / Path(run_name) / Path(category)
        artifact_folder.mkdir(parents=True, exist_ok=True)  # TODO : file assumption
        artifact_path = artifact_folder
        if name is not None:
            name = re.sub(invalid_regex, "_", name)
            artifact_path = artifact_folder / Path(name)
        return URI(
            scheme=self.solution.uri.scheme,
            host=self.solution.uri.host,
            path=artifact_path,
        )

    def init(self):
        """Initialize run state to default values."""
        self.status = RunStatus.READY
        self.metric = 0.0
        self.epoch = 0
        self.duration = 0.0
        self.result_weights = None
        self.result_checkpoint = []

    def start(self):
        """Start the training run if in READY state."""
        if self.status == RunStatus.READY:
            self.started = Datetime()
            self.status = RunStatus.RUNNING
            self._start_time = Datetime.now()

    def stop(self):
        """Stop a running or paused training run and update duration."""
        if self.status in (RunStatus.RUNNING, RunStatus.PAUSED):
            self.status = RunStatus.STOPPED
            self.duration += (Datetime.now().timestamp() * 1000) - (
                self._start_time.timestamp() * 1000.0
            )

    def resume(self):
        """Resume a paused training run."""
        if self.status == RunStatus.PAUSED:
            self.status = RunStatus.RUNNING
            self._start_time = Datetime.now()

    def pause(self):
        """Pause a running training run and update duration."""
        if self.status == RunStatus.RUNNING:
            self.status = RunStatus.PAUSED
            self.duration += (Datetime.now().timestamp() * 1000) - (
                self._start_time.timestamp() * 1000.0
            )

    def finish(self, model, weights, metric, checkpoints):
        """
        Complete the training run with results.

        Finalizes a running training run by setting the final status,
        updating duration, recording results, and adding the result
        model to the parent solution.
        """
        if self.status not in (RunStatus.FAILED, RunStatus.INVALID):
            self.status = RunStatus.FINISHED
            self.duration += (Datetime.now().timestamp() * 1000) - (
                self._start_time.timestamp() * 1000.0
            )
            self.model = model
            self.metric = metric
            self.result_weights = weights
            self.result_checkpoints = checkpoints
            if self.trainer:
                self.epoch = self.trainer.epochs

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Run"


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
        parties=None,
        start=None,
        finish=None,
        date=None,
        jurisdiction=None,
        reference=None,
        uri=None,
        permissions=None,
    ):
        """Initialize the License with terms and validity periods."""
        super(License, self).__init__(name=name)

        # references
        self.add_property(
            "permissions",
            [Permission],
            permissions,
            member=False,
            direction=OUT,
        )

        # members
        self.add_property("parties", [str], parties, direction=OUT)
        self.add_property("jurisdiction", str, jurisdiction, direction=OUT)
        self.add_property("notes", [str], direction=OUT)
        self.add_property("reference", str, reference, direction=OUT)
        self.add_property("date", Datetime, date, direction=OUT)
        self.add_property("start", Datetime, start, direction=OUT)
        self.add_property("finish", Datetime, finish, direction=OUT)
        self.add_property("uri", URI, uri, direction=IN)

        if not start:
            self.start = Datetime()
        if not finish:
            self.finish = Datetime()
        if not date:
            self.date = Datetime()

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "License"


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
        project=None,
        model=None,
        weights=None,
        inputs=None,
        result=None,
        metric=1.0,
    ):
        """Initialize the Inference with model, weights, and results."""
        super(Inference, self).__init__(name=name, project=project)

        # references
        self.add_property("model", Model, model, member=False, direction=IN)
        self.add_property("inputs", Dataset, inputs, member=False, direction=IN)
        self.add_property("weights", Weights, weights, member=False, direction=IN)

        # members
        self.add_property("metric", float, metric, direction=OUT)
        self.add_property("result", Dataset, result, member=True, direction=OUT)

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Inference"


class Artifact(Entity, ABC):
    """
    Abstract base class for versioned, licensed digital artifacts.

    The Artifact class provides a foundation for managing digital assets with
    versioning, licensing, authorship, and provenance tracking. It supports
    hierarchical relationships through ancestors. Each artifact can have an
    equiavelent variant - which are equivalent representations but differing formats
    for example a ONNX version of a PyTorch model.
    """

    def __init__(
        self,
        name=None,
        uri=None,
        version=None,
        licenses=None,
        origin=None,
        author=None,
        project=None,
        tags=None,
        env=None,
        ancestors=None,
        variants=None,
    ):
        """Initialize the Artifact with metadata and relationships."""
        super(Artifact, self).__init__(name=name, project=project)

        # references
        self.add_property("licenses", [License], licenses, member=False, direction=IN)
        self.add_property("tags", [Tag], tags, member=False, direction=IN)
        self.add_property(
            "ancestors", [Artifact], ancestors, member=False, direction=IN
        )

        # members
        self.add_property("version", Version, version, required=True, direction=IN)
        self.add_property("env", [Package], env, direction=IN)
        self.add_property("origin", str, origin, direction=OUT)
        self.add_property("author", str, author, direction=OUT)
        self.add_property("uri", URI, uri, required=True, direction=OUT)
        self.add_property("project", str, project, direction=OUT)
        self.add_property("variants", [Artifact], variants, member=True, direction=OUT)


class Resource(Artifact):

    def __init__(
        self,
        name=None,
        uri=None,
        version=None,
        licenses=None,
        project=None,
        tags=None,
        ancestors=None,
        variants=None,
    ):
        super(Resource, self).__init__(
            name=name,
            uri=uri,
            version=version,
            licenses=licenses,
            tags=tags,
            project=project,
            ancestors=ancestors,
            variants=variants,
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
    refereneced by solutions.
    """

    def __init__(
        self,
        name=None,
        project=None,
        uri=None,
        version=None,
        licenses=None,
        dataset=None,
        origin=None,
        author=None,
        input_type=None,
        output_type=None,
        env=None,
        ancestors=None,
        variants=None,
    ):
        """Initialize the Model with type specifications and metadata."""
        super(Model, self).__init__(
            name=name,
            project=project,
            uri=uri,
            version=version,
            licenses=licenses,
            origin=origin,
            author=author,
            env=env,
            ancestors=ancestors,
            variants=variants,
        )

        # references
        self.add_property("dataset", Dataset, dataset, member=False, direction=IN)

        # members
        self.add_property("metric", float, 1.0, required=True, direction=OUT)
        self.add_property(
            "input_type",
            Type,
            input_type,
            default=Type(type_class=rmtc.artifacts.Asset),
            direction=IN,
        )
        self.add_property(
            "output_type",
            Type,
            output_type,
            default=Type(type_class=rmtc.artifacts.Asset),
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
        project=None,
        uri=None,
        model=None,
        licenses=None,
        version=None,
        env=None,
    ):
        """Initialize the Checkpoint with model and run associations."""
        super(Checkpoint, self).__init__(
            name=name,
            project=project,
            uri=uri,
            licenses=licenses,
            version=version,
            env=env,
        )

        # references
        self.add_property("model", Model, model, member=False, direction=IN)

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
        project=None,
        uri=None,
        version=None,
        licenses=None,
        origin=None,
        author=None,
        model=None,
        metric=1.0,
        env=None,
    ):
        """Initialize the Weights with model association and performance metric."""
        super(Weights, self).__init__(
            name=name,
            project=project,
            uri=uri,
            version=version,
            licenses=licenses,
            origin=origin,
            author=author,
            env=env,
        )

        # references)
        self.add_property("model", Model, model, member=False, direction=IN)

        # members
        self.add_property("metric", float, metric, required=True, direction=OUT)

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
        project=None,
        items=None,
    ):
        """Initialize"""
        super(Group, self).__init__(
            name=name,
            project=project,
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
        project=None,
        uri=None,
        version=None,
        licenses=None,
        origin=None,
        author=None,
        assets=None,
        datasets=None,
        env=None,
    ):
        """Initialize the Dataset with items and metadata."""
        super(Dataset, self).__init__(
            name=name,
            project=project,
            uri=uri,
            version=version,
            licenses=licenses,
            origin=origin,
            author=author,
            env=env,
        )

        # references
        self.add_property("datasets", [Dataset], datasets, member=False, direction=IN)

        # members
        self.add_property("assets", [Asset], assets, member=True, direction=OUT)

    def __iter__(self):
        """
        Create an iterator that iterates over the assets then the datasets depth first
        Note that if there are assets - each asset row is paried with a None
        """
        dataset_iterators = []
        for dataset in self.datasets:
            dataset_iterators.append(dataset.__iter__())
        asset_iterator = PaddedTableIterator(self.assets, 1)
        return IteratorIterator([asset_iterator] + dataset_iterators)

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Dataset"


class Asset(Artifact):
    """
    Entity representing a data asset or file artifact.

    The Asset class extends Item to represent individual data files, images,
    documents, or other digital assets. Assets can be standalone or produced
    by inference operations, providing flexible data management capabilities.

    Assets are volatile during training and deleted shortly after creation,
    during inference, assest are persistant and owned by the inference.
    """

    def __init__(
        self,
        name=None,
        project=None,
        uri=None,
        version=None,
        licenses=None,
        origin=None,
        author=None,
        env=None,
    ):
        """Initialize the Asset with optional inference association."""
        super(Asset, self).__init__(
            name=name,
            project=project,
            uri=uri,
            version=version,
            licenses=licenses,
            origin=origin,
            author=author,
            env=env,
        )

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Asset"
