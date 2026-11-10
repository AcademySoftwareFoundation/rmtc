# Basic Examples

Simple getting going examples to show system setup, basic object creation and general system usage.

## Requirements
- RMTC storage system setup
- Valid config path in env

## Execution

### Go to the basics examples directory
```bash
cd /path/to/examples/basics
```

### Clear the store
Interactively prompts for confirmation before deleting everything in the configured store.
```bash
python example_00_clear.py
```

### Run simple database population
Creates a license, model and dataset then pushes them to the store.
```bash
python example_01_simple.py
```

### Connect to the RMTC server and query for an entity
Start the server, then in another shell query it for the "Apache-2.0" license it creates.
```bash
rmtcserver --config demo &
python example_02_rest_api.py
```

### Publish a model and dataset via the asset manager
```bash
python example_03_asset_manager.py
```

### Sketch of a custom Model class
This one is illustrative only - `TestModel` is not runnable as-is (see the `TODO` in the script).
```bash
python example_04_model_calling.py
```

### Create licenses, rights and solutions and check compliance
```bash
python example_05_rights.py
```

### Explore the resulting population
```bash
rmtcgui&
```
