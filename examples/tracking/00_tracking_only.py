#usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import rmtc.track

import rmtc_core.track.licenses.community as community_licenses
import rmtc_core.track.licenses.commercial as commercial_licenses

from rmtc.system import Logger
from rmtc_core.track.cypher.neo4j import Neo4jDatabase
from rmtc.system import URI, Datetime, Mode, Config, ModuleFactory

import argparse
parser = argparse.ArgumentParser(
    description     = "Tracking Only RMTC Example."
)
parser.add_argument("--store_name",
    help            = "Specify a store name",
    default         = "rmtc_examples",
)
args = parser.parse_args()


###############################################################################

config              = Config()
username            = config["rmtc_store"]["username"]
password            = config["rmtc_store"]["password"]
uri                 = config["rmtc_store"]["uri"]
log                 = Logger()
store               = Neo4jDatabase(
    name            = args.store_name,
    factory         = ModuleFactory(log=log),
    mode            = Mode.PRODUCTION,
    uri             = URI(uri),
    log             = log,
)

# create license
apache1_license     = community_licenses.OSS(
                        "Apache-1.0", 
                        uri=URI("https://www.apache.org/licenses/LICENSE-1.0.html"),
                        parties=["Mozilla Foundation"], 
)

# push
db                  = store.connect(username, password)
db                  .create([apache1_license])
db                  .update([apache1_license])
db                  .close()

# pull
db                  = store.connect(username, password)
license_id          = db.queries.get_licenses("Apache-1.0")[0]
apache_license      = db.fetch([license_id])[0]
db                  .sync([apache_license])
db                  .close()

# clear store cache
store               .clear()

# create licenses
ml_license          = commercial_licenses.Agreement(
                        "ML License", 
                        parties=["VFX Facility", "Production Facility"],
                        place="LA, USA",
                        date=Datetime("2020-05-01T11:31:00"),
                        start=Datetime("2020-05-01T11:31:00"),
                        finish=Datetime("2024-05-01T11:31:00"),
                        uri=URI("sharepoint://documents/ml_training_agreement.pdf"),
                        reference="0123456789"
                    )    
apache2_license     = community_licenses.OSS(
                        "Apache-2.0", 
                        uri=URI("https://apache.org/licenses/LICENSE-2.0.html"),
                        parties=["Mozilla Foundation"],
                    )
show_license        = commercial_licenses.Show(
                        "Show License", 
                        parties=["Production Facility"],
                        start=Datetime("2023-05-01T11:31:00"),
                        finish=Datetime("2030-05-01T11:31:00")
                    )
john_license        = commercial_licenses.Agreement(
                        "John Smith Likeness", 
                        parties=["John Smith", "Production Company"],
                        date=Datetime("2015-05-01T11:31:00"),
                        place="Los Angeles County, USA",
                        start=Datetime("2020-05-01T11:31:00"),
                        finish=Datetime("2030-05-01T11:31:00"),
                        uri=URI("ftp://production_company.com/documents/likeness_agreement.pdf"),
                        reference="0123456789"
                    )

# update with some notes
john_license        .notes.append("Must not be used in a context that may damage the reputation of all parties")
john_license        .notes.append("Only used for facial swap training")

# add to the Objects
db                  = store.connect(username, password)
db                  .create([apache2_license, show_license, ml_license, john_license])
db                  .update([apache2_license, show_license, ml_license, john_license])
db                  .close()

# fetch our created license via the DB
db                  = store.connect(username, password)
license_id          = db.queries.get_licenses("John Smith Likeness")[0]
rock_license        = db.fetch([license_id])[0]
db                  .sync([rock_license])
db                  .close()

# find the licenses
db                  = store.connect(username, password)
apache_license      = db.fetch(db.queries.get_licenses("Apache-2.0"))[0]
show_license        = db.fetch(db.queries.get_licenses("Show License"))[0]
ml_license          = db.fetch(db.queries.get_licenses("ML License"))[0]
john_license        = db.fetch(db.queries.get_licenses("John Smith Likeness"))[0]
db                  .close()

# setup a CSV dataset
db                  = store.connect(username, password)
dataset             = rmtc.track.Dataset(
                        name="Show Facial Dataset", 
                        uri=URI("file://localhost/show_dataset.csv")
                    )
db                  .create([dataset])
dataset             .add_licenses([john_license, ml_license, show_license, apache_license])
db                  .update([dataset])

# create a generic torch model
foundation_model    = rmtc.track.Model(
                        name="Foundation De-Age Model",
                        uri=URI("https://github.com/foundataional_model"),
                        author="Big Tech"
                    )
model               = rmtc.track.Model(
                        name="Show De-Age Model",
                        uri=URI("file://localhost/torch_model.pth"),
                        author="Jane Smith",                     
                        ancestors=[foundation_model],
                    )

# create a specific ONNX model
onnx_model          = rmtc.track.Model(
                        name="ONNX De-Age Model", 
                        uri=URI("file://localhost/onnx_model.onnx")
                    )
db                  .create([foundation_model, model, onnx_model])

# connect all up
foundation_model    .add_licenses([apache_license])
model.dataset       = dataset
model               .add_variants([onnx_model])

# push it
db                  .update([foundation_model])
db                  .update([model])
db                  .close()

# clear and reopen
store               .clear()
db                  = store.connect(username, password)

# get model and dataset
model_ids           = db.queries.get_models("Show De-Age Model")
model               = db.fetch(model_ids)[0]
dataset_ids         = db.queries.get_datasets("Show Facial Dataset")
dataset             = db.fetch(dataset_ids)[0]
db                  .sync([model, dataset])

# create a solution
solution            = rmtc.track.Solution(name="De-Age Solution")

# create a fake run
run                 = rmtc.track.Run(
    name            = "Train Run 1",
    model           = model,
    dataset         = dataset,
    solution        = solution,
)
run.status          = rmtc.track.RunStatus.FINISHED

# create trainer
trainer             = run.create_trainer(
    batch_size      = 5, 
    epochs          = 5, 
    name            = "Regression Trainer")

# create weights
weights             = run.create_weights(
    uri=URI("file://localhost/proj/weights.pt")    
)

# create checkpoints
checkpoints         = []
for i in range(3):
    checkpoint      = run.create_checkpoint(
        uri         = URI("file://localhost/proj/checkpoints/checkpoint_{i}.pt")
    )
    checkpoints.append(checkpoint)

# push
db                  .create([solution, run])
db                  .update([solution, run])
db                  .close()

# reopen
store               .clear()
db                  = store.connect(username, password)

# get run
solution_ids        = db.queries.get_solutions("De-Age Solution")
solution            = db.fetch(solution_ids)[0]
db                  .sync([solution])
run_ids             = db.queries.get_runs(solution=solution)
run                 = db.fetch(run_ids)[0]
db                  .sync([run])

# create inference
inference           = rmtc.track.Inference(
    name            = "Inference 1",
    model           = run.model,
    weights         = run.result_weights,
)

# create assets from the inference
assets              = []
for i in range(3):
    assets          .append(rmtc.track.Asset(name=f"Image_{i}"))
inference.result    = rmtc.track.Dataset(assets=assets)

db                  .create([inference])
db                  .update([inference])

db                  .close()