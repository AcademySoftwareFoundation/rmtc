# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Packagers that return tensors
"""

from typing import Any, Optional
import numpy as np

from rmtc.ops.tensor import Array
from rmtc.ops.process import Packager
from rmtc.system import Device


class Pop(Packager):
    """
    Given a batch of tensor tuples extract nominated element tensors by index

    take list of samples and an element index of 0
    [ #samples
        [ #elements
            ([X],[Y]),
        ],
        [
            ([X],[Y]),
        ]
    ]

    the first element of 2 tensors is split
    [
        [
            ([X],),
        ],
        [
            ([Y],)
        ],
        [
            ([X],[Y]),
        ]
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


class Append(Pop):
    """
    Opposite of pop
    """

    def run(
        self,
        data: list[list[tuple[Array]]],
        device: Optional[Device] = None,
    ) -> Any:
        return super(Append, self).run_inverse(data)

    def run_inverse(
        self,
        data: Any,
        device: Optional[Device] = None,
    ) -> list[list[tuple[Array]]]:
        return super(Append, self).run(data)


class Split(Packager):
    """
    Given an array of element indices - split the tensor along an axis

    For example, elements to combine [0]
    [
        [
            ([X,Y],),
        ],
    ]

    The result is a tuple of 2 tensors
    [
        [
            ([X],[Y]),
        ],
    ]
    The first 2 elements are combined in the order of the element indices
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


class Cat(Split):
    """
    Opposite of split
    """

    def run(
        self,
        data: list[list[tuple[Array]]],
        device: Optional[Device] = None,
    ) -> Any:
        return super(Cat, self).run_inverse(data)

    def run_inverse(
        self,
        data: Any,
        device: Optional[Device] = None,
    ) -> list[list[tuple[Array]]]:
        return super(Cat, self).run(data)


class Batch(Packager):
    """
    The output of this packager is a single tensor where all the inputs are batched
    and padded into one tensor - note this will be huge for tensors of various sizes
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
    This is collapsed into 1 sample, with batched tensors
    [
        [
            ([3,X],[3,Y]),
            ([3,U],[3,V]),
        ],
    ]
    """

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
        out = np.stack(tensors, axis=0)

        # return
        return out

    def run_inverse(
        self,
        data: Any,
        device: Optional[Device] = None,
    ) -> list[list[tuple[Array]]]:
        """Unstack a batch tensor into individual tensors."""
        # unbatch into a list of tensors
        tensors = list(data)

        # arrange the tensor list into the RMTC data structure
        out = []
        for tensor in tensors:
            out.append([(tensor,)])
        return out


class Unbatch(Batch):
    """
    Opposite of batch
    """

    def run(
        self,
        data: list[list[tuple[Array]]],
        device: Optional[Device] = None,
    ) -> Any:
        return super(Unbatch, self).run_inverse(data)

    def run_inverse(
        self,
        data: Any,
        device: Optional[Device] = None,
    ) -> list[list[tuple[Array]]]:
        return super(Unbatch, self).run(data)
