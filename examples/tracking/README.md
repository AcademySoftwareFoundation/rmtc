# Tracking Examples

Simple tracking DB calls - no inference or training. Use these examples to instrument your own training pipelines.

The provenance report allows you to create a markdown report on the sources of a given named entity. The name is searched via a regex.

## Requirements
- RMTC storage system setup
- Valid config path in env
- Credentials for the configured store

## Execution

### Go to the tracking examples directory
```bash
cd /path/to/examples/tracking
```

### Populate the store using the System-level tracking API
Creates licenses, a dataset, model, run, weights, checkpoints and inference, connecting to the store directly with the given credentials.
```bash
python example_00_db_tracking.py --username=<username> --password=<password>
```

### Create a markdown provenance report
Searches for entities matching the given name and builds a report tracing their sources.
```bash
python example_01_provenance_report.py --entity="Apache-2.0"
```

### Populate the store using the lower-level Tracking object directly
Equivalent population to example_00, but bypasses the System object and drives the `Tracking` class directly - useful if you want to integrate tracking into your own pipeline without adopting the rest of System.
```bash
python example_02_tracking.py --username=<username> --password=<password>
```

### Explore the resulting population
```bash
rmtcgui&
```
