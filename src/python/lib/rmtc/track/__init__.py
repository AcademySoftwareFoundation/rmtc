# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
The basic System & DOM classes, these specify how all the sub components
come together.
"""

import enum

from rmtc.track.entities import (
    Jurisdiction,
    Party,
    Right,
    Session,
    Model,
    Resource,
    Dataset,
    License,
    Asset,
    Weights,
    Checkpoint,
    Run,
    Solution,
    Inference,
    Group,
)
from rmtc.track.store import StoreMessage
from rmtc.system import RMTCException, Broadcaster


class TrackingMessage(enum.IntEnum):

    CLEARED = 0
    PULLED = 1
    PUSHED = 2
    SYNCED = 3
    DELETED = 4
    FETCHED = 5
    CREATED = 6
    UPDATED = 7
    ADDED = 8
    REMOVED = 9


class Tracking:
    """
    This class provides the primary entry point for RMTC and abstracts some of the
    processes for training, inference and storage.

    It manages connections to data stores and provides methods for database operations
    on various entity types.

    The storage system has been abstracted, some elements like password & user may
    not be applicable for all classes of storage (e.g. a file)
    """

    def __init__(
        self,
        store,
        credentials,
        objects,
        factory,
        log,
        jurisdiction=None,
        party=None,
        tracer=None,
        asset_manager=None,
        publisher=None,
        watermarkers=None,
        filters=None,
    ):
        # quick check for essentials required to run at all
        if log is None:
            raise RMTCException("Invalid log - can't init")
        if store is None:
            raise RMTCException("Invalid store - can't init system")
        if len(credentials) != 2:
            raise RMTCException("Invalid credentials - can't init")
        if objects is None:
            raise RMTCException("Invalid objects - can't init")
        if factory is None:
            raise RMTCException("Invalid factory - can't init")

        # optionals - warn if missing as some functionality will be invalid
        if asset_manager is None:
            log.warning("Invalid asset manager")
        if publisher is None:
            log.warning("Invalid publisher")
        if party is None:
            log.warning("Invalid party")
        if tracer is None:
            log.warning("Invalid tracer")
        if watermarkers is None:
            log.warning("Invalid watermarkers")
        if filters is None:
            log.warning("Invalid filters")

        # store
        self._asset_manager = asset_manager
        self._publisher = publisher
        self._tracer = tracer
        self._store = store
        self._username = credentials[0]
        self._password = credentials[1]
        self._log = log
        self._factory = factory
        self._objects = objects
        self._watermarkers = watermarkers or []
        self._filters = filters or []
        self._jurisdiction = jurisdiction  # where this tracking instance is invoked
        self._party = party  # which organisation invoked this tracking instance
        self._broadcaster = Broadcaster()

        # listen to the store and add entities to the DOM
        self._store.broadcaster.add(
            StoreMessage.ADDED,
            lambda entities: self.add_entities(entities),
        )
        self._store.broadcaster.add(
            StoreMessage.REMOVED,
            lambda entities: self.remove_entities(entities),
        )

    def is_valid(self):
        if not self._username or len(self._username) == 0:
            return False
        if not self._password or len(self._password) == 0:
            return False
        try:
            if self.open() is None:
                return False
        except Exception as ex:  # pylint: disable=broad-exception-caught
            self._log.debug(ex)
            return False
        return True

    @property
    def credentials(self):
        return (self._username, None)

    @credentials.setter
    def credentials(self, value):
        self._username = value[0]
        self._password = value[1]

    @property
    def has_credentials(self):
        return self._username is not None and self._password is not None

    @property
    def mode(self):
        return self._mode

    @property
    def factory(self):
        return self._factory

    @property
    def tracer(self):
        return self._tracer

    @property
    def store(self):
        return self._store

    @property
    def objects(self):
        return self._objects

    @property
    def log(self):
        return self._log

    @property
    def broadcaster(self):
        return self._broadcaster

    @property
    def publisher(self):
        return self._publisher

    def watermark(self, entities):
        for watermark in self._watermarkers:
            if watermark.is_supported(entities):
                watermark(entities)
        return True

    def open(self):
        """Open a connection to the data store."""
        # TODO: store a auth style token here and use that to open
        connection = self._store.connect(
            username=self._username,
            password=self._password,
        )
        if connection is None:
            raise RMTCException("Unable to open connection")
        return connection

    def clear(self):
        """Clear all local DOM objects - not persistent."""
        self._objects.clear()
        self._store.clear()
        self._broadcaster(TrackingMessage.CLEARED, [])

    def pull(self, entities=None, force=False):
        """Pull all objects from the data store into the DOM. Slow."""

        # TODO: need to check if DB has an updated, force ALWAYS syncs

        # get list to manage
        objs = []
        if entities is None:
            # collect all the entities and recurse down the tree
            objs = self._objects.get(recurse=True)
        else:
            objs = entities
        if force:
            for entity in objs:
                entity.mark_for_sync()

        # create connection
        connection = self.open()
        if connection is None:
            return []
        synced = connection.sync(objs)  # syncs only marked items
        connection.close()

        # filter for non-tracked entities
        objs = [entity for entity in objs if entity.is_tracked()]

        # notify
        if len(synced) > 0:
            self.log.info(f"Pulled: {len(synced)}")
            self.log.debug(f"Entities pulled: {synced}")
        self._broadcaster(TrackingMessage.PULLED, synced)
        self._broadcaster(TrackingMessage.SYNCED, synced)

        return synced

    def push(self, entities=None, force=False):
        """Push all objects to the data store. Should only push the updated data"""

        # create a connection
        connection = self.open()
        if connection is None:
            return []
        objs = []
        if entities is None:
            # collect all the entities and recurse down the tree
            objs = self._objects.get(recurse=True)
        else:
            objs = entities
        if force:
            for entity in objs:
                entity.mark_for_update()

        # filter for non-tracked entities
        objs = [entity for entity in objs if entity.is_tracked()]

        # do it
        created = connection.create(objs)  # creates items that don't exist in store
        updated = connection.update(objs)  # updates only marked items
        deleted = connection.delete(objs)  # deletes only marked items

        # remove entities from the DOM
        self.objects.remove(deleted)
        connection.close()

        # log & broadcast
        pushed = list(set(created + updated + deleted))
        if len(pushed) > 0:
            self.log.info(f"Pushed: {len(pushed)}")
            self.log.debug(f"Entities pushed: {pushed}")
        self._broadcaster(TrackingMessage.PUSHED, pushed)
        self._broadcaster(TrackingMessage.CREATED, created)
        self._broadcaster(TrackingMessage.UPDATED, updated)
        self._broadcaster(TrackingMessage.DELETED, deleted)

        return pushed

    def _get(self, connection, entity_ids, sync=True):
        """Fetch entities from the data store by IDs."""
        entities = connection.fetch(entity_ids)
        if sync:
            connection.sync(entities)
        self._broadcaster(TrackingMessage.FETCHED, entities)
        self.add_entities(entities)
        return entities

    def trace_report(self, report, entities):
        report_instance = report(rmtc_system=self)
        return report_instance(entities)

    def trace_sources(self, entity, recurse=True):
        """Get source entities for a given entity recursively."""
        if entity is None:
            raise RMTCException("Entity is none")
        connection = self.open()
        if connection is None:
            raise RMTCException("Connection is none")
        results = self._trace_sources(
            entity=entity, recurse=recurse, connection=connection
        )
        connection.close()
        return results

    def _trace_sources(self, entity, recurse=True, connection=None):
        """Get source entities for a given entity recursively."""
        if entity is None:
            raise RMTCException("Entity is none")
        if connection is None:
            raise RMTCException("Connection is none")

        # get list of derivatives
        entities = entity.trace_sources(connection)

        # add to session
        self.add_entities(entities)

        # recurse
        sources = []
        if recurse:
            for child in entities:
                sources.append(
                    self._trace_sources(
                        entity=child,
                        connection=connection,
                    )
                )
        else:
            sources = [(child, []) for child in entities]

        return (entity, sources)

    def trace_derivatives(self, entity, recurse=True):
        """Get source entities for a given entity recursively."""
        if entity is None:
            raise RMTCException("Entity is none")
        connection = self.open()
        if connection is None:
            raise RMTCException("Connection is none")
        results = self._trace_derivatives(
            entity=entity, recurse=recurse, connection=connection
        )
        connection.close()
        return results

    def _trace_derivatives(self, entity, recurse=True, connection=None):
        """Get derivative entities for a given entity recursively."""
        if entity is None:
            raise RMTCException("Entity is none")
        if connection is None:
            raise RMTCException("Connection is none")

        # get list of derivatives
        entities = entity.trace_derivatives(connection)

        # add to session
        self.add_entities(entities)

        # recurse
        derivatives = []
        if recurse:
            for child in entities:
                derivatives.append(
                    self._trace_derivatives(
                        entity=child,
                        connection=connection,
                    )
                )
        else:
            derivatives = [(child, []) for child in entities]

        return (entity, derivatives)

    def delete_all(self, store_name=None):
        """
        Erase all data from the store.

        This is a destructive operation that removes all data from the store.
        Only allowed in none-prod mode for safety.
        """
        if self.store.immutable:
            raise RMTCException("Failed attempt made to erase immutable store")
        connection = self.open()
        if connection is None:
            return False
        deleted = connection.delete_all(store_name=store_name)
        connection.close()
        self.log.warning(f"Deleted: {deleted}")
        self._broadcaster(TrackingMessage.DELETED, deleted)
        self.clear()
        return True

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
        sync=True,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """
        Get training runs based on specified criteria.

        Runs are matched by name, creation window and relationships. Setting
        latest returns only the most recently created match.

        Note that run connections are directed to the most common object
        this means that a weights file points to the model, not the other way
        around, even though you could consider a weights object to be a derivative
        of a model.
        """
        connection = self.open()
        entity_ids = connection.queries.get_runs(
            name=name,
            model=model,
            trainer=trainer,
            dataset=dataset,
            checkpoint=checkpoint,
            result_checkpoint=result_checkpoint,
            result_weights=result_weights,
            solution=solution,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )
        results = self._get(connection, entity_ids, sync)
        # the query returns newest first - only re-rank by metric when the
        # caller asked for a range rather than a single most recent result
        if not latest:
            results.sort(key=lambda run: run.metric)
        connection.close()
        return results

    def get_models(
        self,
        name=None,
        model_license=None,
        sync=True,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Get models based on basic criteria."""
        connection = self.open()
        entity_ids = connection.queries.get_models(
            name=name,
            model_license=model_license,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )
        results = self._get(connection, entity_ids, sync)
        if not latest:
            results.sort(key=lambda model: model.metric)
        connection.close()
        return results

    def get_licenses(
        self,
        name=None,
        sync=True,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Get licenses based on specified criteria."""
        connection = self.open()
        entity_ids = connection.queries.get_licenses(
            name=name,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )
        results = self._get(connection, entity_ids, sync)
        connection.close()
        return results

    def get_solutions(
        self,
        name=None,
        sync=True,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Get solutions based on specified criteria."""
        connection = self.open()
        entity_ids = connection.queries.get_solutions(
            name=name,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )
        results = self._get(connection, entity_ids, sync)
        connection.close()
        return results

    def get_datasets(
        self,
        name=None,
        dataset_license=None,
        sync=True,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Get datasets based on specified criteria."""
        connection = self.open()
        entity_ids = connection.queries.get_datasets(
            name=name,
            dataset_license=dataset_license,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )
        results = self._get(connection, entity_ids, sync)
        connection.close()
        return results

    def get_inferences(
        self,
        name=None,
        weights=None,
        model=None,
        inputs=None,
        outputs=None,
        solution=None,
        sync=True,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Get inferences based on specified criteria."""
        connection = self.open()
        entity_ids = connection.queries.get_inferences(
            name=name,
            model=model,
            weights=weights,
            inputs=inputs,
            outputs=outputs,
            solution=solution,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )
        results = self._get(connection, entity_ids, sync)
        connection.close()
        return results

    def get_assets(
        self,
        uri=None,
        name=None,
        sync=True,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Get assets based on specified criteria."""
        connection = self.open()
        entity_ids = connection.queries.get_assets(
            name=name,
            uri=uri,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )
        results = self._get(connection, entity_ids, sync)
        connection.close()
        return results

    def get_entity(
        self,
        name=None,
        category=None,
        obj_id=None,
        sync=True,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
    ):
        """
        Get a single entity based on specified criteria.

        Results come back newest first, so without an obj_id this resolves a
        name to the most recently created match.
        """
        ids = [obj_id] if obj_id is not None else None
        results = self.get_entities(
            name=name,
            categories=[category],
            obj_ids=ids,
            sync=sync,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
        )
        if len(results) > 0:
            return results[0]
        return None

    def get_entities(
        self,
        name=None,
        categories=None,
        obj_ids=None,
        sync=True,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Get entities based on specified criteria."""
        connection = self.open()
        entity_ids = obj_ids or connection.queries.get_entities(
            name=name,
            categories=categories,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )
        results = self._get(connection, entity_ids, sync)
        connection.close()
        return results

    def get_descendents(self, entities, sync=True):
        """Get entities based on specified criteria."""
        connection = self.open()
        entity_ids = connection.queries.get_descendents(
            entities=entities,
        )
        results = self._get(connection, entity_ids, sync)
        connection.close()
        return results

    def add_entities(self, entities):
        added = self.objects.add(entities)
        self._broadcaster(TrackingMessage.ADDED, added)
        return added

    def remove_entities(self, entities):
        removed = self.objects.remove(entities)
        self._broadcaster(TrackingMessage.REMOVED, removed)
        return removed

    def create_model(self, object_type=None, **kwargs):
        """
        Create and add a new model instance to the DOM.
        Passes kwargs to constructor.
        """
        if object_type is None:
            object_type = Model
        if not issubclass(object_type, Model):
            raise RMTCException(f"Subclass {object_type} in create is invalid")
        if not self._factory.is_registered_type_class(object_type):
            raise RMTCException(f"Subclass {object_type} is not registered")

        model = object_type(**kwargs)
        self.add_entities([model])
        return model

    def create_dataset(self, object_type=None, **kwargs):
        """
        Create and add a new dataset instance to the objects store.
        Passes kwargs to constructor.
        """
        if object_type is None:
            object_type = Dataset
        if not issubclass(object_type, Dataset):
            raise RMTCException(f"Subclass {object_type} in create is invalid")
        if not self._factory.is_registered_type_class(object_type):
            raise RMTCException(f"Subclass {object_type} is not registered")
        dataset = object_type(**kwargs)
        self.add_entities([dataset])
        return dataset

    def create_resource(self, object_type=None, **kwargs):
        """
        Create and add a new resource instance to the object store.
        Passes kwargs to constructor.
        """
        if object_type is None:
            object_type = Resource
        if not issubclass(object_type, Resource):
            raise RMTCException(f"Subclass {object_type} in create is invalid")
        if not self._factory.is_registered_type_class(object_type):
            raise RMTCException(f"Subclass {object_type} is not registered")
        new_resource = object_type(**kwargs)
        self.add_entities([new_resource])
        return new_resource

    def create_license(self, object_type=None, **kwargs):
        """
        Create and add a new license instance to the object store.
        Passes kwargs to constructor.
        """
        if object_type is None:
            object_type = License
        if not issubclass(object_type, License):
            raise RMTCException(f"Subclass {object_type} in create is invalid")
        if not self._factory.is_registered_type_class(object_type):
            raise RMTCException(f"Subclass {object_type} is not registered")
        new_license = object_type(**kwargs)
        self.add_entities([new_license])
        return new_license

    def create_asset(self, object_type=None, **kwargs):
        if object_type is None:
            object_type = Asset
        if not issubclass(object_type, Asset):
            raise RMTCException(f"Subclass {object_type} in create is invalid")
        if not self._factory.is_registered_type_class(object_type):
            raise RMTCException(f"Subclass {object_type} is not registered")
        new_asset = object_type(**kwargs)
        self.add_entities([new_asset])
        return new_asset

    def create_weights(self, object_type=None, run=None, **kwargs):
        if object_type is None:
            object_type = Weights
        if not issubclass(object_type, Weights):
            raise RMTCException(f"Subclass {object_type} in create is invalid")
        if not self._factory.is_registered_type_class(object_type):
            raise RMTCException(f"Subclass {object_type} is not registered")
        weights = None
        if run is not None:
            weights = run.create_weights(object_type, **kwargs)
        else:
            weights = object_type(**kwargs)
            if kwargs.get("name") is None:
                weights.name = weights.default_name()
        self.add_entities([weights])

        return weights

    def create_checkpoint(self, object_type=None, run=None, **kwargs):
        if object_type is None:
            object_type = Checkpoint
        if not issubclass(object_type, Checkpoint):
            raise RMTCException(f"Subclass {object_type} in create is invalid")
        if not self._factory.is_registered_type_class(object_type):
            raise RMTCException(f"Subclass {object_type} is not registered")
        checkpoint = None
        if run is not None:
            checkpoint = run.create_checkpoint(object_type, **kwargs)
        else:
            checkpoint = object_type(**kwargs)
            if kwargs.get("name") is None:
                checkpoint.name = checkpoint.default_name()
        self.add_entities([checkpoint])

        return checkpoint

    def create_run(self, object_type=None, solution=None, **kwargs):
        """Create a run and add to objects"""
        if object_type is None:
            object_type = Run
        if not issubclass(object_type, Run):
            raise RMTCException(f"Subclass {object_type} in create is invalid")
        if not self._factory.is_registered_type_class(object_type):
            raise RMTCException(f"Subclass {object_type} is not registered")
        if solution is not None:
            run = solution.create_run(object_type, **kwargs)
        else:
            run = object_type(**kwargs)
        self.add_entities([run])
        return run

    def create_solution(self, object_type=None, **kwargs):
        """
        Create and add a new solution instance to the object store.
        Passes kwargs to constructor.
        """
        if object_type is None:
            object_type = Solution
        if not issubclass(object_type, Solution):
            raise RMTCException(f"Subclass {object_type} in create is invalid")
        if not self._factory.is_registered_type_class(object_type):
            raise RMTCException(f"Subclass {object_type} is not registered")
        solution = object_type(
            origin=self._party, location=self._jurisdiction, **kwargs
        )
        if solution is not None:
            solution.add_filters(self._filters)
        self.add_entities([solution])
        return solution

    def create_inference(self, object_type=None, solution=None, session=None, **kwargs):
        if object_type is None:
            object_type = Inference
        if not issubclass(object_type, Inference):
            raise RMTCException(f"Subclass {object_type} in create is invalid")
        if not self._factory.is_registered_type_class(object_type):
            raise RMTCException(f"Subclass {object_type} is not registered")
        if solution is not None:
            inference = solution.create_inference(object_type, **kwargs)
        else:
            inference = object_type(**kwargs)
        self.add_entities([inference])
        return inference

    def create_entity(self, type_name, **kwargs):
        if not self._factory.is_registered_type_name(type_name):
            raise RMTCException(f"Subclass {type_name} is not registered")
        entity = self._factory.create(type_name, **kwargs)
        self.add_entities([entity])
        return entity

    def create_group(self, **kwargs):
        group = Group(**kwargs)
        self.add_entities([group])
        return group

    def get_create(self, object_type, name, **kwargs):
        """Get the named item in it's category first, then create if not found"""
        entities = self.get_entities(
            categories=[object_type.category()], name=name, exact=True
        )
        if entities:
            return entities[0]
        entity = object_type(name=name, **kwargs)
        self.add_entities([entity])
        return entity

    def create_rights(self, name, **kwargs):
        """Create rights - must be unique"""
        entities = self.get_entities(
            categories=["Right"], name=name, exact=True, sync=False
        )
        if entities:
            raise RMTCException(f"Right {name} exists")
        right = Right(name=name, **kwargs)
        self.add_entities([right])
        return right

    def create_party(self, name):
        """Create a party - must be unique"""
        entities = self.get_entities(
            categories=["Party"], name=name, exact=True, sync=False
        )
        if entities:
            raise RMTCException(f"Party {name} exists")
        party = Party(name=name)
        self.add_entities([party])
        return party

    def create_jurisdiction(self, name):
        """Create a shared jurisdiction entry - must be unique"""
        entities = self.get_entities(
            categories=["Jurisdiction"], name=name, exact=True, sync=False
        )
        if entities:
            raise RMTCException(f"Jurisdition {name} exists")
        jurisdiction = Jurisdiction(name=name)
        self.add_entities([jurisdiction])
        return jurisdiction

    def create_session(self, object_type=None, **kwargs):
        if object_type is None:
            object_type = Session
        if not issubclass(object_type, Session):
            raise RMTCException(f"Subclass {object_type} in create is invalid")
        if not self._factory.is_registered_type_class(object_type):
            raise RMTCException(f"Subclass {object_type} is not registered")
        session = object_type(**kwargs)
        self.add_entities([session])
        return session

    def get_best_run(self, solution):
        connection = self.open()
        if connection is None:
            return None
        run_id = connection.queries.get_best_run(solution=solution)
        if run_id is not None:
            return self.get_entities(obj_ids=[run_id])[0]
        return None

    def publish(self, entities, **kwargs):

        # TODO: this needs to be a task to be scheduled

        # build legit list of things to publish
        to_publish = set()
        for entity in entities:
            if entity is None:
                self._log.warning(f"Invalid entity in publish list {entities}")
                continue
            if entity.requires_create():
                self._log.warning(
                    f"Unable to publish {entity} as not yet pushed to store"
                )
                continue
            if not self._publisher.is_supported([entity]):
                self._log.warning(
                    f"Unable to publish {entity} as not supported by {self._publisher}"
                )
                continue
            to_publish.add(entity)

        # publish them
        published = self._asset_manager.publish(list(to_publish), **kwargs)
        self.push(published)
        self._log.info(f"Published: {len(published)}")

        return published
