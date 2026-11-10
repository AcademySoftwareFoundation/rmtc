# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Packagers that return tensors
"""
from typing import Any, Optional

from rmtc.system import Device
from rmtc.ops.tensor import Array
from rmtc.ops.process import Packager


class ONNXTensor(Packager):

    def run(
        self,
        data: list[list[tuple[Array]]],
        device: Optional[Device] = None,
    ) -> Any:
        # take the batches coming in
        # make a map of the items
        return data

    def run_inverse(
        self,
        data: Any,
        device: Optional[Device] = None,
    ) -> list[list[tuple[Array]]]:
        return data
