# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from typing import Any, Optional

from rmtc.ops.process import Packager
from rmtc.system import Device
from rmtc.ops.tensor import Array


class Enclose(Packager):
    """
    Take a stride and span and enclose into a array
    [
        ([X],[Y]),
        ([U],[V]),
        ([X],[Y]),
        ([U],[V]),
        ([X],[Y]),
        ([U],[V]),
    ]
    Stride of 2 and span of 1:
    [
        [
            ([X],[Y]),
            ([U],[V]),
        ],
        [
            ([X],[Y]),
            ([U],[V]),
        ],
        [
            ([X],[Y]),
            ([U],[V]),
        ],
    ]
    """

    def run(
        self,
        data: list[list[tuple[Array]]],
        device: Optional[Device] = None,
    ) -> Any:
        return data

    def run_inverse(
        self,
        data: Any,
        device: Optional[Device] = None,
    ) -> list[list[tuple[Array]]]:
        return data


class Collapse(Packager):
    """
    Opposite of enclose
    """

    def run(
        self,
        data: list[list[tuple[Array]]],
        device: Optional[Device] = None,
    ) -> Any:
        return super(Collapse, self).run_inverse(data, device)

    def run_inverse(
        self,
        data: Any,
        device: Optional[Device] = None,
    ) -> list[list[tuple[Array]]]:
        return super(Collapse, self).run(data, device)
