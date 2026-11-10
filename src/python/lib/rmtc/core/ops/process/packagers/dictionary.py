# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Packagers that return tensors
"""

from typing import Any, Optional

from rmtc.ops.tensor import Tensor, Array
from rmtc.ops.process import Packager
from rmtc.system import Device

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


class PackDict(Packager):
    """
    Specify a dict of entries and the index from the sample and the insert position:

    Given:
    elements =
    {
        "name1" : 1,
        "name2" : 2,
    }
    insert_position = 1

    data =
    [ #samples
        [#elements
            [X],
            [Y],
            [Z]
        ]
    ]

    out =
    [ #samples
        [#elements
            [X],
            {
            }
        ]
    ]

    """

    def __init__(
        self,
        elements_to_pack=None,
        insert_position=0,
    ):
        super(PackDict, self).__init__()
        self.add_property("elements", dict, elements_to_pack)
        self.add_property("insert_position", int, insert_position)

    def is_valid_input(self, data):
        if not isinstance(data, list):
            return False
        if len(data) > 0:
            sample = data[0]
            if not isinstance(sample, list):
                return False
            if len(sample) > 0:
                element = sample[0]
                if not isinstance(element, tuple):
                    return False
                if len(element) > 0:
                    tensor = element[0]
                    if not isinstance(tensor, Tensor):
                        return False
        return True

    def is_valid_output(self, data):
        if not isinstance(data, list):
            return False
        if len(data) > 0:
            sample = data[0]
            if not isinstance(sample, list):
                return False
            if len(sample) > 0:
                element = sample[0]
                if not isinstance(element, tuple):
                    return False
                if len(element) > 0:
                    tensor = element[0]
                    if not isinstance(tensor, Tensor):
                        return False
        return True

    def run(
        self,
        data: list[list[tuple[Array]]],
        device: Optional[Device] = None,
    ) -> Any:

        out = []

        # process each sample
        for sample in data:

            # for each sample - iterate on the new elements
            # insert them in sequence into the new dict
            indices = []
            new_dict = {}
            for key, index in self.elements:
                new_dict[key] = sample[i]
                indices.append(index)

            # build up the new sample replacing the packed elements
            # with a single dict inserted into the new position
            new_sample = []
            for i, element in enumerate(sample):
                if i in indices:
                    continue
                if i == self.insert_position:
                    new_sample.append(new_dict)
                else:
                    new_sample.append(element)
            out.append(new_sample)

        return out

    def run_inverse(
        self,
        data: Any,
        device: Optional[Device] = None,
    ) -> list[list[tuple[Array]]]:
        out = []

        # for each sample
        for sample in data:

            # init new length - including the unpacked dict, less it's dict index
            new_length = len(sample) + len(new_dict) - 1
            new_sample = [None] * new_length

            # get the dict from the insert position and split off according
            # to the element input map
            indices = []
            new_dict = sample[self.insert_position]
            for key, index in self.elements:
                indices.append(index)
                new_sample[index] = new_dict[key]

            # now cycle through the length of the new sample
            # skip over any sample we have already allocated
            # and append the existing element, if it isn't in the
            # dict insert position
            element_offset = 0
            for i in range(new_length):
                if i not in indices:
                    if element_offset != self.insert_position:
                        new_sample[i] = sample[element_offset]
                    element_offset += 1
            out.append(new_sample)

        return out


class ToDict(Packager):
    """
    Batch all the single tensors and place the batched tensors into a named
    dict entry
    """

    def __init__(
        self,
        names=None,
    ):
        super(ToDict, self).__init__()
        self.add_property("names", [str], names)

    def is_valid_input(self, data):
        # list[list[tuple[Array]]]
        if not isinstance(data, list):
            return False
        if len(data) > 0:
            sample = data[0]
            if not isinstance(sample, list):
                return False
            if len(sample) > 0:
                element = sample[0]
                if not isinstance(element, tuple):
                    return False
                if not len(element) == 1:  # must be only 1 tensor
                    return False
                tensor = element[0]
                if not isinstance(tensor, Tensor):
                    return False
        return True

    def is_valid_output(self, data):
        # dict[Array]
        if not isinstance(data, dict):
            return False
        if len(data) > 0:
            tensor = data.values()[0]
            if not isinstance(tensor, Tensor):
                return False
        return True

    def run(
        self,
        data: list[list[tuple[Array]]],
        device: Optional[Device] = None,
    ) -> Any:

        # take a single sample of elements
        # [ #samples
        #     [ #elements
        #         ([X],),
        #         ([Y],),
        #         ([Z],),
        #     ],
        # ]
        # turn into dict with the names with a combined batched tensor
        # { #dict of elements
        #     "a": [X],
        #     "c": [Y],
        #     "d": [Z],
        # }

        out = {}
        for name, tensors in zip(self.names, data):
            out[name] = tensors[0]

        return out

    def run_inverse(
        self,
        data: Any,
        device: Optional[Device] = None,
    ) -> list[list[tuple[Array]]]:

        # take dictionary of tensors and turn into list of tensor samples
        # this:
        # { #dict of elements
        #     "a": [X],
        #     "c": [Y],
        #     "d": [Z],
        # }
        # becomes:
        # [ #samples
        #     [ #elements
        #         ([X],),
        #         ([Y],),
        #         ([Z],),
        #     ],
        # ]
        out = []
        for value in data.values():
            out.append([(value,)])
        return out
