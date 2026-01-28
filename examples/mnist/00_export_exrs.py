#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

# The dataset is 285 MB

# Example usage:
# ./mnist_exr_export.py --mnist_data /path/to/downloaded/mnist/data

import argparse
import json
import os

import cv2
import numpy as np
from torchvision import transforms, datasets

from rmtc.system import Logger

parser = argparse.ArgumentParser(
    description="Script that exports MNIST images as EXRs with labels."
)
parser.add_argument(
    "--input", 
    type=str, 
    default="./original",
    help="Directory containing MNIST data"
)
parser.add_argument(
    "--output", 
    type=str, 
    default="./exr",
    help="Directory containing MNIST data"
)
args = parser.parse_args()
log = Logger()

###############################################################################

def export_mnist_exrs(output_dir, train=True, data_dir="./data"):
    """Save the MNIST dataset as EXR images and a corresponding json or csv.

    Args:
        output_dir (str): Output directory path
        train (bool): If true, exports the training data, otherwise exports the testing data
        data_dir (str): Directory containing downloaded MNIST data
        save_csv (bool): If true, export as CSV instead of JSON
    """
    # Load the MNIST dataset

    # The ToTensor() transform will convert the PIL images to a PyTorch tensor,
    # scaling the pixel values to the range [0.0, 1.0]
    transform = transforms.ToTensor()

    dataset = datasets.MNIST(
        root=data_dir,
        train=train,
        download=True,
        transform=transform,
    )

    exr_output_dir = os.path.join(output_dir, "exr")
    if not os.path.exists(exr_output_dir):
        os.makedirs(exr_output_dir, exist_ok=True)

    export_data = []

    # Iterate through the dataset and save each image as EXR
    for i, (image_tensor, label) in enumerate(dataset):

        # Ensure the image is on the CPU
        image_tensor = image_tensor.cpu()

        # PyTorch tensors are typically in C,H,W format.
        # OpenCV expects H,W,C for color images, but for grayscale H,W is fine
        # The MNIST images are grayscale (1, 28, 28)

        # Convert the PyTorch tensor to a NumPy array.
        # Use squeeze() to remove the channel dimension, making it 28x28
        np_image = image_tensor.squeeze().numpy()

        # Normalize the image data to a floating-point range of [0, 1] (already handled
        # by ToTensor()) and ensure float32 for the EXR format
        np_image = np_image.astype(np.float32)

        # Convert the PyTorch tensor to a NumPy array.
        # The image_tensor from MNIST will have the shape (1, 28, 28),
        # representing (channels, height, width). We squeeze the channel dimension
        # to get a shape of (28, 28) for a grayscale image
        np_image = np.squeeze(np_image)

        # Convert to a 3 channel image for RMTC
        np_image = np.stack([np_image, np_image, np_image], axis=-1)

        # Export EXR
        output_path = os.path.join(exr_output_dir, "mnist_{:05d}_{}.exr".format(i, label))
        if not os.path.exists(output_path):
            success = cv2.imwrite(output_path, np_image)
            if not success:
                log.error(f"Error: Could not create output file for {output_path}")
                continue

        rmtc_exr_uri = "file://localhost{}".format(os.path.abspath(output_path))

        # Convert label to integer logit tensor
        label_logits = [0.0] * 10
        label_logits[label] = 1.0
        export_data.append([rmtc_exr_uri, label_logits])

        # Save label integer value
        # export_data.append([rmtc_exr_uri,[label]])

        # Print progress
        if (i + 1) % 1000 == 0:
            log.info("Saved {} {} images to EXR format...".format(
                i + 1, "training" if train else "testing"))

    # Save JSON file
    json_data = {}
    for exr_uri, label in export_data:
        json_data[exr_uri] = label

    json_file_path = os.path.join(output_dir, "mnist_exr_dataset.json")
    with open(json_file_path, "w") as json_file:
        json.dump(json_data, json_file, indent=4)

    log.info("json file created: {}".format(json_file_path))


data_dir = args.input

# Export the 60,000 training images and labels
export_mnist_exrs(f"{args.output}/train", train=True, data_dir=data_dir)

# Export the 10,000 testing images and labels
export_mnist_exrs(f"{args.output}/test", train=False, data_dir=data_dir)

log.info("Conversion complete")
