# Basic tracking example

Simple tracking in the DB calls - no inference or training. Use this example to instrument your own training pipelines.

The provenance report allows you to create a markdown report on the sources of a given named
asset. The name is searched via a regex.

## Requirements
- RMTC storage system setup
- Valid config path in env

## Execution

### Go to rmtc examples directory
```bash
cd /path/to/examples
```

### Run tracking database population
Raw storage calls do not use the config, pass the store URI that is from the config yaml
```bash
python 00_tracking_only.py --store_uri="postgres://age.com:1234"
```

### Create a markdown provenance report
```bash
python 01_provenance_report.py --entity="Image"
```

### Explore the resulting population
```bash
rmtc-gui&
```
