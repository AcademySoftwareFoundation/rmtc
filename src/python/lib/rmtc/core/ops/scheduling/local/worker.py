# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

# Run a task in a new process using the inherited environment
# Packages are pulled in by the asset manager on load
# JSON is used to deploy results

# TODO: this is incomplete

import argparse
import ast
import json
from pathlib import Path

import rmtc
from rmtc.system import Config, URI
from rmtc.system.objects import Immutable
from rmtc.core.system.serializers.json import JSONSerializer

parser = argparse.ArgumentParser()
parser.add_argument("--job_id", required=True, type=str)
parser.add_argument("--job_range", required=True, type=str)
parser.add_argument("--task_id", required=True, type=str)
parser.add_argument("--results_file", required=True, type=str)
parser.add_argument("--artifact_uri", required=True, type=str)
# NOTE: testing overrides the environment store - so requires passing
parser.add_argument("--store_name", required=True, type=str)
parser.add_argument("--config_name", required=True, type=str)

# get the values
args = parser.parse_args()
job_range = ast.literal_eval(args.job_range)
job_id = args.job_id
task_id = args.task_id
store_name = args.store_name
config_name = args.config_name
results_file = Path(args.results_file)
artifact_uri = URI(args.artifact_uri)

# setup system
rmtc_sys = rmtc.System(
    Config(
        name=config_name,
        overrides={
            "rmtc_store": {
                "name": store_name,
            },
        },
    )
)

# get and run the task - this is const so is thread safe
task = rmtc_sys.get_entity(obj_id=task_id)
with Immutable(task):

    # run and get results
    metric, artifacts = task.run(
        run_range=job_range,
        rmtc_system=rmtc_sys,
    )

    # write out any artifacts that were not written
    # to a temporary location
    asset_manager = rmtc_sys.ops.asset_manager
    for artifact in artifacts:
        if not asset_manager.exists([artifact]):
            artifact.uri.parent = artifact_uri
            rmtc_sys.ops.asset_manager.write([artifact])

    # pack the metric and objects into a single JSON struct
    serializer = JSONSerializer(factory=rmtc_sys.factory, objects=rmtc_sys.objects)
    json_data = {}
    json_data["metric"] = metric
    json_data["artifacts"] = json.loads(serializer.serialize(artifacts))
    data = json.dumps(json_data)
    results_file.write_text(data, encoding="utf-8")
