# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


import torch

from rmtc.system import URI, Context, RMTCException
from rmtc.io import IO
from rmtc.artifacts import Weights


class TorchWeightsFile(IO):
    """
    Reader/writer for PyTorch model weights in .pt format.

    The TorchWeightsFile class handles serialization and deserialization of
    PyTorch model weights (state dictionaries) to and from .pt files. It
    provides secure loading with weights_only=True to prevent arbitrary
    code execution during deserialization.

    This reader/writer is specifically designed for TorchWeights artifacts
    and ensures proper device context management during loading operations.
    """

    def create_uri(self, artifact):
        new_uri = URI(scheme="file", host="localhost")
        new_uri.path /= artifact.name
        new_uri.path = new_uri.path.with_suffix(".pt")
        return new_uri

    def is_artifact_supported(self, artifact):
        return isinstance(artifact, Weights)

    def is_uri_supported(self, uri):
        """Check if URI points to a valid .pt file."""
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".pt"
        return False

    def read(self, artifact, uri):
        """Load PyTorch weights from file into artifact."""
        device = "cuda"
        if artifact.get_context() == Context.CPU:
            device = "cpu"
        weights = artifact
        if weights.torch_weights is None:
            if uri.exists():
                weights.torch_weights = torch.load(
                    str(uri.path), weights_only=True, map_location=device
                )

    def write(self, artifact, uri):
        """Save PyTorch weights from artifact to file."""
        weights = artifact
        if weights.torch_weights is not None:
            torch.save(weights.torch_weights, str(uri.path))
        else:
            raise RMTCException("Torch weights is empty")
