# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import torch
import torch.onnx

from rmtc.core.ops.artifacts.torch.weights import Weights
from rmtc.core.ops.artifacts.onnx.models import ONNXModel
from rmtc.core.ops.io.onnx.models import ONNXSessionFile

from rmtc.core.ops.process.torch.packagers.tensor import BatchedTorchTensor
from rmtc.core.ops.artifacts.torch.models import TorchModel
from rmtc.core.ops.process.packagers.tensor import Batch
from rmtc.core.ops.process.packagers.dictionary import ToDict

from rmtc.ops.pipeline import Builder
from rmtc.ops.process import PackagerStack, ProcessPackager
from rmtc.system import Device, RMTCException


class ONNXBuilder(Builder):
    """
    Create an ONNX model - works only for batched torch tensors
    """

    def __init__(
        self,
        opset=18,
    ):
        super(ONNXBuilder, self).__init__()
        self._opset = opset

    def is_supported(self, artifact):
        # Only support batched tensor to tensor models right now
        if artifact is None:
            return False
        if not isinstance(artifact, Weights):
            return False
        model = artifact.model
        if model is None:
            return False
        if not isinstance(model, TorchModel):
            return False
        supported_packagers = (ProcessPackager, BatchedTorchTensor)
        if not isinstance(model.input_packager, supported_packagers):
            return False
        if not isinstance(model.output_packager, supported_packagers):
            return False
        return True

    def __call__(self, asset_manager, artifact, options=None):
        model = artifact.model
        weights = artifact

        if model is None or weights is None:
            raise RMTCException(f"Model {model} or weights {weights} is invalid")

        # construct an associated onnx file
        uri = asset_manager.resolve([weights.uri])[0]
        uri.path = uri.path.with_suffix(".onnx")

        # TODO : convert other packagers to be ONNX compatible
        input_packager = ProcessPackager(
            processors=[proc.duplicate() for proc in model.input_packager.processors],
            packager=PackagerStack(
                stack=[
                    Batch(),
                    ToDict(names=model.input_names),
                ],
            ),
        )
        output_packager = ProcessPackager(
            processors=[proc.duplicate() for proc in model.output_packager.processors],
            packager=PackagerStack(
                stack=[
                    Batch(),
                    ToDict(names=model.output_names),
                ],
            ),
        )

        # construct a new ONNX model item from the weights/model
        onnx_model = ONNXModel(
            name=weights.name + "_ONNX",
            uri=uri,
            input_names=model.input_names,
            input_types=model.input_types,
            input_packager=input_packager,
            output_names=model.output_names,
            output_types=model.output_types,
            output_packager=output_packager,
            io=ONNXSessionFile(device=artifact.device),
        )

        # push all to same device
        device = Device.CPU
        if torch.cuda.is_available():
            device = Device.GPU

        # construct inputs
        input_assets = []
        for input_type in model.input_types:
            input_asset = input_type.type_class()
            input_asset.init()
            input_assets.append(input_asset)
        torch_input = model.to_input([input_assets], device=device)

        # read the torch model
        asset_manager.read([model])
        torch_model = model.torch_model

        # convert to torch
        torch_model.to("cuda" if device == Device.GPU else "cpu")

        # construct the model input
        torch_model.eval()
        torch.onnx.export(
            torch_model,
            torch_input,
            str(onnx_model.uri.path),
            input_names=onnx_model.input_names,
            output_names=onnx_model.output_names,
            opset_version=self._opset,
        )

        # unload torch model
        model.reset()

        return [onnx_model]
