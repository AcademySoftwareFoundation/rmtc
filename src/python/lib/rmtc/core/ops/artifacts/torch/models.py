# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.core.ops.artifacts.torch.weights import TorchWeights
from rmtc.core.ops.artifacts.torch.checkpoints import TorchCheckpoint
from rmtc.system import URI, RMTCException, Device
from rmtc.ops.artifacts import Model


class TorchModel(Model):
    """
    PyTorch model artifact with inference and state management capabilities.

    The Torch class extends the base Model to provide PyTorch-specific functionality
    including model execution, weight loading, checkpoint management, and device
    device switching. It integrates PyTorch models with the RMTC artifact system.

    The class handles automatic device placement (CPU/CUDA), type validation for
    inputs and outputs, and provides seamless integration with asset processors
    for data transformation between RMTC assets and PyTorch tensors.
    """

    def __init__(
        self,
        name=None,
        context=None,
        uri=URI(),
        torch_model=None,
        io=None,
        licenses=None,
        input_names=None,
        input_types=None,
        input_packager=None,
        output_names=None,
        output_types=None,
        output_packager=None,
        ancestors=None,
        devices=None,
        dependencies=None,
        trainable=None,
        runner=None,
    ):
        """Initialize Torch model with PyTorch instance and configuration."""
        super(TorchModel, self).__init__(
            name=name,
            context=context,
            uri=uri,
            licenses=licenses,
            ancestors=ancestors,
            devices=devices,
            dependencies=dependencies,
            trainable=trainable,
            runner=runner,
            io=io,
            input_names=input_names,
            input_types=input_types,
            input_packager=input_packager,
            output_names=output_names,
            output_types=output_types,
            output_packager=output_packager,
        )
        self._model = torch_model
        self._device = Device.GPU

    def reset(self):
        """Clear the PyTorch model from memory."""
        self._model = None

    def is_valid(self):
        return self._model is not None

    def get_internal_model(self):
        """Get the PyTorch model instance."""
        return self._model

    def set_internal_model(self, value):
        """Set the PyTorch model instance."""
        self._model = value

    @property
    def torch_model(self):
        """Get the PyTorch model instance."""
        return self._model

    @torch_model.setter
    def torch_model(self, value):
        """Set the PyTorch model instance."""
        self._model = value

    def run(self, inputs):
        """
        Execute model inference on input assets.
        """
        if not self.is_valid():
            raise RMTCException(f"Model {self} is invalid")
        model_input = self.to_input(inputs, self.device)
        model_output = self._model(model_input)
        return self.from_output(model_output, self.device)

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

        # ignore model prefixes
        self._model.load_state_dict(weights.torch_weights, strict=False)

    def create_weights(self, run=None, **kwargs):
        """Create weights artifact from current model state."""
        weights = TorchWeights(model=self, **kwargs)
        weights.torch_weights = self.torch_model.state_dict()
        return self._adopt_result(weights, run, kwargs.get("name"))

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

    def create_checkpoint(self, run=None, **kwargs):
        """Create checkpoint artifact from current model state."""
        checkpoint = TorchCheckpoint(model=self, **kwargs)
        checkpoint.torch_weights = self.torch_model.state_dict()
        return self._adopt_result(checkpoint, run, kwargs.get("name"))

    def move(self, device):
        """Move model to specified execution device (CPU/CUDA)."""
        if self._model is not None:
            if device == Device.GPU:
                self._model.to("cuda")
            elif device == Device.CPU:
                self._model.to("cpu")
        self._device = device

    def get_device(self):
        return self._device


class Torch(TorchModel):
    # HACK : remove
    pass
