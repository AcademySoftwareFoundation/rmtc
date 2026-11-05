# Image2Mask Example

This is an example of how to train an image-to-mask model - taking a plate image in and producing a mask, tracking the model, dataset and run through RMTC.

## Requirements
- RMTC storage system setup
- Valid config path in env
- A pre-packaged PyTorch image-to-image model (pickled)
- A folder of correlated EXR plate/mask pairs

## Execution

### Go to the image2mask examples directory
```bash
cd /path/to/examples/image2mask
```

### Create and track the model and solution
```bash
python example_00_create_artifacts.py \
    --model_path=/path/to/model.pt \
    --model_name="Test Model" \
    --model_class_name=Model \
    --model_package=model.pkl \
    --solution_name="Test Solution" \
    --solution_path=/path/to/solution
```

### Train the model against a dataset
```bash
python example_01_local_train.py \
    --model="Test Model" \
    --dataset_name="Test Dataset" \
    --dataset_path=/path/to/correlated/exrs \
    --solution_name="Test Solution" \
    --tracker_path=/path/to/tensorboard/run
```

### Run inference using the best run for the solution
```bash
python example_02_best_infer.py \
    --inputs_path=/path/to/input/images \
    --outputs_path=/path/to/write/masks \
    --solution_name="Test Solution"
```

### Explore the resulting population
```bash
rmtcgui&
```
