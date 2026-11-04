# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.system import DataType
from rmtc.ops.process import Process, ProcessStack
from rmtc.core.ops.process.image.color import LinearNormalize
from rmtc.core.ops.process.tensor.structure import ConvertDataType
from rmtc.core.ops.process.image.channels import (
    MoveChannelsFirst,
    Flip,
    TrimAlpha,
)


class TorchvisionFormat(Process):
    """
    [CHW] float32 0/+1 RGB
    """

    def __init__(self):
        super(TorchvisionFormat, self).__init__()
        self._processor = ProcessStack(
            [
                TrimAlpha(),
                # LinearNormalize(scale_range=[0,1]),
                ConvertDataType(to_data_type=DataType.FLOAT32),
                MoveChannelsFirst(),
            ]
        )

    def run(self, tensors):
        return self._processor.run(tensors)

    def run_inverse(self, tensors):
        return self._processor.run_inverse(tensors)


class PyTorchFormat(Process):
    """
    [CHW] float32 -1/+1 RGB
    """

    def __init__(self):
        super(PyTorchFormat, self).__init__()
        self._processor = ProcessStack(
            [
                TrimAlpha(),
                LinearNormalize(scale_range=[-1, 1]),
                ConvertDataType(to_data_type=DataType.FLOAT32),
                MoveChannelsFirst(),
            ]
        )

    def run(self, tensors):
        return self._processor.run(tensors)

    def run_inverse(self, tensors):
        return self._processor.run_inverse(tensors)


class KerasFormat(Process):
    """
    [HWC] float32 -1/+1 RGB
    """

    def __init__(self):
        super(KerasFormat, self).__init__()
        self._processor = ProcessStack(
            [
                TrimAlpha(),
                LinearNormalize(scale_range=[-1, 1]),
                ConvertDataType(to_data_type=DataType.FLOAT32),
            ]
        )

    def run(self, tensors):
        return self._processor.run(tensors)

    def run_inverse(self, tensors):
        return self._processor.run_inverse(tensors)


class OpenCVFormat(Process):
    """
    [HWC] int8 0/255 BGR
    """

    def __init__(self):
        super(OpenCVFormat, self).__init__()
        self._processor = ProcessStack(
            [
                TrimAlpha(),
                Flip(),
                LinearNormalize(scale_range=[0, 1]),
                ConvertDataType(to_data_type=DataType.INT8),
            ]
        )

    def run(self, tensors):
        return self._processor.run(tensors)

    def run_inverse(self, tensors):
        return self._processor.run_inverse(tensors)


class OIIOFormat(Process):
    """
    [HWC] float32 0/+1 RGBA
    """

    def __init__(self):
        super(OIIOFormat, self).__init__()
        self._processor = ProcessStack(
            [
                LinearNormalize(scale_range=[0, 1]),
                ConvertDataType(to_data_type=DataType.FLOAT32),
            ]
        )

    def run(self, tensors):
        return self._processor.run(tensors)

    def run_inverse(self, tensors):
        return self._processor.run_inverse(tensors)


class TensorflowFormat(KerasFormat):
    """
    Same as Keras
    """

    pass


class ONNXFormat(TorchvisionFormat):
    """
    Same as Torchvision
    """

    pass
