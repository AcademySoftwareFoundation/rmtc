# Pipeline Example

This is an example of how to create artifacts, build variants with the asset manager pipeline builders, and then publish them.

## Requirements
- RMTC storage system setup
- Valid config path in env

## Execution

### Go to the pipeline examples directory
```bash
cd /path/to/examples/pipeline
```

### Create a model, solution, run and weights
```bash
python example_00_create_artifacts.py \
    --weights_path=/path/to/weights.pt \
    --model_path=/path/to/model.pt \
    --model_name="Test Model" \
    --model_class_name=Model \
    --model_package=model.pkl \
    --solution_name="Test Solution"
```

### Publish the model and weights via the asset manager
```bash
python example_01_publish_weights.py --solution_name="Test Solution"
```

### Build a TorchScript variant of the weights
```bash
python example_02_build_torchscript.py --solution_name="Test Solution"
```

### Build a Nuke CAT file variant of the weights
Pulls the weights before building, so the asset manager publish step above must have run first.
```bash
python example_03_nuke_pipeline.py --solution_name="Test Solution"
```

### Build a safetensors variant of the weights
```bash
python example_04_build_safetensors.py --solution_name="Test Solution"
```

### Explore the resulting population
```bash
rmtcgui&
```
