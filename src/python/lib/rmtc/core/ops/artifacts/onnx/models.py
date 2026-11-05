# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.system import URI, RMTCException, Device
from rmtc.ops.artifacts import Model


class ONNXModel(Model):
    """
    ONNX model artifact with inference and state management capabilities.
    """

    def __init__(
        self,
        name=None,
        context=None,
        uri=URI(),
        io=None,
        licenses=None,
        input_names=None,
        input_types=None,
        input_packager=None,
        output_names=None,
        output_types=None,
        output_packager=None,
        ancestors=None,
        onnx_model=None,
        onnx_session=None,
    ):
        # TODO : build input and output shape from the ONNX description

        """Initialize Torch model with ONNX instance and configuration."""
        super(ONNXModel, self).__init__(
            name=name,
            context=context,
            uri=uri,
            io=io,
            licenses=licenses,
            input_names=input_names,
            input_types=input_types,
            input_packager=input_packager,
            output_names=output_names,
            output_types=output_types,
            output_packager=output_packager,
            ancestors=ancestors,
        )
        self._model = onnx_model
        self._session = onnx_session
        self._device = Device.GPU

    def reset(self):
        """Clear the ONNX model from memory."""
        self._session = None
        self._model = None

    def is_valid(self):
        # TODO : this valid check is for a specific runtime
        return self._session is not None

    @property
    def model(self):
        """Get the ONNX model instance."""
        return self._session

    @model.setter
    def model(self, value):
        """Set the ONNX model instance."""
        self._model = value

    @property
    def session(self):
        """Get the ONNX model instance."""
        return self._session

    @session.setter
    def session(self, value):
        """Set the ONNX model instance."""
        self._session = value

    def load_weights(self, weights):
        raise RMTCException(f"ONNX Model {self.uri} cannot load weights {weights.uri}")

    def create_weights(self, run=None, **kwargs):
        raise NotImplementedError()

    def load_checkpoint(self, checkpoint):
        raise RMTCException(f"ONNX Models cannot load checkpoint {checkpoint.uri}")

    def create_checkpoint(self, run=None, **kwargs):
        raise RMTCException(f"ONNX Model {self.uri} cannot create checkpoint ")

    def move(self, device):
        raise NotImplementedError()

    def get_device(self):
        return self._device

    def set_internal_model(self, model):
        self._model = model

    def get_internal_model(self):
        return self._model

    def run(self, inputs):
        model_input = self.to_input(inputs, self.device)
        model_output = self._model(model_input)
        return self.from_output(model_output, self.device)
