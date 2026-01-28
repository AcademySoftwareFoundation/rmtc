# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


import torch

from rmtc.system import URI, Context, RMTCException
from rmtc.io import IO
from rmtc.artifacts import Checkpoint


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

    def create_uri(self, artifact):
        new_uri = URI(scheme="file", host="localhost")
        new_uri.path /= artifact.name
        new_uri.path = new_uri.path.with_suffix(".pt")
        return new_uri

    def is_artifact_supported(self, artifact):
        return isinstance(artifact, Checkpoint)

    def is_uri_supported(self, uri):
        """Check if URI points to a valid .pt file."""
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".pt"
        return False

    def read(self, artifact, uri):
        """
        Load PyTorch checkpoint from file into artifact.

        Loads the complete training state including model weights, optimizer
        state, epoch information, and metrics from the checkpoint file.
        """
        device = "cuda"
        if artifact.get_context() == Context.CPU:
            device = "cpu"

        checkpoint = artifact
        if checkpoint.uri.exists():
            checkpoint_state = torch.load(
                str(uri.path), weights_only=False, map_location=device
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
            checkpoint.optimizer_name = checkpoint_state["optimizer_name"]
            checkpoint.torch_weights = checkpoint_state["model_state"]
            checkpoint.torch_optimizer = checkpoint_state["optimizer_state"]
            checkpoint.metric = checkpoint_state["metric"]

    def write(self, artifact, uri):
        """
        Save PyTorch checkpoint from artifact to file.

        Saves the complete training state including model weights, optimizer
        state, epoch information, and metrics to the checkpoint file.
        """
        checkpoint = artifact
        checkpoint_state = {
            "epoch": checkpoint.epoch,
            "optimizer_name": checkpoint.optimizer_name,
            "model_state": checkpoint.torch_weights,
            "optimizer_state": checkpoint.torch_optimizer,
            "metric": checkpoint.metric,
        }
        torch.save(checkpoint_state, str(uri.path))
