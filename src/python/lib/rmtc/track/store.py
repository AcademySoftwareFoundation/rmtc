# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import enum
import weakref

from abc import abstractmethod, ABC

from rmtc.system import RMTCException, Broadcaster, Datetime
from rmtc.system.objects import Object, Unlocked


class MergeType(enum.IntEnum):
    """Enumeration for entity merge strategies."""

    INVALID = 0  # Does nothing, ignore
    LATEST = 1  # Whichever was last updated
    EARLIEST = 2  # Whichever was updated earlier
    THIS = 3  # Incoming entity always overridden
    OTHER = 4  # This entity always overridden

    def __repr__(self):
        return self.name.upper()


class EntityMessage(enum.IntEnum):

    CREATED = 0
    UPDATED = 1
    SYNCED = 2
    DELETED = 3
    REQUIRES_CREATE = 4
    REQUIRES_UPDATE = 5
    REQUIRES_SYNC = 6
    REQUIRES_DELETE = 7

    def __repr__(self):
        return self.name.upper()


class Direction(enum.IntEnum):
    """Enumeration for expansion of reports"""

    INVALID = 0
    SOURCES = 1
    DERIVATIVES = 2
    BOTH = 3

    def __repr__(self):
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
        context=None,
        active=True,
        externals=None,
    ):
        """Initiailize"""
        super(Entity, self).__init__(name=name, obj_id=obj_id)
        self.add_property(
            "context",
            str,
            context,
            required=True,
        )
        self.add_property(
            "active",
            bool,
            active,
            hidden=True,
        )
        self.add_property(
            "externals",
            [str],
            externals,
            hidden=True,
        )
        self.add_property(
            "instantiated_at",
            Datetime,
            Datetime(),
            required=True,
            hidden=True,
            readonly=True,
        )

        self._store = None  # the store the id is valid for
        self._requires_create = True  # does this require creating - defaults to TRUE
        self._requires_update = False  # does this require updates
        self._requires_sync = False  # is this in sync with the DB
        self._requires_delete = False  # is this to be removed
        self._updated_at = Datetime()  # the last edit time

        # mark for creation & updating immediately
        self.mark_for_create()
        self.mark_for_update()

    def __repr__(self):
        return self.name

    @property
    def store(self):
        """Get the store managing this entity."""
        return self._store

    @property
    def updated_at(self):
        return self._updated_at

    @updated_at.setter
    def updated_at(self, value):
        self._updated_at = value

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
        self._updated_at = Datetime()
        self.mark_for_update()

    def mark_for_sync(self):
        """Mark entity for future syncing - e.g. after fetch."""
        self._requires_sync = True
        self.broadcaster(EntityMessage.REQUIRES_SYNC, self)

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
        self.broadcaster(EntityMessage.REQUIRES_DELETE, self)

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
        self.broadcaster(EntityMessage.REQUIRES_UPDATE, self)

    def requires_update(self):
        """Check if entity has changes to update in the store."""
        return self._requires_update

    def reset_update(self):
        """Reset update flag, entity is updated in store."""
        self._requires_update = False
        self.broadcaster(EntityMessage.UPDATED, self)

    def mark_for_create(self):
        """Mark entity for creation"""
        self._requires_create = True
        self.broadcaster(EntityMessage.REQUIRES_CREATE, self)

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
            if other.updated_at > self.updated_at:
                self._copy_properties(other, self)
                self.mark_for_update()
        if strategy == MergeType.EARLIEST:
            if other.updated_at < self.updated_at:
                self._copy_properties(self, other)
                other.mark_for_update()
        if strategy == MergeType.OTHER:
            self._copy_properties(other, self)
            self.mark_for_update()
        if strategy == MergeType.THIS:
            self._copy_properties(self, other)
            other.mark_for_update()
        return self

    @staticmethod
    def _copy_properties(source, target):
        """
        Copy properties from source to target.

        Uses the value setter and blocks an entity's instantiated_at identity from being copied
        """
        for name, prop in source.properties.items():
            target_prop = target.get_property(name)
            if target_prop is None or target_prop.readonly:
                continue
            target_prop.value = prop.value

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

    def duplicate(self, descendent=False):
        dupe = super(Entity, self).duplicate()

        # a duplicate is a new entity with a new obj_id - the duplicated
        # property carries the original's creation time, so re-stamp it
        with Unlocked(dupe.properties["instantiated_at"]) as prop:
            prop.value = Datetime()

        if descendent:
            dupe.add_ancestors([self])
        return dupe

    def is_tracked(self):
        """
        Should this be pushed to the DB
        """
        return True


class Proxy(Entity):

    def __init__(
        self,
        category=None,
        name=None,
        obj_id=None,
        type_name=None,
    ):
        super(Proxy, self).__init__(
            name=name,
            obj_id=obj_id,
        )
        self._category = category
        self._type_name = type_name

    def set_category(self, category):
        self._category = category

    def requires_delete(self):
        return False

    def requires_update(self):
        return False

    def requires_create(self):
        return False

    def __str__(self):
        string = super(Proxy, self).__str__()
        return f"Proxy({string})"

    @property
    def type_name(self):
        """Type name of the entity this proxy stands in for, if known"""
        return self._type_name

    @property
    def class_category(self):
        """Get the string name of the entity type."""
        return self._category or "Proxy"


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

    def __init__(self, store, queries):
        """Initialize the Connection with store and configuration."""
        self._store = store
        self._queries = queries
        self._store.log.debug(  # pylint: disable=no-member
            f"Created connection to: {self._store}"
        )

    @property
    def limit(self):
        return self._store.limit

    @property
    def timeout(self):
        return self._store.timeout

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
    def lock(self, timeout=None):
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
    def delete_all(self, store_name=None):
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
            if entity is None:
                continue
            if not entity.requires_delete():
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
            if entity is None:
                continue
            if not entity.requires_create():
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
        ids_to_fetch = []
        for obj_id in ids:
            if obj_id == 0:
                raise RMTCException("No ID specified for fetch")
            entity = self.store.get_entity(obj_id=obj_id)
            if entity is not None:
                entities.append(entity)
            else:
                ids_to_fetch.append(obj_id)
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
            raise RMTCException(f"Failed to update {entities_to_update}")
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
            if entity is None:
                continue
            if not entity.requires_sync():
                continue
            if entity.store != self.store:
                continue
            entities_to_sync.add(entity)
        if not self.sync_entities(entities_to_sync):
            raise RMTCException(f"Failed to sync {entities_to_sync}")
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
        raise NotImplementedError()

    def release_lock(self, lock_key=None):
        """Release the store lock."""
        raise NotImplementedError()


class Sync:
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

    def __init__(self, rmtc_sys):
        self._system = rmtc_sys

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

    def __repr__(self):
        return self.name.upper()


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
        name,
        factory,
        uri,
        log,
        immutable=True,
        jit=None,
        limit=None,
        timeout=None,
    ):
        """Initialize the Store with factory, URI, and configuration."""

        # check
        if not uri or not uri.is_valid():
            raise RMTCException(f"A store must have a valid URI, got {uri}")
        if log is None:
            raise RMTCException(f"A store must have a valid log, got {log}")
        if factory is None:
            raise RMTCException(f"A store must have a valid factory, got {factory}")
        if len(name) == 0:
            raise RMTCException(f"A store must have a valid name, got {name}")

        # assign
        self._entities = {}
        self._uri = uri
        self._immutable = immutable
        self._name = name
        self._jit = jit
        self._factory = factory
        self._log = log
        self._broadcaster = Broadcaster()
        self._limit = limit
        self._timeout = timeout

    def __repr__(self):
        return f"{self.name}@{self.uri}"

    @property
    def limit(self):
        return self._limit

    @property
    def timeout(self):
        return self._timeout

    @property
    def broadcaster(self):
        return self._broadcaster

    @property
    def name(self):
        """Get the name."""
        return self._name

    @property
    def uri(self):
        """Get the store URI."""
        return self._uri

    @property
    def factory(self):
        """Get the entity factory."""
        return self._factory

    @factory.setter
    def factory(self, value):
        self._factory = value

    @property
    def log(self):
        """Get the logger."""
        return self._log

    @property
    def jit(self):
        return self._jit

    @property
    def immutable(self):
        return self._immutable

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
    querying by entity type, relationships, properties, and creation window.

    Entities are identified by name plus instantiation time, and optionally by
    an explicit version. The get methods take an instantiated_at window and a
    latest flag for resolving a name to its most recent match, plus a version
    filter for exact-match lookups - the two are additive, not alternatives.
    """

    def __init__(self, connection=None):
        """Initialize Queries with database connection."""
        self._connection = weakref.proxy(connection)

    @property
    def connection(self):
        """Get the database connection."""
        return self._connection

    @abstractmethod
    def get_entities(
        self,
        name=None,
        categories=None,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Get entities by name, type and creation window."""
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
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Get training runs by various criteria."""
        return []

    @abstractmethod
    def get_models(
        self,
        name=None,
        model_license=None,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Get models by name, creation window and license."""
        return []

    @abstractmethod
    def get_datasets(
        self,
        name=None,
        dataset_license=None,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Get datasets by name, creation window and license."""
        return []

    @abstractmethod
    def get_solutions(
        self,
        name=None,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Get solutions by name and creation window."""
        return []

    @abstractmethod
    def get_licenses(
        self,
        name=None,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Get licenses by name and creation window."""
        return []

    @abstractmethod
    def get_inferences(
        self,
        name=None,
        weights=None,
        model=None,
        inputs=None,
        outputs=None,
        solution=None,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Get inferences by weights, model, inputs or outputs."""
        return []

    @abstractmethod
    def get_assets(
        self,
        uri=None,
        name=None,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Get assets by URI, name and creation window."""
        return []

    @abstractmethod
    def get_descendents(self, entities, limit=None):
        """Get the descedents that have the given entities as ancestors"""
        return []

    @abstractmethod
    def get_sources(self, entities, limit=None):
        """Get any upstream entities"""
        pass

    @abstractmethod
    def get_derivatives(self, entities, limit=None):
        """Get any downstream entities"""
        return []

    @abstractmethod
    def get_related(self, entities, limit=None):
        """Get any related entities"""
        return []

    @abstractmethod
    def get_timestamps(self, entities):
        """Get a datetime timestamp of the last time entity was updated"""
        return []

    @abstractmethod
    def get_recent_inference(self, solution):
        """Return the last chronological inference"""
        return None

    @abstractmethod
    def get_recent_run(self, solution):
        """Return the last chronological run"""
        return None

    @abstractmethod
    def get_best_run(self, solution):
        """Return the run with the lowset metric"""
        return None
