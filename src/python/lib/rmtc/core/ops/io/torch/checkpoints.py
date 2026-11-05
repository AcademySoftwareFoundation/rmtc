# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from pathlib import Path

import torch

from rmtc.system import Device, RMTCException
from rmtc.ops.io import IO
from rmtc.ops.artifacts import Checkpoint


class TorchCheckpointFile(IO):
    """
    Reader/writer for PyTorch training checkpoints in .pt format.

    The TorchCheckpointFile class handles serialization and deserialization of
    complete PyTorch training checkpoints including model weights, optimizer
    state, epoch information, and training metrics. This enables full training
    state restoration for resuming interrupted training sessions.

    The checkpoint format includes:
    - Model state dictionary
    - Optimizer state dictionary
    - Current epoch number
    - Optimizer name/type
    - Performance metrics
    """

    def create_name(self, artifact):
        return str(Path(artifact.name + ".pt"))

    def get_scheme(self):
        return "file"

    def get_artifact_type(self):
        return Checkpoint

    def is_uri_supported(self, uri):
        """Check if URI points to a valid .pt file."""
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".pt"
        return False

    def read(self, uri, artifact, asset_manager):
        """
        Load PyTorch checkpoint from file into artifact.

        Loads the complete training state including model weights, optimizer
        state, epoch information, and metrics from the checkpoint file.
        """
        device = "cpu"
        if artifact.get_device() == Device.GPU and torch.cuda.is_available():
            device = "cuda"

        checkpoint = artifact
        if uri.path.exists():
            checkpoint_state = torch.load(
                str(uri.path), weights_only=True, map_location=device
            )

            # Validate required keys exist
            required_keys = [
                "epoch",
                "optimizer_name",
                "model_state",
                "optimizer_state",
                "metric",
            ]
            if not all(key in checkpoint_state for key in required_keys):
                raise RMTCException(
                    f"Invalid checkpoint format, missing required keys: {required_keys}"
                )

            checkpoint.epoch = checkpoint_state["epoch"]
            checkpoint.optimizer = checkpoint_state["optimizer_name"]
            checkpoint.torch_weights = checkpoint_state["model_state"]
            checkpoint.torch_optimizer_state = checkpoint_state["optimizer_state"]
            checkpoint.metric = checkpoint_state["metric"]

    def write(self, uri, artifact, asset_manager):
        """
        Save PyTorch checkpoint from artifact to file.

        Saves the complete training state including model weights, optimizer
        state, epoch information, and metrics to the checkpoint file.
        """
        checkpoint = artifact
        checkpoint_state = {
            "epoch": checkpoint.epoch,
            "optimizer_name": checkpoint.optimizer,
            "model_state": checkpoint.torch_weights,
            "optimizer_state": checkpoint.torch_optimizer_state,
            "metric": checkpoint.metric,
        }
        torch.save(checkpoint_state, str(uri.path))
