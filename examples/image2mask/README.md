# Image2Mask Example

This is an example of how to refine a foundational image to mask model on shot data, trained on your local machine with the best training session used to process an additional set of images.

## Requirements
- RMTC storage system setup
- A foundational model that has been exported as a pytorch package with all dependencies interned
- A folder of paired EXRs which are color to mask correlates, interleaved in alphanumeric order
- A folder of color EXRs to infer against
- Valid config path in env

The foundational model assumes a ImageNet/PyTorch tensor format, the process stack reflects this:
- BCHW Float32 contiguous
- Input is ResNet Normalized RGB
- Output is Unormalized Mono

Packaging the model can be done through the `rmtc_core.artifacts.io.models.torch.TorchPackage.package_model`. The aim is to 'assetize' the python class into a pipelinable file.

## Execution
Run the create artifacts script first - to create the datasets and models. Run local train to run the regressor on your local machine. Run best infer to find the best run and evaluate against the input EXR images.

Once ran you can explore the results in rmtc-gui.

### Go to rmtc examples directory
```bash
cd /path/to/examples
```

### Create all the artefacts in the DB
```bash
python 00_create_artifacts.py \
    --model_name=<name of model> \
    --model_path=/path/to/model/pytorch \
    --model_package=<pytorch package name> \
    --model_class_name=<pytorch class name> \
    --model_type=CLASSIFICATION \
    --dataset_path=/path/to/interleaved/exrs \
    --dataset_name=<dataset name> \
    --solution_path=/path/to/location/to/save/checkpoints/weights \
    --solution_name=<name of solution>
```

### Run a local regression training system
```bash
python 01_local_train.py \
    --model=<name of model> \
    --dataset=<dataset name> \
    --solution=<name of solution>
```

### Get the solution, find best run and run inference
```bash
python 02_best_infer.py \
    --results_path=/path/to/place/to/output/result \
    --input_path=/path/to/folder/of/input/exrs \
    --solution=<name of solution>
```

### Open the explorer
```bash
rmtc-gui&
```



