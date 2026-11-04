# RMTC Architecture: Modules & Subsystems

This document describes each of RMTC's major modules and subsystems, their purpose, key classes, and current implementation status. It is designed to complement the canonical architecture document at [docs/technical/notes.md](README.md) with a focus on file paths and real class signatures extracted from the codebase.

## System Module

**Purpose:** Foundational type registration, configuration, object/property base classes, and core utilities.

**Key Classes:**
- `Factory` (`src/python/lib/rmtc/system/__init__.py:967`) — Dynamic instantiation and registration of RMTC classes using fully qualified type names (e.g., `rmtc.core.model.TorchModel-1.0.0`). Loads module definitions from YAML files and maintains a whitelist of allowed types.
- `Config` (`src/python/lib/rmtc/system/__init__.py:637`) — Singleton configuration manager. Loads YAML config files to provide database credentials, store settings, log levels, and system modes (production/testing).
- `Object` (`src/python/lib/rmtc/system/objects.py`) — Base class for all RMTC entities. Provides property system with types (Bool, Integer, String, DateTime, URI, Type, Package, Enum, Object references). Supports property arrays, access tracking, and event broadcasting.
- `Property` (`src/python/lib/rmtc/system/objects.py:121`) — Type-safe property wrapper supporting single values or arrays. Tracks ownership (member/non-member), visibility, requirements, and provenance direction (IN/OUT).
- `URI` (`src/python/lib/rmtc/system/__init__.py:160`) — Fully qualified resource identifier with query parameter parsing and manipulation. Supports file URIs and arbitrary schemes.
- `Version` (`src/python/lib/rmtc/system/__init__.py:25`) — Semantic versioning wrapper with validation and compatibility checking.
- `Datetime` (`src/python/lib/rmtc/system/__init__.py:118`) — ISO UTC timestamp wrapper enforcing consistent formatting.
- `TypeName` (`src/python/lib/rmtc/system/__init__.py:903`) — Parsed representation of fully qualified type names (module.category.name-version).
- `Logger` (`src/python/lib/rmtc/system/__init__.py:533`) — Python logging wrapper with event broadcasting.
- `Broadcaster` (`src/python/lib/rmtc/system/__init__.py:602`) — Simple pub-sub event system for object lifecycle notifications.

**Maturity:** Implemented. Factory and Config systems are production-ready; property system is complete with comprehensive type support.

## Objects & Containers Module

**Purpose:** Generic base classes for property-aware objects and abstract data container structures.

**Key Classes:**
- `Object` (`src/python/lib/rmtc/system/objects.py`) — Abstract base for all trackable items in RMTC. Manages properties, UUID identification, property change notifications, and immutability semantics.
- `PropertyDirection` (enum) — Defines provenance flow: IN (sources), OUT (derivations), INOUT (both).
- `Container` (`src/python/lib/rmtc/system/containers.py:14`) — Abstract base for 2D table-like data structures (e.g., datasets with correlated rows).
- `Table` (`src/python/lib/rmtc/system/containers.py:14`) — Abstract interface for 2D tables with row/column iteration, used by Dataset types.
- `TableIterator` (`src/python/lib/rmtc/system/containers.py:86`) — Abstract iterator for table traversal; concrete implementations like `PaddedTableIterator` and `RowMajorIterator` handle different dataset layouts.

**Maturity:** Implemented. Core object and property system is mature; containers are lean abstractions sufficient for current dataset types.

## Track Module: Provenance & Storage

**Purpose:** Entity storage abstraction, provenance graph management, and query interface for the distributed artifact tracking database.

### Entity Base Class

**Key Classes:**
- `Entity` (`src/python/lib/rmtc/track/store.py:52`) — Abstract base for all storable entities. Provides lazy loading (fetch/sync), lifecycle states (created/updated/synced/deleted), timestamp tracking, and JIT (just-in-time) sync capability.
- `Store` (abstract, `src/python/lib/rmtc/track/store.py`) — Abstract storage backend interface. Concrete implementations include Neo4j, Apache AGE, and JSON file stores.
- `Connection` (abstract, `src/python/lib/rmtc/track/store.py`) — Abstract database connection interface.
- `Queries` (abstract, `src/python/lib/rmtc/track/store.py`) — Abstract query builder interface.

**Maturity:** Implemented. Core entity lifecycle is solid; store backends are pluggable.

### Cypher/AGE Store Backend

**Key Classes:**
- `CypherConnection` (`src/python/lib/rmtc/core/track/store/cypher/connection.py:37`) — Concrete Connection implementation for Cypher-based graph databases (Neo4j, Apache AGE). Handles entity persistence, relationship management, parameterized queries (to prevent SQL injection), and property serialization.
- `CypherQueries` — Query builder for Cypher syntax, supporting both Neo4j and Apache AGE dialects.
- `Neo4jDatabase` (`rmtc.core.track.store.cypher.neo4j.Neo4jDatabase` per `res/modules/rmtc_core.yaml:337`) — Concrete Store implementation for Neo4j.
- `AGEDatabase` (`rmtc.core.track.store.cypher.age.AGEDatabase` per `res/modules/rmtc_core.yaml:341`) — Concrete Store implementation for Apache AGE (PostgreSQL extension).

**Maturity:** Partial. Core Cypher queries are implemented; recent work (commits visible in git history) shows parameterized query refactoring to address injection vulnerabilities.

### Tracking Entities

**Key Classes (from `src/python/lib/rmtc/track/entities.py`):**
- `Asset` (`Asset`, line 1119) — Base artifact representing a concrete digital asset (image, model, dataset).
- `Artifact` (`Artifact`, line 679) — Abstract base for versioned, licensed digital artifacts with provenance tracking. Supports ancestors (lineage) and variants (format equivalents).
- `License` (`License`, line 413) — Shared entity representing usage rights, validity periods, jurisdictional constraints, and permission requirements.
- `Model` (`Model`, line 793) — Artifact subclass for ML models with input/output type specifications and performance metrics.
- `Weights` (`Weights`, line 919) — Artifact subclass for trained model parameters. Owned by Runs.
- `Checkpoint` (`Checkpoint`, line 877) — Artifact subclass for training checkpoints with epoch metadata.
- `Dataset` (`Dataset`, line 1005) — Artifact subclass representing collections of assets for training/inference. Can be repositories (URI-deferred), aggregations, or collections.
- `Solution` (`Solution`, line 169) — Container entity for a complete ML problem. Holds input/output type signatures and manages Runs.
- `Run` (`Run`, line 306) — Entity representing a single training execution. Owned by Solutions; owns result Weights and Checkpoints.
- `Inference` (`Inference`, line 630) — Entity representing model inference execution and results. Links Model, Weights, and output Datasets.
- `Watermark` (`Watermark`, line 1084) — Entity for tracking data provenance markers.
- `Session` (`Session`, line 42) — Entity for DCC or tooling sessions that produce inferences.
- `Environment` (`Environment`, line 19) — Entity for package and environment specifications.
- `Party`, `Jurisdiction`, `Tag`, `Right`, `Filter` — Supporting entities for licensing, organization, and query filters.

**Maturity:** Implemented. Core provenance entities are complete; recent work shows property access parameterization for security.

## Ops Module: Operations & Pipelines

**Purpose:** Processing, training, inference, I/O, and artifact building subsystems.

### I/O Subsystem

**Key Files/Classes:**
- `src/python/lib/rmtc/core/ops/io/` — Technology-specific I/O implementations.
  - `torch/models.py` — PyTorch model I/O (TorchScript, Package formats).
  - `torch/weights.py` — PyTorch weights I/O.
  - `torch/checkpoints.py` — PyTorch checkpoint I/O.
  - `onnx/models.py` — ONNX model I/O.
  - `oiio/image.py` — Image I/O via OpenImageIO (EXR, JPG).
  - `filesystem/folders.py` — Dataset I/O for folder-based asset collections (correlated or flat).
  - `filesystem/json.py` — JSON tensor serialization.
  - `usd/camera.py` — USD camera data I/O.
  - `safetensors/weights.py` — Safetensors weights I/O.

**Maturity:** Partial. Core image and tensor I/O working; USD and multi-part EXR support are incomplete (see [notes.md](README.md) for known limitations).

### Processing Subsystem

**Purpose:** Invertible tensor transformations for format conversion between asset-native and model-specific representations.

**Key Classes/Files:**
- `Process` (base class, `src/python/lib/rmtc/core/ops/process/`) — Abstract invertible operator with `run()` and `run_inverse()` methods.
- `ProcessStack` — Ordered sequence of Processes.
- Concrete Processors:
  - `image/color.py` — Color space conversions (LinearToSRGB, LinearNormalize, StatsNormalize, MakeMonochrome).
  - `image/channels.py` — Channel manipulation (MoveChannelsFirst, TrimAlpha, Shuffle, Flip).
  - `image/transform.py` — Spatial transforms (Rotate, Translate, Scale, Resize, Crop, Align, Pad).
  - `image/conversions.py` — Format converters for PyTorch, Keras, OpenCV, ONNX, Tensorflow.
  - `tensor/structure.py` — Tensor structure ops (Batch, Contiguous, DataType).
  - `camera/intrinsics.py` — Camera parameter conversion.
  - `packagers/tensor.py` — Tensor batching/unbatching (Batch, Unbatch, Split, Cat, Append, Pop).

**Maturity:** Partial. Basic image operations implemented; advanced augmentation and validation incomplete.

### Artifacts Subsystem

**Key Files:**
- `src/python/lib/rmtc/core/ops/artifacts/torch/models.py` — PyTorch model wrappers (TorchModel).
- `src/python/lib/rmtc/core/ops/artifacts/torch/weights.py` — PyTorch weights wrappers (TorchWeights).
- `src/python/lib/rmtc/core/ops/artifacts/torch/checkpoints.py` — PyTorch checkpoint wrappers (TorchCheckpoint).
- `src/python/lib/rmtc/core/ops/artifacts/onnx/models.py` — ONNX model wrappers (ONNXModel).
- `src/python/lib/rmtc/core/ops/artifacts/structured/datasets.py` — Structured dataset implementations (MappedAssets).

**Maturity:** Implemented. PyTorch artifacts production-ready; ONNX and structured datasets have known input/output shape gaps.

### Training Subsystem

**Key Classes/Files:**
- `src/python/lib/rmtc/core/ops/train/torch/trainers.py` — PyTorch trainer implementation (TorchRegression). Handles dataset loading, processor application, model training, checkpoint/weight creation.
- `src/python/lib/rmtc/ops/scheduling.py` — Job scheduling abstraction for distributing training runs.
- `Scheduler` (abstract) — Deferred to facility implementations (OpenCue, Deadline, local).

**Maturity:** Partial. Local training loop works; distributed scheduling is a stub (facility-specific implementations expected).

### Inference Subsystem

**Key Classes/Files:**
- `src/python/lib/rmtc/core/ops/infer/simple/inferers.py` — Simple inferer implementations (DatasetInferer, BatchedInferer).
- `Inferer` (abstract) — Base class for inference operations.
- Dataset-to-dataset inference model with dynamic output dataset creation.

**Maturity:** Partial. Basic dataset inference works; DCC plugin integration and real-time inference optimization are incomplete.

### Pipeline & Asset Management

**Key Classes/Files:**
- `src/python/lib/rmtc/core/ops/pipeline/asset_managers/filesystem.py` — Filesystem asset manager (FilesystemManager).
- `src/python/lib/rmtc/core/ops/pipeline/*/builders.py` — Format-specific builders (e.g., Nuke CAT builders, ONNX builders).
- Builders transform artifacts (Model + Weights → TorchScript → Nuke CAT) and publish variants.

**Maturity:** Partial. Filesystem asset management works; facility-specific builders and Open Asset IO integration incomplete.

## GUI Module

**Purpose:** Qt-based user interfaces for ingestion, provenance tracing, and training management.

**Key Components:**
- `NodeGraphQt` DAG editor for provenance visualization.
- Property editor widgets for Entity property viewing/editing.
- Junction ingestion tool for Model/Dataset/Solution creation.
- Signal Box for provenance tree traversal.
- Conductor for training job submission.
- Train Track for training monitoring and result publishing.

**Maturity:** Prototype. Provenance visualization and property editing are functional; training management tools are incomplete.

## Placeholder Modules

**Purpose:** Stubs for future expansion.

**Scheduler Module** (`src/python/lib/rmtc/ops/scheduling.py`) — Deferred job scheduling abstraction intended for shared use by train and infer subsystems.

**Environment Module** (`src/python/lib/rmtc/core/system/environment/packages.py`) — Package and environment management (e.g., UV virtual environments). Allows injection of environment managers for dependency resolution.

**Interface Module** (`src/python/lib/rmtc/interface/`, REST client in `src/python/lib/rmtc/core/interface/rest/`) — Client & Server abstractions and a REST client for bridging distributed Systems via network. The Flask REST server is the separate `rmtc-server` package (`src/python/server/`).

## Key Design Patterns

### Injection & Deferral
Classes accept injected dependencies (trainers, I/O implementations, asset managers, schedulers) rather than hard-coding them. The Factory resolves type names to concrete classes at runtime.

### Provenance Immutability
Artifacts are immutable; updates via variants or new artifacts only. Licenses form the terminus of provenance traces.

### Data Minimization
Entities are lazy-loaded (fetch retrieves light representation, sync loads full properties). JIT sync pulls partial entities on first access to non-required properties. Reverse relationships (Run → Solution, not Solution → Runs) prevent massive pulls.

### Type Registration
All storable classes registered in `res/modules/rmtc_core.yaml` with fully qualified type names. Factory whitelist prevents arbitrary code execution.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
