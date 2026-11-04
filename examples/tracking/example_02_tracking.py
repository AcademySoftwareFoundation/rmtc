#usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import rmtc
import rmtc.track

from rmtc.core.track.publishing.publishers.filesystem import DiskPublisher
from rmtc.track.entities import Party
from rmtc.system import Logger
from rmtc.ops.scheduling import Status
from rmtc.core.track.store.cypher.neo4j import Neo4jDatabase
from rmtc.system import URI, Datetime, Config, Factory
from rmtc.system.objects import Objects

import argparse
parser = argparse.ArgumentParser(
    description     = "Tracking Only RMTC Example."
)
parser.add_argument("--username",
    required        = True,
)
parser.add_argument("--password",
    required        = True,
)
args = parser.parse_args()

# Setup config and create a tracking object
config              = Config(name="demo")
log                 = Logger()
objects             = Objects()
factory             = Factory(log=log)
publisher           = DiskPublisher(log=log, immutable=False)
credentials         = (args.username, args.password)
store               = Neo4jDatabase(
    name            = config["rmtc_store"]["name"],
    uri             = URI(config["rmtc_store"]["uri"]),
    immutable       = config["rmtc_store"]["immutable"],
    log             = log,
    factory         = factory,
)
rmtc_tracking       = rmtc.track.Tracking(
    store           = store,
    publisher       = publisher,
    credentials     = credentials,
    log             = log,
    objects         = objects,
    factory         = factory,
    jurisdiction    = None,
    party           = None, 
    tracer          = None, 
)

# create license
apache1_license     = rmtc_tracking.create_license(
                        name="Apache-1.0", 
                        uri=URI("https://www.apache.org/licenses/LICENSE-1.0.html"),
                        parties=[rmtc_tracking.get_create(Party, "Mozilla Foundation")], 
                    )

# push it & clear
rmtc_tracking       .push()
rmtc_tracking       .clear()

# get license
apache1_license     = rmtc_tracking.get_licenses("Apache-1.0")[0]
print(f"License: {apache1_license}")

# create licenses
ml_license          = rmtc_tracking.create_license(
                        name="ML License", 
                        parties=[
                            rmtc_tracking.get_create(Party, "VFX Facility"), 
                            rmtc_tracking.get_create(Party, "Production Facility")
                        ],
                        date=Datetime("2020-05-01T11:31:00"),
                        start=Datetime("2020-05-01T11:31:00"),
                        finish=Datetime("2024-05-01T11:31:00"),
                        uri=URI("sharepoint://documents/ml_training_agreement.pdf"),
                        externals=["0123456789"],
                    )    
apache2_license     = rmtc_tracking.create_license(
                        name="Apache-2.0", 
                        uri=URI("https://apache.org/licenses/LICENSE-2.0.html"),
                        parties=[rmtc_tracking.get_create(Party, "Mozilla Foundation")], 
                    )
show_license        = rmtc_tracking.create_license(
                        name="Show License", 
                        parties=[rmtc_tracking.get_create(Party, "Production Facility")],
                        start=Datetime("2023-05-01T11:31:00"),
                        finish=Datetime("2030-05-01T11:31:00")
                    )
john_license        = rmtc_tracking.create_license(
                        name="John Smith Likeness", 
                        parties=[
                            rmtc_tracking.get_create(Party, "John Smith"), 
                            rmtc_tracking.get_create(Party, "Production Company")
                        ],
                        date=Datetime("2015-05-01T11:31:00"),
                        start=Datetime("2020-05-01T11:31:00"),
                        finish=Datetime("2030-05-01T11:31:00"),
                        uri=URI("ftp://production_company.com/documents/likeness_agreement.pdf"),
                        externals=["0123456789"],
                    )

# update with some notes
john_license        .notes.append("Must not be used in a device that may damage the reputation of all parties")
john_license        .notes.append("Only used for facial swap training")

# push it & clear
rmtc_tracking       .push()
rmtc_tracking       .clear()

# find the licenses
apache_license      = rmtc_tracking.get_licenses("Apache-2.0")[0]
show_license        = rmtc_tracking.get_licenses("Show License")[0]
ml_license          = rmtc_tracking.get_licenses("ML License")[0]
john_license        = rmtc_tracking.get_licenses("John Smith Likeness")[0]
print(f"Licenses: {[apache_license, show_license, ml_license, john_license]}")

# setup a CSV dataset
dataset             = rmtc_tracking.create_dataset(
                        name="Show Facial Dataset", 
                        uri=URI("file://localhost/show_dataset.csv")
                    )

# create a generic torch model
foundation_model    = rmtc_tracking.create_model(
                        name="Foundation De-Age Model",
                        uri=URI("https://github.com/foundataional_model"),
                        author="Big Tech"
                    )
model               = rmtc_tracking.create_model(
                        name="Show De-Age Model",
                        uri=URI("file://localhost/torch_model.pth"),
                        author="Jane Smith",                     
                        ancestors=[foundation_model],
                    )

# create a specific ONNX model
onnx_model          = rmtc_tracking.create_model(
                        name="ONNX De-Age Model", 
                        uri=URI("file://localhost/onnx_model.onnx")
                    )

# connect all up
foundation_model    .add_licenses([apache_license])
model               .add_variants([onnx_model])

# push it & clear
rmtc_tracking       .push()
rmtc_tracking       .clear()

# get model and dataset
model               = rmtc_tracking.get_models("Show De-Age Model")[0]
dataset             = rmtc_tracking.get_datasets("Show Facial Dataset")[0]
print(f"Model: {model}")
print(f"Dataset: {dataset}")

# create a solution
solution            = rmtc_tracking.create_solution(
                        name="De-Age Solution"
                    )

# create a fake run
run                 = rmtc_tracking.create_run(
    solution        = solution,
    name            = "Train Run 1",
    model           = model,
    dataset         = dataset,
)
run.status          = Status.FINISHED

# create weights
weights             = run.create_weights( 
    uri             = URI("file://localhost/proj/weights.pt")    
)

# create checkpoints
for i in range(3):
    checkpoint      = run.create_checkpoint(
        uri         = URI("file://localhost/proj/checkpoints/checkpoint_{i}.pt")
    )

# push it & clear
rmtc_tracking       .push()
rmtc_tracking       .clear()

# get run
print(f"Solution: {solution}")
solution            = rmtc_tracking.get_solutions("De-Age Solution")[0]
run                 = rmtc_tracking.get_runs(solution=solution)[0]
print(f"Run: {run}")

# create inference
inference           = rmtc_tracking.create_inference(
    name            = "Inference 1",
    model           = run.model,
    weights         = run.result_weights,
)

# create assets from the inference
assets              = []
for i in range(3):
    asset           = rmtc_tracking.create_asset(name=f"Image_{i}")
    assets.append(asset)
inference.outputs   = rmtc.track.entities.Dataset(assets=assets)

# push it & clear
rmtc_tracking       .push()
rmtc_tracking       .clear()

# get inference
inference           = rmtc_tracking.get_inferences(model=run.model)[0]
print(f"Inference: {inference}")
print(f"Result: {inference.outputs}")

