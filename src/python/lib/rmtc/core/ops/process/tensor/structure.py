# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


import numpy as np

from rmtc.ops.tensor import Tensor, Array
from rmtc.ops.process import Process
from rmtc.system import DataType


class Batch(Process):
    """
    Tensor batching processor for combining individual tensors into batches.

    The Batch processor stacks multiple input tensors along a new batch dimension
    (axis 0) to create batched data suitable for batch processing in ML models.
    It provides bidirectional transformation between individual tensors and
    batched representations.

    This processor is commonly used in data pipelines to combine individual
    samples into batches for efficient model inference or training.
    """

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        """Stack individual tensors into a single batch tensor."""
        out = np.stack(tensors, axis=0)
        return [out]

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        """Unstack a batch tensor into individual tensors."""
        tensor = tensors[0]
        return [tensor[i] for i in range(tensor.shape[0])]


class ConvertDataType(Process):

    def __init__(
        self,
        to_data_type=None,
        from_data_type=None,
    ):
        super(ConvertDataType, self).__init__()
        self.add_property("to_data_type", DataType, to_data_type)
        self.add_property("from_data_type", DataType, from_data_type)

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        if self.to_data_type is not DataType.INVALID:
            out = []
            for tensor in tensors:
                out.append(tensor.astype(Tensor.to_array_type(self.to_data_type)))
            return tuple(out)
        return tensors

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        if self.from_data_type is not DataType.INVALID:
            out = []
            for tensor in tensors:
                out.append(tensor.astype(Tensor.from_array_type(self.from_data_type)))
            return tuple(out)
        return tensors


class Contiguous(Process):
    """
    Tensor flattening processor for memory layout optimization.
    """

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        out = []
        for tensor in tensors:
            out.append(np.ascontiguousarray(tensor))
        return out

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        "Inverse is a noop"
        return tensors


class Transpose(Process):

    def __init__(
        self,
        axes=None,
    ):
        self.add_property("axes", [int], axes)

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        out = []
        for tensor in tensors:
            out.append(np.transpose(tensor, self.axes))
        return out

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        out = []
        for tensor in tensors:
            out.append(np.transpose(tensor, np.argsort(self.axes)))
        return out
