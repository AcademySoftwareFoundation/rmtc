# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from pathlib import Path

import torch

from rmtc.system import Device, RMTCException
from rmtc.ops.io import IO
from rmtc.ops.artifacts import Weights


class TorchWeightsFile(IO):
    """
    Reader/writer for PyTorch model weights in .pt format.

    The TorchWeightsFile class handles serialization and deserialization of
    PyTorch model weights (state dictionaries) to and from .pt files. It
    provides secure loading with weights_only=True to prevent arbitrary
    code execution during deserialization.

    This reader/writer is specifically designed for TorchWeights artifacts
    and ensures proper device device management during loading operations.
    """

    def create_name(self, artifact):
        return str(Path(artifact.name + ".pt"))

    def get_scheme(self):
        return "file"

    def get_artifact_type(self):
        return Weights

    def is_uri_supported(self, uri):
        """Check if URI points to a valid .pt file."""
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".pt"
        return False

    def read(self, uri, artifact, asset_manager):
        """Load PyTorch weights from file into artifact."""
        device = "cpu"
        if artifact.get_device() == Device.GPU and torch.cuda.is_available():
            device = "cuda"
        weights = artifact
        if weights.torch_weights is None:
            if uri.path.exists():
                weights.torch_weights = torch.load(
                    str(uri.path), weights_only=True, map_location=device
                )

    def write(self, uri, artifact, asset_manager):
        """Save PyTorch weights from artifact to file."""
        weights = artifact
        if weights.torch_weights is not None:
            torch.save(weights.torch_weights, str(uri.path))
        else:
            raise RMTCException("Torch weights is empty")
