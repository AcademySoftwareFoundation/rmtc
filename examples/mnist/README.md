# MNIST Training Example

Example of how to use RMTC to train a classification model using the MNIST data, (60,000 28x28 images of handwritten digits (0 to 9) and 10,000 testing images).

## Requirements
- RMTC storage system setup
- Valid config path in env

## Execution

### Go to rmtc examples directory
```bash
cd /path/to/examples
```

### Export the MNIST datasets as EXRs and JSON file with label logits.
If you already have the data downloaded you can specify the directory, otherwise
it will be downloaded using pytorch. Data will be saved to ./mnist_exr
```bash
python 00_exr_export.py --input=/path/to/downloaded/mnist/data --output=/path/to/export/to
```

### Use RMTC to track
This trains the model and generates inferences in ./results
```bash
python 01_train_infer.py --mnist_path=/path/to/export/to
```

### Check the success rate of the model predictions
```bash
python 02_validate_inferences.py --folder=./results
```
