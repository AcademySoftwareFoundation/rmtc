# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
The basic System & DOM classes, these specify how all the sub components
come together.
"""

import datetime
import enum

import rmtc.track
import rmtc.infer
import rmtc.train
import rmtc.system


class SystemMessage(enum.IntEnum):

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
    PUBLISHED = 10
    BUILT = 11
    TRAINING = 12
    INFERRING = 13


class System:
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
        objects,
        tracker,
        log,
        config,
        mode,
        credentials,
        asset_manager,
        env_manager,
        broadcaster,
        factory,
    ):
        # quick check
        if config is None:
            raise rmtc.system.RMTCException("Invalid config - can't init system")
        if objects is None:
            raise rmtc.system.RMTCException("Invalid objects - can't init system")
        if log is None:
            raise rmtc.system.RMTCException("Invalid log - can't init system")
        if mode is None:
            raise rmtc.system.RMTCException("Invalid mode - can't init system")
        if tracker is None:
            raise rmtc.system.RMTCException("Invalid tracker - can't init system")
        if store is None:
            raise rmtc.system.RMTCException("Invalid store - can't init system")
        if asset_manager is None:
            raise rmtc.system.RMTCException("Invalid asset manager - can't init system")
        if env_manager is None:
            raise rmtc.system.RMTCException("Invalid env manager - can't init system")
        if broadcaster is None:
            raise rmtc.system.RMTCException("Invalid broadcaster - can't init system")
        if factory is None:
            raise rmtc.system.RMTCException("Invalid factory - can't init system")

        # store
        self._store = store
        self._tracker = tracker
        self._config = config
        self._log = log
        self._username = credentials[0]
        self._password = credentials[1]
        self._mode = mode
        self._asset_manager = asset_manager
        self._env_manager = env_manager
        self._broadcaster = broadcaster
        self._factory = factory
        self._objects = objects

        # listen to the store and add entities to the DOM
        self._store.broadcaster.add(
            rmtc.track.StoreMessage.ADDED, lambda entities: self.add_entities(entities)
        )
        self._store.broadcaster.add(
            rmtc.track.StoreMessage.REMOVED,
            lambda entities: self.remove_entities(entities),
        )

    def __repr__(self):
        string = f"{self.__class__.__module__}.{self.__class__.__name__}\n"
        string += f" - Mode: {self.mode}\n"
        string += f" - Config: {self.config}\n"
        string += f" - Objects: {self.objects}\n"
        string += f" - Store: {self.store}\n"
        string += f" - Tracker: {self.tracker}\n"
        string += f" - Log: {self.log}\n"
        string += f" - Asset Manager: {self.asset_manager}"
        string += f" - Env Manager: {self.env_manager}"
        return string

    @property
    def broadcaster(self):
        return self._broadcaster

    @property
    def mode(self):
        """Get system mode."""
        return self._mode

    @property
    def factory(self):
        return self._factory

    @property
    def store(self):
        """Get the data store backend."""
        return self._store

    @property
    def objects(self):
        """Get the object manager."""
        return self._objects

    @property
    def tracker(self):
        """Get the tracking system."""
        return self._tracker

    @property
    def env_manager(self):
        """Get the environment configuration."""
        return self._env_manager

    @property
    def config(self):
        """Get the configuration manager."""
        return self._config

    @property
    def log(self):
        """Get the data store backend."""
        return self._log

    @property
    def asset_manager(self):
        """Get the asset manager."""
        return self._asset_manager

    def setup(self, env):
        """Set up the system environment."""
        if self._env_manager is not None:
            self._env_manager.setup(env)

    def teardown(self, env):
        """Tear down the system environment."""
        if self._env_manager is not None:
            self._env_manager.teardown(env)

    def open(self):
        """Open a connection to the data store."""
        # TODO: store a auth style token here and use that to open
        connection = self._store.connect(
            username=self._username or self._config["rmtc_store"]["username"],
            password=self._password or self._config["rmtc_store"]["password"],
        )
        if connection is None:
            raise rmtc.system.RMTCException("Unable to open connection")
        return connection

    def clear(self):
        """Clear all local DOM objects - not persistent."""
        self._objects.clear()
        self._store.clear()
        self._broadcaster(SystemMessage.CLEARED, [])

    def pull(self, entities=None):
        """Pull all objects from the data store into the DOM. Slow."""

        # get list to manage
        if entities is None:
            entities = self._objects.get()

        # create connection
        connection = self.open()
        if connection is None:
            return []
        synced = connection.sync(entities)  # syncs only marked items
        connection.close()

        # notify
        self.log.info(f"Pulled: {len(synced)} from {self._store}")
        self._broadcaster(SystemMessage.PULLED, synced)
        self._broadcaster(SystemMessage.SYNCED, synced)

        return synced

    def push(self, entities=None):
        """Push all objects to the data store. Should only push the updated data"""
        connection = self.open()
        if connection is None:
            return []
        objs = []
        if entities is None:
            objs = self._objects.get()
        else:
            objs = entities
        created = connection.create(objs)  # creates items that don't exist in store
        updated = connection.update(objs)  # updates only marked items
        deleted = connection.delete(objs)  # deletes only marked items
        pushed = list(set(created + updated + deleted))

        # remove entities from the DOM
        # TODO : should listen to the store
        self.objects.remove(deleted)

        self.log.info(f"Pushed: {len(pushed)} to {self._store}")
        connection.close()
        self._broadcaster(SystemMessage.PUSHED, pushed)
        self._broadcaster(SystemMessage.CREATED, created)
        self._broadcaster(SystemMessage.UPDATED, updated)
        self._broadcaster(SystemMessage.DELETED, deleted)

        return pushed

    def build(self, artifacts, pipeline_name=None):

        # build legit list of things to publish
        to_build = []
        for artifact in artifacts:
            if artifact is None:
                self.log.warning(f"Invalid entity in publish list {artifacts}")
                continue
            to_build.append(artifact)

        # build them
        built_artifacts = self.asset_manager.build(
            to_build, pipeline_name=pipeline_name
        )
        self.add_entities(built_artifacts)
        self.log.info(f"Built: {len(built_artifacts)}")
        self._broadcaster(SystemMessage.BUILT, built_artifacts)
        return built_artifacts

    def publish(self, artifacts, **kwargs):

        # build legit list of things to publish
        to_publish = set()
        for artifact in artifacts:
            if artifact is None:
                self.log.warning(f"Invalid entity in publish list {artifacts}")
                continue
            if artifact.requires_create():
                self.log.warning(
                    f"Unable to publish {artifact} as not yet pushed to store"
                )
                continue
            if not self.asset_manager.is_supported(artifact):
                self.log.warning(
                    f"Unable to publish {artifact} as not supported by {self.asset_manager}"
                )
                continue
            to_publish.add(artifact)

        # publish them
        published = self.asset_manager.publish(list(to_publish), **kwargs)
        self.push(list(to_publish))
        self.log.info(f"Published: {len(published)}")
        self._broadcaster(SystemMessage.PUBLISHED, published)
        return published

    def _get(self, connection, entity_ids, sync=True):
        """Fetch entities from the data store by IDs."""
        entities = connection.fetch(entity_ids)
        if sync:
            connection.sync(entities)
        self._broadcaster(SystemMessage.FETCHED, entities)
        self.add_entities(entities)
        return entities

    def trace_sources(self, entity, recurse=True, connection=None):
        """Get source entities for a given entity recursively."""
        if entity is None:
            raise rmtc.system.RMTCException("Entity is none")
        if connection is None:
            connection = self.open()
        if connection is None:
            raise rmtc.system.RMTCException("Connection is none")
        sources = entity.trace_sources(connection)
        self.add_entities(sources)
        if recurse:
            results = []
            for source in sources:
                second_sources = self.trace_sources(source, connection=connection)
                results.append(second_sources)
            return (entity, results)
        return (entity, list(sources))

    def trace_derivatives(self, entity, recurse=True, connection=None):
        """Get derivative entities for a given entity recursively."""
        if entity is None:
            raise rmtc.system.RMTCException("Entity is none")
        if connection is None:
            connection = self.open()
        if connection is None:
            raise rmtc.system.RMTCException("Connection is none")
        derivatives = entity.trace_derivatives(connection)
        self.add_entities(derivatives)
        if recurse:
            results = []
            for derivative in derivatives:
                second_derivs = self.trace_derivatives(
                    derivative, connection=connection
                )
                results.append(second_derivs)
            return (entity, results)
        return (entity, list(derivatives))

    def delete_all(self):
        """
        Erase all data from the store.

        This is a destructive operation that removes all data from the store.
        Only allowed in none-prod mode for safety.
        """
        # TODO: add privilege check
        if self.mode == rmtc.system.Mode.PRODUCTION:
            raise rmtc.system.RMTCException(
                "Failed atempt made to erase store outside testing environment"
            )
        connection = self.open()
        if connection is None:
            return False
        deleted = connection.delete_all()
        connection.close()
        self.log.warning(f"Deleted: {deleted}")
        self._broadcaster(SystemMessage.DELETED, deleted)
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
    ):
        """
        Get training runs based on specified criteria.

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
        )
        results = self._get(connection, entity_ids, sync)
        results.sort(key=lambda run: run.metric)
        connection.close()
        return results

    def get_models(self, name=None, version=None, model_license=None, sync=True):
        """Get models based on basic criteria."""
        connection = self.open()
        entity_ids = connection.queries.get_models(
            name=name, version=version, model_license=model_license
        )
        results = self._get(connection, entity_ids, sync)
        results.sort(key=lambda model: model.metric)
        connection.close()
        return results

    def get_licenses(self, name=None, version=None, sync=True):
        """Get licenses based on specified criteria."""
        connection = self.open()
        entity_ids = connection.queries.get_licenses(name=name, version=version)
        results = self._get(connection, entity_ids, sync)
        connection.close()
        return results

    def get_solutions(self, name=None, sync=True):
        """Get solutions based on specified criteria."""
        connection = self.open()
        entity_ids = connection.queries.get_solutions(
            name=name,
        )
        results = self._get(connection, entity_ids, sync)
        connection.close()
        return results

    def get_datasets(self, name=None, version=None, dataset_license=None, sync=True):
        """Get datasets based on specified criteria."""
        connection = self.open()
        entity_ids = connection.queries.get_datasets(
            name=name, version=version, dataset_license=dataset_license
        )
        results = self._get(connection, entity_ids, sync)
        connection.close()
        return results

    def get_inferences(
        self, name=None, weights=None, model=None, asset=None, sync=True
    ):
        """Get inferences based on specified criteria."""
        connection = self.open()
        entity_ids = connection.queries.get_inferences(
            name=name,
            model=model,
            weights=weights,
            asset=asset,
        )
        results = self._get(connection, entity_ids, sync)
        connection.close()
        return results

    def get_assets(self, uri=None, name=None, asset_license=None, sync=True):
        """Get assets based on specified criteria."""
        connection = self.open()
        entity_ids = connection.queries.get_assets(
            name=name, uri=uri, asset_license=asset_license
        )
        results = self._get(connection, entity_ids, sync)
        connection.close()
        return results

    def get_entities(self, name=None, category=None, ids=None, sync=True):
        """Get entities based on specified criteria."""
        connection = self.open()
        entity_ids = ids or connection.queries.get_entities(
            name=name,
            category=category,
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
        self._broadcaster(SystemMessage.ADDED, added)
        return added

    def remove_entities(self, entities):
        removed = self.objects.remove(entities)
        self._broadcaster(SystemMessage.REMOVED, removed)
        return removed

    def create_model(self, object_type=None, **kwargs):
        """
        Create and add a new model instance to the DOM.
        Passes kwargs to constructor.
        """
        if object_type is None:
            object_type = rmtc.track.Model
        if not issubclass(object_type, rmtc.track.Model):
            raise rmtc.system.RMTCException(
                f"Subclass {object_type} in create is invalid"
            )
        if not self._factory.is_registered_type_class(object_type):
            raise rmtc.system.RMTCException(f"Subclass {object_type} is not registered")

        model = object_type(**kwargs)
        self.add_entities([model])
        return model

    def create_dataset(self, object_type=None, **kwargs):
        """
        Create and add a new dataset instance to the objects store.
        Passes kwargs to constructor.
        """
        if object_type is None:
            object_type = rmtc.track.Dataset
        if not issubclass(object_type, rmtc.track.Dataset):
            raise rmtc.system.RMTCException(
                f"Subclass {object_type} in create is invalid"
            )
        if not self._factory.is_registered_type_class(object_type):
            raise rmtc.system.RMTCException(f"Subclass {object_type} is not registered")
        dataset = object_type(**kwargs)
        self.add_entities([dataset])
        return dataset

    def create_license(self, object_type=None, **kwargs):
        """
        Create and add a new license instance to the object store.
        Passes kwargs to constructor.
        """
        if object_type is None:
            object_type = rmtc.track.License
        if not issubclass(object_type, rmtc.track.License):
            raise rmtc.system.RMTCException(
                f"Subclass {object_type} in create is invalid"
            )
        if not self._factory.is_registered_type_class(object_type):
            raise rmtc.system.RMTCException(f"Subclass {object_type} is not registered")
        new_license = object_type(**kwargs)
        self.add_entities([new_license])
        return new_license

    def create_asset(self, object_type=None, **kwargs):
        if object_type is None:
            object_type = rmtc.track.Asset
        if not issubclass(object_type, rmtc.track.Asset):
            raise rmtc.system.RMTCException(
                f"Subclass {object_type} in create is invalid"
            )
        if not self._factory.is_registered_type_class(object_type):
            raise rmtc.system.RMTCException(f"Subclass {object_type} is not registered")
        new_asset = object_type(**kwargs)
        self.add_entities([new_asset])
        return new_asset

    def create_group(self, items=None):
        group = rmtc.track.Group(items=items)
        self.add_entities([group])
        return group

    def create_weights(self, object_type=None, **kwargs):
        if object_type is None:
            object_type = rmtc.track.Weights
        if not issubclass(object_type, rmtc.track.Weights):
            raise rmtc.system.RMTCException(
                f"Subclass {object_type} in create is invalid"
            )
        if not self._factory.is_registered_type_class(object_type):
            raise rmtc.system.RMTCException(f"Subclass {object_type} is not registered")
        weights = object_type(**kwargs)
        self.add_entities([weights])
        return weights

    def create_run(self, solution, object_type=None, **kwargs):
        """Create a run and add to objects"""
        if object_type is None:
            object_type = rmtc.track.Run
        if not issubclass(object_type, rmtc.track.Run):
            raise rmtc.system.RMTCException(
                f"Subclass {object_type} in create is invalid"
            )
        if not self._factory.is_registered_type_class(object_type):
            raise rmtc.system.RMTCException(f"Subclass {object_type} is not registered")
        run = object_type(**kwargs)
        run.solution = solution
        self.add_entities([run])
        return run

    def create_solution(self, object_type=None, **kwargs):
        """
        Create and add a new solution instance to the object store.
        Passes kwargs to constructor.
        """
        if object_type is None:
            object_type = rmtc.track.Solution
        if not issubclass(object_type, rmtc.track.Solution):
            raise rmtc.system.RMTCException(
                f"Subclass {object_type} in create is invalid"
            )
        if not self._factory.is_registered_type_class(object_type):
            raise rmtc.system.RMTCException(f"Subclass {object_type} is not registered")
        solution = object_type(**kwargs)
        self.add_entities([solution])
        return solution

    def create_inference(self, object_type=None, **kwargs):
        if object_type is None:
            object_type = rmtc.infer.Inference
        if not issubclass(object_type, rmtc.track.Inference):
            raise rmtc.system.RMTCException(
                f"Subclass {object_type} in create is invalid"
            )
        if not self._factory.is_registered_type_class(object_type):
            raise rmtc.system.RMTCException(f"Subclass {object_type} is not registered")
        inference = object_type(**kwargs)
        self.add_entities([inference])
        return inference

    def create_entity(self, object_type, **kwargs):
        if not issubclass(object_type, rmtc.track.Entity):
            raise rmtc.system.RMTCException(
                f"Subclass {object_type} in create is invalid"
            )
        if not self._factory.is_registered_type_class(object_type):
            raise rmtc.system.RMTCException(f"Subclass {object_type} is not registered")
        entity = object_type(**kwargs)
        self.add_entities([entity])
        return entity

    def infer(
        self,
        inferer,
        scheduler=None,
    ):
        """
        Execute inference using the provided inferer.
        This also adds the inference to the object store.
        """

        # TODO : make this work async with the scheduler
        if scheduler is not None:
            raise rmtc.system.RMTCException("Scheduler inference not implemented yet")

        # create name
        name = "Inference " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # TODO : move this to a local scheduler
        inferer.asset_manager = self.asset_manager
        inferer.env_manager = self.env_manager
        inference = inferer()
        if inference is not None:
            self.add_entities([inference])
        inference.name = name
        self.asset_manager.write([inference.result])
        self._broadcaster(SystemMessage.INFERRING, [inference])

        # return
        return inference

    def train(
        self,
        solution,
        trainer,
        model,
        dataset,
        scheduler=None,
        checkpoints=None,
    ):
        """
        Execute a training run, adds the run to the given solution and
        kicks off the training. The operation is blocking and waits until the
        scheduler has completed.
        """

        # TODO : construct a scheduler
        if scheduler is None:
            raise rmtc.system.RMTCException(
                "Scheduler free training not implemented yet"
            )

        # create name
        name = "Run " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # setup
        run = rmtc.train.Run(
            name=name,
            model=model,
            dataset=dataset,
            checkpoints=checkpoints,
            trainer=trainer,
            solution=solution,
        )
        scheduler.tracker = self.tracker
        scheduler.run = run
        scheduler.asset_manager = self.asset_manager
        scheduler.env_manager = self.env_manager

        # connect the references - the solution includes these
        solution.add_models([model])
        solution.add_datasets([dataset])
        self.add_entities([model, dataset, run])

        # TODO : make this work async
        scheduler()
        scheduler.join()

        self._broadcaster(SystemMessage.TRAINING, [run])

        # return
        return run

    def create_report(self, report, entity_names):
        report_instance = report(system=self)
        entities = []
        for name in entity_names:
            entities.extend(self.get_entities(name=name))
        return report_instance(entities)

    def get_best_run(self, solution):
        best_run = None
        runs = self.get_runs(solution=solution)
        for run in runs:
            if run.status == rmtc.track.RunStatus.FINISHED:
                if best_run is None or run.metric < best_run.metric:
                    best_run = run
        return best_run
