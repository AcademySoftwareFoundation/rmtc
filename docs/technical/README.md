# RMTC Technical Notes 

This document follows a technical notes format on each of the modules of the implementation to give you a sense of how RMTC works. It is the partner document to the initial develop branch release to the ASWF GitHub and is intended to be read alongside the code to provide insights into each of the modules - it is not class documentation, docstrings are present on almost all the Python classes. 

For file-path and class-level detail behind these notes, see the companion [Architecture: Modules & Subsystems](modules.md) reference. 

## Contents 

* [Introduction](introduction.md) - what RMTC is, project status and the key concepts (provenance, immutability, data minimisation) that shape the rest of the design 
* [Code Structure](code-structure.md) - the module "sandwich", RMTC vs RMTC Core, testing, linting and resources 
* [Examples](examples.md) - the worked examples in the repo and the general coding style they follow 
* [Modules](type-modules.md) - how to use a System instance to create, train, infer and push tracked artifacts 
* [System (module)](system-module.md) - Factory, type name resolution, module & config YAML, complex base types, logging and event broadcasting 
* [Containers](containers.md) - the Table abstraction used to represent correlated datasets 
* [Objects](objects.md) - the Object/Entity/Artifact hierarchy, the property system, arrayed properties and the local object DOM 
* [Track](track.md) - entities, schema, immutability, provenance, tracing/reports and filters 
* [Stores & Store Names](stores-store-names.md) - how entities are persisted, the fetch/sync/update model and JIT sync 
* [Artifacts](artifacts.md) - URIs & IO, assets, licenses & guardrails, dataset types, ancestors & variants, metrics, tensor formats, processors, packagers, and models/weights/checkpoints 
* [Train](train.md) - solutions & runs, scheduling, trainers & trackers, augmentation 
* [Infer](infer.md) - inferers, inferencing & datasets, performance notes, DCC inference 
* [Pipeline](pipeline.md) - building artifact variants, asset management and publishers 
* [GUI](gui.md) - the shared System-backed Qt tooling: property editor, Signal Box, Junction, Conductor and Train Track 
* [Scheduler](scheduler.md) - the shared Scheduler/Task/Job/Executor/Tracker abstractions behind Train's run scheduling 
* [Environment](environment.md) - the placeholder module for package & environment management 
* [Interface](interface.md) - the Client/Server abstractions and REST client for bridging two Systems over REST 
* [Server](server.md) - the Flask REST server: serialization, serving, environment variables, versioning and routes
* [Web UI](webui.md) - the browser UI for the REST API: stack, structure, development and hosting

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
