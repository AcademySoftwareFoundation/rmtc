# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from pathlib import Path

import torch
from safetensors.torch import load_file, save_file

from rmtc.system import Device, RMTCException
from rmtc.ops.io import IO
from rmtc.ops.artifacts import Weights


class SafetensorsTorchWeightsFile(IO):
    """
    Reader/writer for PyTorch model weights in .safetensors format.
    """

    def create_name(self, artifact):
        return str(Path(artifact.name + ".safetensors"))

    def get_scheme(self):
        return "file"

    def get_artifact_type(self):
        return Weights

    def is_uri_supported(self, uri):
        """Check if URI points to a valid .safetensors file."""
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".safetensors"
        return False

    def read(self, uri, artifact, asset_manager):
        """Load weights from safetensors file into artifact."""
        device = "cpu"
        if artifact.get_device() == Device.GPU and torch.cuda.is_available():
            device = "cuda"
        weights = artifact
        if weights.torch_weights is None:
            if uri.path.exists():
                weights.torch_weights = load_file(str(uri.path), device=device)

    def write(self, uri, artifact, asset_manager):
        """Save artifact weights to safetensors file."""
        weights = artifact
        if weights.torch_weights is not None:
            save_file(weights.torch_weights, str(uri.path))
        else:
            raise RMTCException("Torch weights is empty")
