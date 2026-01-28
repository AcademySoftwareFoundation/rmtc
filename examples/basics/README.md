# Basic Exampls

Simple getting going examples to show system setup, basic object creation and general system usage.

## Requirements
- RMTC storage system setup
- RMTC server instance running `rmtc-server`
- Valid config path in env

## Execution

### Go to rmtc examples directory
```bash
cd /path/to/examples
```

### Run simple database population
```bash
python 00_simple.py
```

### Run explorer and search for Apache-2.0
```bash
rmtc-gui&
```

### Start server and query for entities
```bash
rmtc-server&
python 01_rest_api.py --entity="Apache-2.0"
```


