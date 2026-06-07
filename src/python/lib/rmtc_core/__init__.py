# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import os

from rmtc_core.track.cypher.age import AGEDatabase
from rmtc_core.track.cypher.neo4j import Neo4jDatabase
from rmtc_core.train.torch.trackers import TensorBoard
from rmtc_core.pipeline.filesystem.asset_managers import FilesystemManager
from rmtc_core.pipeline.onnx.builders import ONNXModelBuilder, ONNXWeightsBuilder

from rmtc.objects import Objects
from rmtc.system import URI, LogLevel, Mode, Broadcaster, Logger, Config, ModuleFactory
from rmtc.track import Sync
from rmtc.pipeline import Pipeline
from rmtc.environment import NullEnv

import rmtc


class System(rmtc.System):
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
        mode=0,
        asset_manager=None,
        env_manager=None,
        broadcaster=None,
        factory=None,
    ):
        # create a config
        config = config or Config()

        # System config
        system_config = config["rmtc_system"]
        if system_config:

            # Get mode
            mode = Mode[system_config["mode"]]

            # Use the system pull to manage the just in time sync
            if jit is None:
                if "jit_sync" in system_config and system_config["jit_sync"]:
                    jit = Sync(self)

        # create simple log
        if log is None:
            log_config = config["rmtc_log"]
            log = Logger()
            if log_config:
                level = LogLevel[log_config["level"]]
                log.set_level(level)

        # create a factory
        if factory is None:
            factory = ModuleFactory(log=log)

        # Default tracker
        if tracker is None:
            tracker_config = config["rmtc_tracker"]
            tracker_uri = None
            if tracker_config:
                tracker_uri = URI(tracker_config["uri"])
            tracker = TensorBoard(uri=tracker_uri, log=log)

        # Store config
        if store is None:
            store_config = config["rmtc_store"]
            store_uri = URI()
            store_name = "rmtc"
            store_username = ""
            store_password = ""
            if store_config is not None:
                store_name = store_config["name"]
                store_uri = URI(store_config["uri"])
                store_username = store_config["username"]
                store_password = store_config["password"]
                if store_config["type"] == "age":
                    store = AGEDatabase(
                        factory=factory,
                        name=store_name,
                        db_name=store_config.get("db_name", "postgresDB"),
                        uri=store_uri,
                        mode=mode,
                        log=log,
                        jit=jit,
                    )
                else:
                    store = Neo4jDatabase(
                        factory=factory,
                        name=store_name,
                        uri=store_uri,
                        mode=mode,
                        log=log,
                        jit=jit,
                    )
            else:
                log.warning("No store config found")

        # Asset manager by default is the filesystem
        asset_manager = asset_manager or FilesystemManager(log=log)

        # create conformation pipeline for ONNX
        onnx_pipeline = Pipeline(
            log=log,
            name="ONNX",
            builders={
                "Model": [
                    ONNXModelBuilder(),
                ],
                "Weights": [
                    ONNXWeightsBuilder(),
                ],
            },
        )
        asset_manager.add_pipeline(onnx_pipeline)

        # General dependency eco system
        env_manager = env_manager or NullEnv(log=log)

        # Simple DOM store
        objects = objects or Objects()

        # create a basic broadcaster
        broadcaster = broadcaster or Broadcaster()

        # Pass up
        super(System, self).__init__(
            store=store,
            objects=objects,
            tracker=tracker,
            credentials=(store_username, store_password),
            config=config,
            mode=mode,
            log=log,
            asset_manager=asset_manager,
            env_manager=env_manager,
            broadcaster=broadcaster,
            factory=factory,
        )

        # Small features
        version = os.getenv("RMTC_VERSION", "0.0.0")
        self.log.info("--------------------------------------------")
        self.log.info("The Rongotai Model Train Club")
        self.log.info(f"Version: {version} / {mode}")
        self.log.info("SPDX-License-Identifier: Apache-2.0")
        self.log.info("Copyright Contributors to the RMTC Project")
        self.log.info("--------------------------------------------")
