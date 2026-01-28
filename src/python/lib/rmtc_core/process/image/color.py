# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from __future__ import division

import numpy as np

from rmtc.process import Process


class StatsNormalize(Process):

    # TODO : add shape validation

    """
    Image normalization processor for standardizing pixel values.

    The StatsNormalize processor applies channel-wise normalization to image tensors
    using configurable mean and standard deviation values. This is commonly used
    in computer vision pipelines to standardize input data for neural networks.

    The normalization formula applied is: (pixel - mean) / std for each channel.
    The processor expects 3D tensors in HWC format and temporarily transposes
    to CHW for efficient channel-wise operations.
    """

    def __init__(
        self,
        mean=None,
        std=None,
    ):
        """Initialize StatsNormalize processor with mean and std values."""
        if mean is None:
            mean = [0.5, 0.5, 0.5]
        if std is None:
            std = [0.25, 0.25, 0.25]
        super(StatsNormalize, self).__init__()
        self.add_property("mean", [float], mean)
        self.add_property("std", [float], std)

    def validate(self, tensors):
        """Validate tensors are RGBA HWC"""
        for tensor in tensors:
            if len(tensor.shape) != 3:
                return False
        return True

    def run(self, tensors):
        """Apply normalization to input tensors."""
        out = []
        for tensor in tensors:
            normalized = np.zeros_like(tensor, dtype=np.float32)
            for c in range(tensor.shape[2] - 1):
                channel = tensor[:, :, c]
                normalized[:, :, c] = (channel - self.mean[c]) / self.std[c]
            normalized[:, :, 3] = tensor[:, :, 3]
            out.append(normalized)
        return out

    def run_inverse(self, tensors):
        """Reverse normalization to recover original pixel values."""
        out = []
        for tensor in tensors:
            normalized = np.zeros_like(tensor, dtype=np.float32)
            for c in range(tensor.shape[2] - 1):
                channel = tensor[:, :, c]
                normalized[:, :, c] = (channel * self.std[c]) + self.mean[c]
            normalized[:, :, 3] = tensor[:, :, 3]
            out.append(normalized)
        return out


class LinearNormalize(Process):
    """
    Image normalization processor for standardizing pixel values.

    The LinearNormalize processor applies channel-wise normalization to image tensors
    using min-max scaling, in the range [0, 1] by default.
    """

    def __init__(
        self,
        scale_range=None,
        data_min=None,
        data_max=None,
    ):
        """Initialize LinearNormalize processor with mean and std values."""
        if scale_range is None:
            scale_range = [0.0, 1.0]
        super(LinearNormalize, self).__init__()
        self.add_property("scale_range", [float], scale_range)
        if data_min is not None:
            self.add_property("data_min", float, data_min)
        if data_max is not None:
            self.add_property("data_max", float, data_max)

    def validate(self, tensors):
        """Validate tensors are RGBA HWC"""
        for tensor in tensors:
            if len(tensor.shape) != 3:
                return False
        return True

    def run(self, tensors):
        """Apply normalization to input tensors."""
        out = []
        for tensor in tensors:
            normalized = tensor.astype(np.float32)

            # Global min and max of r, g, b
            if self.data_min is None:
                data_min = np.min(normalized)
            else:
                data_min = self.data_min
            if self.data_max is None:
                data_max = np.max(normalized)
            else:
                data_max = self.data_max

            # Edge cases if all data points are the same
            if data_min == data_max:
                if self.scale_range[0] == self.scale_range[1]:
                    # Range is zero
                    normalized[..., :3] = self.scale_range[0]
                else:
                    # Constant data, return the midpoint of the range
                    normalized[..., :3] = (
                        self.scale_range[0] + self.scale_range[1]
                    ) / 2.0
            else:
                # Apply min-max scaling formula to r, g, b channels
                rgb_channels = normalized[..., :3]
                scaled_rgb = self.scale_range[0] + (
                    (rgb_channels - data_min)
                    * (self.scale_range[1] - self.scale_range[0])
                    / (data_max - data_min)
                )
                normalized[..., :3] = scaled_rgb

            out.append(normalized)
        return out

    def run_inverse(self, tensors):
        """Reverse normalization to recover original pixel values. This is
        only possible if the forward pass was done with a specified data_min
        and data_max, otherwise this is a no-op."""
        if self.data_min is None or self.data_max is None:
            return tensors

        out = []
        for tensor in tensors:
            normalized = tensor.astype(np.float32)

            if self.data_min == self.data_max:
                # Edge case: constant data was mapped to midpoint or constant value
                # May not be able to reliable invert
                normalized[..., :3] = self.data_min
            else:
                # Inverse of forward pass
                rgb_channels = normalized[..., :3]
                original_rgb = (
                    (rgb_channels - self.scale_range[0])
                    * (self.data_max - self.data_min)
                    / (self.scale_range[1] - self.scale_range[0])
                ) + self.data_min
                normalized[..., :3] = original_rgb

            out.append(normalized)

        return out


class LinearToSRGB(Process):
    """Convert images from linear to sRGB color space using the power approximation."""

    CONVERSION_EXPONENT = 0.4545

    def run(self, tensors):
        """Convert from linear to sRGB."""
        out = []
        for tensor in tensors:
            # Apply power function to the first three channels (R, G, B)
            tensor[..., :3] = np.power(tensor[..., :3], self.CONVERSION_EXPONENT)
            out.append(tensor)
        return out

    def run_inverse(self, tensors):
        """Convert from sRGB back to linear"""
        inverse_exponent = 1.0 / self.CONVERSION_EXPONENT
        out = []
        for tensor in tensors:
            # Apply inverse power function to R, G, B channels
            tensor[..., :3] = np.power(tensor[..., :3], inverse_exponent)
            out.append(tensor)
        return out


class MakeMonochrome(Process):
    """
    Monochrome conversion processor for creating single-channel images.

    The MakeMonochrome processor converts RGB images to monochrome by
    replicating a single channel across all three color channels. This
    creates a grayscale-like effect while maintaining the 3-channel format
    required by some models.
    """

    def __init__(
        self,
        channel=0,
    ):
        """Initialize MakeMonochrome processor with channel selection."""
        super(MakeMonochrome, self).__init__()
        self.add_property("channel", int, channel)

    def validate(self, tensors):
        """Validate input tensors are 3D with 3 channels (RGB)."""
        for tensor in tensors:
            if len(tensor.shape) != 4:
                return False
            if tensor.shape[2] != 4:
                return False
        return True

    def run(self, tensors):
        """Convert RGBA tensors to monochrome by replicating selected channel."""
        out = []
        for tensor in tensors:
            channel = tensor[:, :, self.channel : self.channel + 1]
            alpha = tensor[:, :, 3:4]
            mono = np.concatenate([channel, channel, channel, alpha], axis=2)
            out.append(mono)
        return out

    def run_inverse(self, tensors):
        """
        Return tensors unchanged (no-op inverse operation).
        """
        return tensors
