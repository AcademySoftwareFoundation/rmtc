# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.system import URI, Context
from rmtc.artifacts import Checkpoint


class TorchCheckpoint(Checkpoint):
    """
    PyTorch checkpoint artifact with model and optimizer state management.

    The TorchCheckpoint class extends the base Checkpoint to provide PyTorch-specific
    functionality for saving and loading both model weights anCd optimizer states.
    This enables complete training state preservation for resuming training sessions.

    Unlike TorchWeights which only stores model parameters, TorchCheckpoint
    maintains the full training context including optimizer state, learning
    rates, and other training-specific information.
    """

    def __init__(
        self,
        uri=URI(),
        project=None,
        model=None,
        licenses=None,
        io=None,
    ):
        """Initialize TorchCheckpoint with PyTorch-specific reader/writer."""
        super(TorchCheckpoint, self).__init__(
            uri=uri,
            project=project,
            model=model,
            io=io,
            licenses=licenses,
        )
        self.add_property("optimizer", str)
        self._model_state = None
        self._optimizer_state = None
        self._context = Context.GPU

    def reset(self):
        """Clear model and optimizer state from memory."""
        self._model_state = None
        self._optimizer_state = None

    def is_valid(self):
        return self._model_state is not None and self._optimizer_state is not None

    @property
    def torch_weights(self):
        """Get the PyTorch model state dictionary."""
        return self._model_state

    @torch_weights.setter
    def torch_weights(self, value):
        """Set the PyTorch model state dictionary."""
        self._model_state = value

    @property
    def torch_optimizer(self):
        """Get the PyTorch optimizer state dictionary."""
        return self._optimizer_state

    @torch_optimizer.setter
    def torch_optimizer(self, value):
        """Set the PyTorch optimizer state dictionary."""
        self._optimizer_state = value

    def to_weights(self):
        """Not implemented"""
        return None

    def move(self, ctx):
        if self._model_state is not None:
            if ctx == Context.GPU:
                self._model_state.to("cuda")
            elif ctx == Context.CPU:
                self._model_state.to("cpu")
        self._context = ctx

    def get_context(self):
        return self._context
