# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import torch

from rmtc_core.artifacts.torch.weights import TorchWeights
from rmtc_core.artifacts.torch.checkpoints import TorchCheckpoint
from rmtc.system import URI, RMTCException, Context
from rmtc.artifacts import Model


class Torch(Model):
    """
    PyTorch model artifact with inference and state management capabilities.

    The Torch class extends the base Model to provide PyTorch-specific functionality
    including model execution, weight loading, checkpoint management, and device
    context switching. It integrates PyTorch models with the RMTC artifact system.

    The class handles automatic device placement (CPU/CUDA), type validation for
    inputs and outputs, and provides seamless integration with asset processors
    for data transformation between RMTC assets and PyTorch tensors.
    """

    def __init__(
        self,
        name=None,
        project=None,
        uri=URI(),
        torch_model=None,
        io=None,
        asset_to_input=None,
        asset_to_output=None,
        licenses=None,
        input_type=None,
        output_type=None,
        ancestors=None,
        input_shape=None,
        output_shape=None,
    ):
        """Initialize Torch model with PyTorch instance and configuration."""
        super(Torch, self).__init__(
            name=name,
            project=project,
            uri=uri,
            io=io,
            asset_to_input=asset_to_input,
            asset_to_output=asset_to_output,
            input_shape=input_shape,
            output_shape=output_shape,
            licenses=licenses,
            input_type=input_type,
            output_type=output_type,
            ancestors=ancestors,
        )
        self._model = torch_model
        self._context = Context.GPU

    def reset(self):
        """Clear the PyTorch model from memory."""
        self._model = None

    def is_valid(self):
        return self._model is not None

    @property
    def torch_model(self):
        """Get the PyTorch model instance."""
        return self._model

    @torch_model.setter
    def torch_model(self, value):
        """Set the PyTorch model instance."""
        self._model = value

    def __call__(self, assets, context=Context.GPU):
        """
        Execute model inference on input assets.

        Performs end-to-end inference including input validation, device placement,
        tensor conversion, model execution, and output conversion back to assets.
        """
        if len(assets) == 0:
            return None
        ctx = "cuda"
        if context == Context.CPU:
            ctx = "cpu"
        self._model.to(ctx)
        for a in assets:
            if not isinstance(a, self.input_type.type_class):
                raise RMTCException(
                    f"Invalid input type {self.input_type.__name__}, got {a.__class__.__name__}"
                )
            if not a.is_valid():
                raise RMTCException(f"Invalid asset {a}")
        input_tensors = self.assets_to_input_tensors(assets)
        if len(input_tensors) == 0:
            raise RMTCException("No input tensors generated from assets")
        input_tensor = input_tensors[0]
        torch_input_tensor = torch.from_numpy(input_tensor).to(ctx)
        torch_output_tensor = self._model(torch_input_tensor)
        output_tensor = torch_output_tensor.detach().cpu().numpy()
        results = self.output_tensors_to_assets([output_tensor])
        for a in results:
            if not isinstance(a, self.output_type.type_class):
                raise RMTCException(
                    f"Invalid output type {self.output_type.__name__}, got {a.__class__.__name__}"
                )
        return results

    def load_weights(self, weights):
        """
        Load trained weights into the model.
        """
        if self._model is None:
            raise RMTCException(f"Invalid model: {self.uri}")
        if not weights.is_valid():
            raise RMTCException(f"Invalid weights {weights}")
        if not isinstance(weights, TorchWeights):
            raise RMTCException("Invalid weights - Torch model requires TorchWeights")
        # TODO : should the weights move, seems too heavy
        if weights.torch_weights is None:
            raise RMTCException(f"Invalid weights: {weights.uri}")

        self._model.load_state_dict(weights.torch_weights)

    def create_weights(self, io):
        """Create weights artifact from current model state."""
        weights = TorchWeights(model=self, io=io)
        weights.torch_weights = self.torch_model.state_dict()
        return weights

    def load_checkpoint(self, checkpoint):
        """
        Load model state from checkpoint.
        """
        if self._model is None:
            raise RMTCException(f"Invalid model {self.uri}")
        if not checkpoint.is_valid():
            raise RMTCException(f"Invalid checkpoint {checkpoint}")
        if not isinstance(checkpoint, TorchCheckpoint):
            raise RMTCException(
                "Invalid checkpoint - Torch model requires TorchCheckpoint"
            )
        if checkpoint.torch_weights is None:
            raise RMTCException("Invalid checkpoint")
        self._model.load_state_dict(checkpoint.torch_weights)

    def create_checkpoint(self, io):
        """Create checkpoint artifact from current model state."""
        checkpoint = TorchCheckpoint(model=self, io=io)
        checkpoint.torch_weights = self.torch_model.state_dict()
        return checkpoint

    def move(self, ctx):
        """Move model to specified execution context (CPU/CUDA)."""
        if self._model is not None:
            if ctx == Context.GPU:
                self._model.to("cuda")
            elif ctx == Context.CPU:
                self._model.to("cpu")
        self._context = ctx

    def get_context(self):
        return self._context
