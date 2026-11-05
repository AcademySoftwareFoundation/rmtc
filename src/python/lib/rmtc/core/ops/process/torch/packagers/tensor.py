# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Packagers that return tensors
"""

from typing import Any, Optional
import torch
import numpy as np

from rmtc.ops.tensor import Tensor, Array
from rmtc.ops.process import Packager
from rmtc.system import Device, DataType, RMTCException


class SingleTorchTensor(Packager):

    def __init__(
        self,
        contiguous=True,
        data_type=None,
    ):
        super(SingleTorchTensor, self).__init__()
        self.add_property("contiguous", bool, contiguous)
        self.add_property("data_type", DataType, data_type)

    def run(
        self,
        data: list[list[tuple[Array]]],
        device: Optional[Device] = None,
    ) -> Any:
        # single tensor coming in
        out = data[0][0][0]

        # make flat
        if self.contiguous:
            out = np.ascontiguousarray(out)
        if self.data_type is not DataType.INVALID:
            out = out.astype(Tensor.to_array_type(self.data_type))

        # convert to torch
        device_name = "cpu"
        if device == Device.GPU and torch.cuda.is_available():
            device_name = "cuda"
        out = torch.from_numpy(out).to(device_name)

        # return
        return out

    def run_inverse(
        self,
        data: Any,
        device: Optional[Device] = None,
    ) -> list[list[tuple[Array]]]:
        return [[(data,)]]


class BatchedTorchTensor(Packager):

    def __init__(
        self,
        contiguous=True,
        data_type=None,
    ):
        super(BatchedTorchTensor, self).__init__()
        self.add_property("contiguous", bool, contiguous)
        self.add_property("data_type", DataType, data_type)

    def run(
        self,
        data: list[list[tuple[Array]]],
        device: Optional[Device] = None,
    ) -> Any:

        # collect all the tensors into a single array
        tensors = []
        for sample in data:
            tensors.append(sample[0][0])

        # stack all that up
        shape = tensors[0].shape
        for i, tensor in enumerate(tensors):
            if tensor.shape != shape:
                raise RMTCException(
                    f"Cannot batch differing shapes: {shape} vs {i}={tensor.shape}"
                )
        out = np.stack(tensors, axis=0)

        # make flat
        if self.contiguous:
            out = np.ascontiguousarray(out)
        if self.data_type is not DataType.INVALID:
            out = out.astype(Tensor.to_array_type(self.data_type))

        # convert to torch
        device_name = "cpu"
        if device == Device.GPU and torch.cuda.is_available():
            device_name = "cuda"
        out = torch.from_numpy(out).to(device_name)

        # return
        return out

    def run_inverse(
        self,
        data: Any,
        device: Optional[Device] = None,
    ) -> list[list[tuple[Array]]]:

        # unbatch into a list of tensors
        batch_list = data.unbind(0)
        out = []
        for sample in batch_list:
            out.append([(sample.detach().cpu().numpy(),)])
        return out
