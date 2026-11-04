# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from __future__ import division

import numpy as np

from rmtc.ops.tensor import Array
from rmtc.ops.process import Process


class TrimAlpha(Process):
    """
    [WH4] -> [WH3]
    Alpha channel removal processor for RGBA to RGB conversion.

    The TrimAlpha processor removes the alpha channel from RGBA images,
    converting 4-channel tensors to 3-channel RGB tensors. The inverse
    operation adds a fully opaque alpha channel (value 1.0) to RGB images.

    This processor is useful when working with image formats that include
    transparency information but the downstream processing only expects
    RGB data.
    """

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        """Remove alpha channel from RGBA tensors."""
        out = []
        for tensor in tensors:
            out.append(tensor[:, :, :3])
        return out

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        """Add opaque alpha channel to RGB tensors."""
        out = []
        for tensor in tensors:
            h, w, c = tensor.shape  # pylint: disable=unused-variable
            alpha = np.full((h, w, 1), 1.0, dtype=np.float32)
            out.append(np.concatenate([tensor, alpha], axis=2))
        return out


class Shuffle(Process):
    """
    [WHC] -> [HWC]
    """

    def __init__(
        self,
        order=None,
    ):
        super(Shuffle, self).__init__()
        self.add_property("order", [int], order)

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        out = []
        for tensor in tensors:
            if len(tensor.shape) == 4:
                out.append(tensor.transpose(self.order))
            else:
                out.append(tensor.transpose(self.order))
        return out

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        return self.run(tensors)


class Flip(Process):
    """
    RGB -> BGR
    """

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        out = []
        for tensor in tensors:
            if len(tensor.shape) == 4:
                out.append(tensor.transpose(2, 1, 0, 3))
            else:
                out.append(tensor.transpose(2, 1, 0))
        return out

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        return self.run(tensors)


class SwapWidthHeight(Process):
    """
    [WHC] -> [HWC]
    """

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        out = []
        for tensor in tensors:
            if len(tensor.shape) == 4:
                out.append(tensor.transpose(1, 0, 2, 3))
            else:
                out.append(tensor.transpose(1, 0, 2))
        return out

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        return self.run(tensors)


class ExtractChannel(Process):
    """
    [WH4] -> [WH1]
    Remove all but 1 nominated channel on an RGBA tensor
    """

    def __init__(
        self,
        channel=0,
    ):
        super(ExtractChannel, self).__init__()
        self.add_property("channel", int, channel)

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        out = []
        for tensor in tensors:
            out.append(tensor[:, :, self.channel : self.channel + 1])
        return out

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        out = []
        for tensor in tensors:
            h, w, _ = tensor.shape
            alpha = np.ones((h, w, 1), dtype=np.float32)
            out.append(np.concatenate([tensor, tensor, tensor, alpha], axis=2))
        return out


class AddChannel(Process):
    """
    [WH] -> [WHC]
    Repeat the tensor over to fill RGBA
    """

    def __init__(
        self,
        channel=0,
    ):
        super(AddChannel, self).__init__()
        self.add_property("channel", int, channel)

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        out = []
        for tensor in tensors:
            tensor = tensor[:, :, self.channel]
            out.append(tensor)
        return out

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        out = []
        for tensor in tensors:
            tensor = tensor.squeeze(self.channel)
            out.append(tensor)
        return out


class ExpandChannel(Process):
    """
    [WH1] -> [WH4]
    Repeat the tensor over to fill RGBA
    """

    def __init__(
        self,
        channel=0,
    ):
        super(ExpandChannel, self).__init__()
        self._extract = ExtractChannel(channel=channel)

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        return self._extract.run_inverse(tensors)

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        return self._extract.run(tensors)


class MoveChannelsFirst(Process):
    """
    [WHC] -> [CWH]

    Channel dimension reordering processor for HWC to CHW conversion.

    The MoveChannelsFirst processor transposes image tensors from Height-Width-Channel
    (HWC) format to Channel-Height-Width (CHW) format. This is commonly required
    when interfacing between different deep learning frameworks or when preparing
    data for models that expect channels-first format (e.g., PyTorch).

    The processor validates input format and provides bidirectional conversion
    between HWC and CHW layouts.
    """

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        """Convert tensors from HWC to CHW format."""
        out = []
        for tensor in tensors:
            out.append(np.transpose(tensor, (2, 0, 1)))
        return out

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        """Convert tensors from CHW to HWC format."""
        out = []
        for tensor in tensors:
            out.append(np.transpose(tensor, (1, 2, 0)))
        return out


class MoveChannelsLast(Process):
    """
    [CWH] -> [WHC]
    """

    def __init__(self):
        super(MoveChannelsLast, self).__init__()
        self._move = MoveChannelsFirst()

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        return self._move.run_inverse(tensors)

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        return self._move.run(tensors)


class CHWImage(Process):
    """
    [WHC] -> [CHW]
    """

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        tensors = MoveChannelsFirst().run(tensors)
        return tensors

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        tensors = MoveChannelsFirst().run_inverse(tensors)
        return tensors


class WHCImage(Process):
    """
    [CWH] -> [WHC]
    """

    def __init__(self):
        super(WHCImage, self).__init__()
        self._chw = CHWImage()

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        return self._chw.run_inverse(tensors)

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        return self._chw.run(tensors)
