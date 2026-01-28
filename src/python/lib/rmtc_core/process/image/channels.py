# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from __future__ import division

import numpy as np

from rmtc.process import Process


class TrimAlpha(Process):

    # TODO : add shape validation

    """
    Alpha channel removal processor for RGBA to RGB conversion.

    The TrimAlpha processor removes the alpha channel from RGBA images,
    converting 4-channel tensors to 3-channel RGB tensors. The inverse
    operation adds a fully opaque alpha channel (value 1.0) to RGB images.

    This processor is useful when working with image formats that include
    transparency information but the downstream processing only expects
    RGB data.
    """

    def run(self, tensors):
        """Remove alpha channel from RGBA tensors."""
        out = []
        for tensor in tensors:
            out.append(tensor[:, :, :3])
        return out

    def run_inverse(self, tensors):
        """Add opaque alpha channel to RGB tensors."""
        out = []
        for tensor in tensors:
            h, w, c = tensor.shape  # pylint: disable=unused-variable
            alpha = np.full((h, w, 1), 1.0, dtype=np.float32)
            out.append(np.concatenate([tensor, alpha], axis=2))
        return out


class ExtractChannel(Process):
    """Remove all but 1 nominated channel on an RGBA tensor"""

    def __init__(
        self,
        channel=0,
    ):
        super(ExtractChannel, self).__init__()
        self.add_property("channel", int, channel)

    def run(self, tensors):
        out = []
        for tensor in tensors:
            out.append(tensor[:, :, self.channel : self.channel + 1])
        return out

    def run_inverse(self, tensors):
        out = []
        for tensor in tensors:
            h, w, c = tensor.shape  # pylint: disable=unused-variable
            alpha = np.ones((h, w, 1), dtype=np.float32)
            out.append(np.concatenate([tensor, tensor, tensor, alpha], axis=2))
        return out


class MoveChannelsFirst(Process):
    """
    Channel dimension reordering processor for HWC to CHW conversion.

    The MoveChannelsFirst processor transposes image tensors from Height-Width-Channel
    (HWC) format to Channel-Height-Width (CHW) format. This is commonly required
    when interfacing between different deep learning frameworks or when preparing
    data for models that expect channels-first format (e.g., PyTorch).

    The processor validates input format and provides bidirectional conversion
    between HWC and CHW layouts.
    """

    def run(self, tensors):
        """Convert tensors from HWC to CHW format."""
        out = []
        for tensor in tensors:
            out.append(np.transpose(tensor, (2, 0, 1)))
        return out

    def run_inverse(self, tensors):
        """Convert tensors from CHW to HWC format."""
        out = []
        for tensor in tensors:
            out.append(np.transpose(tensor, (1, 2, 0)))
        return out
