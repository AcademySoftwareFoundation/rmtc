# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import os

from rmtc.interface import Client
from rmtc.track import Tracking
from rmtc.ops import Operations
from rmtc.system import (
    URI,
    LogLevel,
    Mode,
    Broadcaster,
    Logger,
    Config,
    Factory,
    Version,
    TypeName,
    RMTCException,
)
from rmtc.system.objects import Object
from rmtc.ops.pipeline import Pipeline
from rmtc.ops.scheduling import Scheduler


class System(Client):
    """
    RMTC Core system implementation with AGE database and TensorBoard integration.

    The System class extends the base RMTC System to provide a complete ML tracking
    and collaboration system with AGE graph database storage, TensorBoard experiment
    tracking, and configuration management. It automatically configures components
    from the system configuration file and provides a unified interface for ML
    workflow management.
    """

    def __init__(
        self,
        config=None,
        store=None,
        tracker=None,
        objects=None,
        log=None,
        jit=None,
        publisher=None,
        readerwriter=None,
        asset_manager=None,
        tracer=None,
        watermarkers=None,
        env_manager=None,
        factory=None,
        pipelines=None,
        credentials=None,
        filters=None,
        party=None,
        jurisdiction=None,
    ):
        # Create event system
        self._broadcaster = Broadcaster()

        # Query version
        try:
            self._version = Version(os.getenv("RMTC_VERSION", "0.0.0"))
        except:  # pylint: disable=bare-except
            self._version = Version("0.0.0")

        # Create a config
        config = config or Config()
        self._config = config

        # Create log for initialising subsystems
        if log is None:
            log = Logger()
            log_config = config["rmtc_log"]
            if log_config:
                level = LogLevel[log_config["level"]]
                log.set_level(level)
        self._log = log

        # log now
        log.info(f"Loaded config {self._config.path}")

        # Create a factory - key
        if factory is None:
            factory = Factory(log=log)
        self._factory = factory

        # Basic System init
        self._mode = Mode.PRODUCTION
        system_config = config["rmtc_system"]
        if system_config:
            self._mode = Mode[system_config["mode"]]

        # Get password and username for env if not passed in
        if credentials is None:
            credentials = (os.getenv("RMTC_USER"), os.getenv("RMTC_PW"))
        if credentials[0] is None or credentials[1] is None:
            raise RMTCException("No credentials")

        # JIT sync
        if jit is None and config["rmtc_jit"]:
            jit = self._construct(
                config["rmtc_jit"],
                rmtc_sys=self,
            )

        # Default tracker
        if tracker is None and config["rmtc_tracker"]:
            tracker = self._construct(
                config["rmtc_tracker"],
                log=log,
            )

        # Store config
        if store is None and config["rmtc_store"]:
            store = self._construct(
                config["rmtc_store"],
                factory=factory,
                log=log,
                jit=jit,
            )

        # General dependency eco system
        if env_manager is None and config["rmtc_env_manager"]:
            env_manager = self._construct(
                config["rmtc_env_manager"],
                log=log,
            )

        # Publisher manager
        if publisher is None and config["rmtc_publisher"]:
            publisher = self._construct(
                config["rmtc_publisher"],
                log=log,
            )

        # Pipeline tracer
        if tracer is None and config["rmtc_tracer"]:
            tracer = self._construct(
                config["rmtc_tracer"],
                log=log,
            )

        # Add the watermarkers
        if watermarkers is None and config["rmtc_watermarkers"]:
            watermarkers_config = config["rmtc_watermarkers"]
            watermarkers = []
            for watermarker_config in watermarkers_config:
                watermarker = self._construct(
                    watermarker_config,
                )
                watermarkers.append(watermarker)

        # File manager
        if readerwriter is None and config["rmtc_readerwriter"]:
            readerwriter = self._construct(
                config["rmtc_readerwriter"],
                log=log,
                env_manager=env_manager,
                publisher=publisher,
            )

        # Add the pipelines
        if pipelines is None and config["rmtc_pipelines"]:
            pipelines_config = config["rmtc_pipelines"]
            pipelines = []
            for name in pipelines_config:
                builders = []
                for builder_config in pipelines_config[name]:
                    builder = self._construct(
                        builder_config,
                    )
                    builders.append(builder)
                pipeline = Pipeline(
                    name=name,
                    builders=builders,
                    log=log,
                )
                pipelines.append(pipeline)

        # Asset manager - file readwrite & publishing
        if asset_manager is None and config["rmtc_asset_manager"]:
            asset_manager = self._construct(
                config["rmtc_asset_manager"],
                log=log,
                publisher=publisher,
                readerwriter=readerwriter,
            )

        # Simple DOM store
        if objects is None and config["rmtc_objects"]:
            objects = self._construct(config["rmtc_objects"])
        self._objects = objects

        # Add tracking filters
        if filters is None and config["rmtc_filters"]:
            filters_config = config["rmtc_filters"]
            filters = []
            for filter_config in filters_config:
                new_filter = self._construct(
                    filter_config,
                )
                filters.append(new_filter)

        # Create the tracking subsystem
        self._track = Tracking(
            store=store,
            asset_manager=asset_manager,
            publisher=publisher,
            watermarkers=watermarkers,
            tracer=tracer,
            objects=objects,
            credentials=credentials,
            log=log,
            factory=factory,
            filters=filters,
            party=party,
            jurisdiction=jurisdiction,
        )

        # Create the operations subsystem on top of the tracker
        self._ops = Operations(
            tracking=self._track,
            tracker=tracker,
            asset_manager=asset_manager,
            pipelines=pipelines,
            env_manager=env_manager,
            log=log,
        )

        # Install a process-wide namer for naming convention overrides on all objects
        Object.set_namer(
            asset_manager.default_name if asset_manager is not None else None
        )

        # Startup
        self.log.info(
            f"Rongotai Model Train Club - v{self._version} / {self.config.name}"
        )
        self.log.info("Copyright Contributors to the RMTC Project")

    def _construct(self, config, **kwargs):
        """
        Simple
        """
        args = {}
        for k, v in config.items():
            if k == "uri":
                args[k] = URI(v)
            elif k == "type_name":
                args[k] = TypeName(v)
            else:
                args[k] = v
        try:
            return self._factory.create(
                **args,
                **kwargs,
            )
        except RMTCException as e:
            self._log.warning(f"Failed to construct {args['type_name']}\n{e}")
        return None

    @property
    def ops(self):
        return self._ops

    @property
    def track(self):
        return self._track

    @property
    def log(self):
        return self._log

    @property
    def objects(self):
        return self._objects

    @property
    def factory(self):
        return self._factory

    @property
    def broadcaster(self):
        return self._broadcaster

    @property
    def version(self):
        return self._version

    @property
    def mode(self):
        return self._mode

    @property
    def config(self):
        return self._config

    def is_valid(self):
        if self.track is None:
            return False
        if self.ops is None:
            return False
        if not self.track.is_valid():
            return False
        if not self.ops.is_valid():
            return False
        return True

    # entity management

    def add_entities(self, entities):
        return self._track.add_entities(entities)

    def remove_entities(self, entities):
        return self._track.remove_entities(entities)

    def clear(self):
        return self._track.clear()

    def pull(self, entities=None, force=False):
        return self._track.pull(entities, force=force)

    def push(self, entities=None, force=False):
        return self._track.push(entities, force=force)

    def delete_all(self, store_name=None):
        return self._track.delete_all(store_name=store_name)

    # artifact management

    def publish(self, entities, **kwargs):
        return self._track.publish(entities, **kwargs)

    # queries

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
        return self._track.get_runs(
            name=name,
            model=model,
            dataset=dataset,
            checkpoint=checkpoint,
            trainer=trainer,
            result_checkpoint=result_checkpoint,
            result_weights=result_weights,
            solution=solution,
            sync=sync,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )

    def get_best_run(
        self,
        solution,
    ):
        return self._track.get_best_run(solution=solution)

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
        return self._track.get_models(
            name=name,
            model_license=model_license,
            sync=sync,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )

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
        return self._track.get_licenses(
            name=name,
            sync=sync,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )

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
        return self._track.get_solutions(
            name=name,
            sync=sync,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )

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
        return self._track.get_datasets(
            name=name,
            dataset_license=dataset_license,
            sync=sync,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )

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
        return self._track.get_inferences(
            name=name,
            weights=weights,
            model=model,
            inputs=inputs,
            outputs=outputs,
            solution=solution,
            sync=sync,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )

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
        self.log.warning("Requesting assets - which are generally untracked")
        return self._track.get_assets(
            uri=uri,
            name=name,
            sync=sync,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )

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
        limit=25,
    ):
        return self._track.get_entities(
            name=name,
            categories=categories,
            obj_ids=obj_ids,
            sync=sync,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )

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
        return self._track.get_entity(
            name=name,
            category=category,
            obj_id=obj_id,
            sync=sync,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
        )

    def get_descendents(self, entities, sync=True):
        return self._track.get_descendents(
            entities=entities,
            sync=sync,
        )

    # creation

    def create_model(self, object_type=None, **kwargs):
        return self._track.create_model(object_type=object_type, **kwargs)

    def create_dataset(self, object_type=None, **kwargs):
        return self._track.create_dataset(object_type=object_type, **kwargs)

    def create_license(self, object_type=None, **kwargs):
        return self._track.create_license(object_type=object_type, **kwargs)

    def create_resource(self, object_type=None, **kwargs):
        return self._track.create_resource(object_type=object_type, **kwargs)

    def create_asset(self, object_type=None, **kwargs):
        return self._track.create_asset(object_type=object_type, **kwargs)

    def create_weights(self, object_type=None, run=None, **kwargs):
        return self._track.create_weights(object_type=object_type, run=run, **kwargs)

    def create_checkpoint(self, object_type=None, run=None, **kwargs):
        return self._track.create_checkpoint(object_type=object_type, run=run, **kwargs)

    def create_run(self, object_type=None, solution=None, **kwargs):
        run = self._track.create_run(
            solution=solution, object_type=object_type, **kwargs
        )

        return run

    def create_solution(self, object_type=None, **kwargs):
        return self._track.create_solution(object_type=object_type, **kwargs)

    def create_inference(self, session=None, object_type=None, **kwargs):
        return self._track.create_inference(
            object_type=object_type, session=session, **kwargs
        )

    def create_entity(self, type_name, **kwargs):
        return self._track.create_entity(type_name=type_name, **kwargs)

    def create_group(self, items):
        return self._track.create_group(items=items)

    def create_rights(self, name):
        return self._track.create_rights(name=name)

    def create_party(self, name):
        return self._track.create_party(name=name)

    def create_jurisdiction(self, name):
        return self._track.create_jurisdiction(name=name)

    def create_session(self, object_type=None, **kwargs):
        return self._track.create_session(object_type=object_type, **kwargs)

    def get_create(self, object_type, name, **kwargs):
        return self._track.get_create(object_type=object_type, name=name, **kwargs)

    # operations

    def create_scheduler(self, object_type=None, **kwargs):
        if not issubclass(object_type, Scheduler):
            raise RMTCException(f"Subclass {object_type} in create is invalid")
        return object_type(**kwargs, rmtc_system=self)

    def build(self, artifacts, pipeline_name):
        return self._ops.build(artifacts, pipeline_name)

    def infer(
        self,
        inputs,
        solution,
        inferer,
        scheduler,
        model=None,
        outputs=None,
        session=None,
        weights=None,
    ):
        # ensure scehduler is this
        if scheduler.rmtc_system is not self:
            raise RMTCException("Mismatched system for scheduler")

        # HACK: backward compat
        if isinstance(inputs, list):
            inputs = inputs[0]
            self.log.warning("Taking first element of inputs for infer")
        if isinstance(outputs, list):
            outputs = outputs[0]
            self.log.warning("Taking first element of outputs for infer")

        # run inference
        inference = self._ops.infer(
            solution=solution,
            inferer=inferer,
            model=model,
            inputs=inputs,
            outputs=outputs,
            scheduler=scheduler,
            weights=weights,
        )

        # add to inference sessions
        if session is not None:
            session.add_inferences([inference])

        # push to RMTC
        self.push()

        return inference

    def train(
        self,
        solution,
        trainer,
        model,
        dataset,
        scheduler,
        checkpoint=None,
    ):
        # ensure scehduler is this
        if scheduler.rmtc_system is not self:
            raise RMTCException("Mismatched system for scheduler")

        # HACK: backward compat
        if isinstance(dataset, list):
            dataset = dataset[0]
            self.log.warning("Taking first element of dataset for train")

        # use local if empty
        run = self._ops.train(
            solution=solution,
            trainer=trainer,
            model=model,
            dataset=dataset,
            scheduler=scheduler,
            checkpoint=checkpoint,
        )

        # push to RMTC
        self.push()

        return run

    def read(self, artifacts, metadata=None):
        return self._ops.asset_manager.read(artifacts, metadata=metadata)

    def write(self, artifacts, **kwargs):
        return self._ops.asset_manager.write(artifacts, **kwargs)

    def init(self, artifacts):
        return self._ops.asset_manager.init(artifacts)

    def reset(self, artifacts):
        return self._ops.asset_manager.reset(artifacts)

    def create_uri(self, artifact, root=None, **kwargs):
        return self._ops.asset_manager.create_uri(artifact, root=root, **kwargs)

    def identity_mode(self, mode):
        return self._ops.asset_manager.identity_mode(mode)

    def manage_versions_with_publisher(self, use_for_versioning):
        return self._ops.asset_manager.manage_versions_with_publisher(
            use_for_versioning
        )

    def default_name(self, entity):
        return self._ops.asset_manager.default_name(entity)

    def purge(self, solution, category):
        return self._ops.purge(solution, category)

    # tracing

    def trace_report(self, report, entities):
        return self._track.trace_report(report=report, entities=entities)

    def trace_sources(
        self,
        entity,
        recurse=True,
    ):
        return self._track.trace_sources(
            entity=entity,
            recurse=recurse,
        )

    def trace_derivatives(
        self,
        entity,
        recurse=True,
    ):
        return self._track.trace_derivatives(
            entity=entity,
            recurse=recurse,
        )
