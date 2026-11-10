# MNIST Training Example

Example of how to use RMTC to train a classification model using the MNIST data, (60,000 28x28 images of handwritten digits (0 to 9) and 10,000 testing images).

## Requirements
- RMTC storage system setup
- Valid config path in env

## Execution

### Go to the mnist examples directory
```bash
cd /path/to/examples/mnist
```

### Export the MNIST datasets as EXRs and JSON file with label logits.
If you already have the data downloaded you can specify the directory, otherwise
it will be downloaded using pytorch. Data will be saved to ./mnist_exr
```bash
python example_00_export_exrs.py --input=/path/to/downloaded/mnist/data --output=/path/to/export/to
```

### Use RMTC to track
This trains the model and generates inferences in ./results
```bash
python example_01_train_infer.py \
    --solution_path=/path/to/solution \
    --mnist_path=/path/to/export/to \
    --results_path=/path/to/results
```

### Check the success rate of the model predictions
```bash
python example_02_validate.py --folder=./results
```
