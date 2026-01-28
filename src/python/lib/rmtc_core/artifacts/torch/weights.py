# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


from rmtc.system import URI, Context
from rmtc.artifacts import Weights


class TorchWeights(Weights):
    """
    PyTorch model weights artifact for trained parameter storage.

    The TorchWeights class extends the base Weights to provide PyTorch-specific
    functionality for storing and loading trained model parameters. It handles
    PyTorch state dictionaries and integrates with the RMTC artifact system.

    This class is used to persist trained model parameters separately from
    the model architecture, enabling weight sharing across different model
    instances and training sessions.
    """

    def __init__(
        self,
        uri=URI(),
        project=None,
        model=None,
        licenses=None,
        io=None,
    ):
        """Initialize TorchWeights with PyTorch-specific reader/writer."""
        super(TorchWeights, self).__init__(
            uri=uri,
            project=project,
            model=model,
            io=io,
            licenses=licenses,
        )
        self._model_state = None
        self._context = Context.GPU

    def is_valid(self):
        return self._model_state is not None

    @property
    def torch_weights(self):
        """Get the PyTorch model state dictionary."""
        return self._model_state

    @torch_weights.setter
    def torch_weights(self, value):
        """Set the PyTorch model state dictionary."""
        self._model_state = value

    def reset(self):
        """Clear model state from memory."""
        self._model_state = None

    def get_context(self):
        """Return the current context - not persistent"""
        return self._context

    def move(self, ctx):
        if self._model_state is not None:
            if ctx == Context.GPU:
                self._model_state.to("cuda")
            elif ctx == Context.CPU:
                self._model_state.to("cpu")
        self._context = ctx
