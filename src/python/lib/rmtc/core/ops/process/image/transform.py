# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from __future__ import division

import random
import math

import cv2
import numpy as np
from rmtc.ops.tensor import Array

from rmtc.ops.process import Process


class Rotate(Process):
    """
    Rotate images in HWC numpy tensor format by a specific angle or by a random
    angle within a specified range. Useful for transforming data during training.
    """

    def __init__(
        self,
        angle=None,
        max_angle=360.0,
        **kwargs,
    ):
        super(Rotate, self).__init__(**kwargs)

        # Specific rotation angle. If None, a random rotation is applied, up to max_angle
        if angle:
            self.add_property("angle", float, angle)

        # Max rotation angle in degrees
        self.add_property("max_angle", float, max_angle)

    def validate(self, tensors):
        """Validate tensors are RGBA HWC"""
        for tensor in tensors:
            if len(tensor.shape) != 3:
                return False
        return True

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        """Rotate image tensors."""

        rotated_tensors = []

        for img_tensor in tensors:

            if self.angle is not None:
                angle = self.angle
            else:
                # Apply different random rotation per image
                angle = self.max_angle * random.random()
                if random.random() <= 0.5:
                    angle *= -1

            h, w, c = img_tensor.shape
            center = (w // 2, h // 2)

            # Rotate the image
            rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated_img = cv2.warpAffine(img_tensor, rotation_matrix, (w, h))

            if c == 1:
                # Add channels back for single-channel images
                rotated_img = rotated_img[:, :, np.newaxis]

            rotated_tensors.append(rotated_img)

        return rotated_tensors

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        """
        Rotation is random, so the inverse is a no-op
        """
        return tensors

    def is_reversible(self):
        return False


class Translate(Process):
    """
    Translate images in HWC numpy tensor format by a specific number of pixels or by a random
    amount within a specified range. Useful for transforming data during training.
    """

    def __init__(
        self,
        x=None,
        y=None,
        max_x=1.0,
        max_y=1.0,
        **kwargs,
    ):
        super(Translate, self).__init__(**kwargs)

        # Specific translation (in pixels). If None, a random translation is applied
        if x:
            self.add_property("x", float, x)
        if y:
            self.add_property("y", float, y)

        # Max translation (as a fraction of image size)
        self.add_property("max_x", float, max_x)
        self.add_property("max_y", float, max_y)

    def validate(self, tensors):
        """Validate tensors are RGBA HWC"""
        for tensor in tensors:
            if len(tensor.shape) != 3:
                return False
        return True

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        """Translate image tensors"""
        translated_tensors = []

        for img_tensor in tensors:
            h, w, c = img_tensor.shape

            if self.x is not None or self.y is not None:
                tx = self.x or 0.0
                ty = self.y or 0.0
            else:
                # Apply a unique translation for each image
                tx = random.uniform(-self.max_x, self.max_x) * w
                ty = random.uniform(-self.max_y, self.max_y) * h

            # Translate the image
            translation_matrix = np.float32([[1, 0, tx], [0, 1, ty]])
            translated_img = cv2.warpAffine(img_tensor, translation_matrix, (w, h))

            if c == 1:
                # Add channels back for single-channel images
                translated_img = translated_img[:, :, np.newaxis]

            translated_tensors.append(translated_img)

        return translated_tensors

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        """
        Transformation is applied randomly, so the inverse is a no-op
        """
        return tensors

    def is_reversible(self):
        return False


class Pad(Process):

    def __init__(
        self,
        width=None,
        height=None,
    ):
        super(Pad, self).__init__()
        self.add_property("width", int, width)
        self.add_property("height", int, height)

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        outputs = []
        for img_tensor in tensors:
            h, w, _ = img_tensor.shape
            pad_h = max(self.height - h, 0)
            pad_w = max(self.width - w, 0)
            tensor = np.pad(
                img_tensor,
                pad_width=(
                    (pad_h // 2, pad_h - pad_h // 2),
                    (pad_w // 2, pad_w - pad_w // 2),
                    (0, 0),  # channels ignore
                ),
                mode="constant",
                constant_values=0,  # black
            )
            outputs.append(tensor)
        return outputs

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        return tensors

    def is_reversible(self):
        return False


class Align(Process):

    def __init__(
        self,
        width_boundary=1,
        height_boundary=1,
    ):
        super(Align, self).__init__()
        self.add_property("width_boundary", int, width_boundary)
        self.add_property("height_boundary", int, height_boundary)

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        output = []
        for tensor in tensors:
            h, w, _ = tensor.shape
            padded_height = math.ceil(h / self.height_boundary) * self.height_boundary
            padded_width = math.ceil(w / self.width_boundary) * self.width_boundary
            pad_h = padded_height - h
            pad_w = padded_width - w
            tensor = np.pad(
                tensor,
                pad_width=(
                    (pad_h // 2, pad_h - pad_h // 2),
                    (pad_w // 2, pad_w - pad_w // 2),
                    (0, 0),  # channels ignore
                ),
                mode="constant",
                constant_values=0,  # black
            )
            output.append(tensor)
        return output

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        return tensors

    def is_reversible(self):
        return False


class Scale(Process):
    """
    Scale images in HWC numpy tensor format by a specific factor or by a random
    scale within a range. Useful for transforming data during training.
    """

    def __init__(
        self,
        scale=None,
        scale_min=(0.5, 0.5),
        scale_max=(2.0, 2.0),
        **kwargs,
    ):
        super(Scale, self).__init__(**kwargs)

        # Specific scale factor. If None, a random scale is applied
        if scale:
            self.add_property("scale", [float], scale)

        # Scale range
        self.add_property("scale_min", [float], scale_min)
        self.add_property("scale_max", [float], scale_max)

    def validate(self, tensors):
        """Validate tensors are RGBA HWC"""
        for tensor in tensors:
            if len(tensor.shape) != 3:
                return False
        return True

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        """Scale image tensors"""
        scaled_tensors = []

        for img_tensor in tensors:
            if self.scale is not None:
                sx, sy = self.scale
            else:
                # Apply a unique scale for each image
                min_x, min_y = self.scale_min
                max_x, max_y = self.scale_max
                sx = random.uniform(min_x, max_x)
                sy = random.uniform(min_y, max_y)

            # Scale the image
            scaled_img = cv2.resize(
                img_tensor, None, fx=sx, fy=sy, interpolation=cv2.INTER_AREA
            )

            # Add channels back for single-channel images
            _, _, c = img_tensor.shape
            if c == 1:
                scaled_img = scaled_img[:, :, np.newaxis]

            scaled_tensors.append(scaled_img)

        return scaled_tensors

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        """
        Scale is applied randomly, so the inverse is a no-op
        """
        return tensors

    def is_reversible(self):
        return False


class Flip(Process):
    """
    Flip HWC images horizontally and/or vertically.
    """

    def __init__(
        self,
        horizontal=None,
        vertical=None,
        probability=(0.5, 0.5),
        **kwargs,
    ):
        super(Flip, self).__init__(**kwargs)

        # Specific flip. If None, a random flip is applied
        if horizontal is not None:
            self.add_property("horizontal", bool, horizontal)
        if vertical is not None:
            self.add_property("vertical", bool, vertical)

        # Flip probabilities (horizontal flip prob, vertical flip prob)
        self.add_property("probability", [float], probability)

    def validate(self, tensors):
        """Validate tensors are RGBA HWC"""
        for tensor in tensors:
            if len(tensor.shape) != 3:
                return False
        return True

    def run(self, tensors: tuple[Array]) -> tuple[Array]:

        flipped_tensors = []

        for img_tensor in tensors:
            if self.horizontal is not None or self.vertical is not None:
                flip_h = self.horizontal or False
                flip_v = self.vertical or False
            else:
                # Apply a unique flip for each image
                prob_h, prob_v = self.probability
                flip_h = random.random() <= prob_h
                flip_v = random.random() <= prob_v

            if not flip_h and not flip_v:
                # No flip
                flipped_tensors.append(img_tensor)
                continue

            if flip_h and not flip_v:
                # Horizontal flip
                flip_code = 1
            elif not flip_h and flip_v:
                # Vertical flip
                flip_code = 0
            elif flip_h and flip_v:
                # Horizontal and vertical flip
                flip_code = -1

            # Flip the image
            flipped_img = cv2.flip(img_tensor, flip_code)

            _, _, c = img_tensor.shape
            if c == 1:
                # Add channels back for single-channel images
                flipped_img = flipped_img[:, :, np.newaxis]

            flipped_tensors.append(flipped_img)

        return flipped_tensors

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        """
        Flip is applied randomly, so the inverse is a no-op
        """
        return tensors

    def is_reversible(self):
        return False


class Resize(Process):
    """
    Resize the image, scaling up or down (CV2 scale method)
    """

    def __init__(
        self,
        width=None,
        height=None,
        **kwargs,
    ):
        super(Resize, self).__init__(**kwargs)
        self.add_property("width", int, width)
        self.add_property("height", int, height)

    def validate(self, tensors):
        return tensors is not None and len(tensors) > 0

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        resized_tensors = []
        for img_tensor in tensors:
            resized_tensors.append(cv2.resize(img_tensor, (self.width, self.height)))
        return resized_tensors

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        """Cannot inverse - no storage of previous size"""
        return tensors

    def is_reversible(self):
        return False


class Crop(Process):
    """
    Crop the image from the centre
    """

    def __init__(
        self,
        width=None,
        height=None,
        **kwargs,
    ):
        super(Crop, self).__init__(**kwargs)
        self.add_property("width", int, width)
        self.add_property("height", int, height)

    def validate(self, tensors):
        return tensors is not None and len(tensors) > 0

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        image_tensor = tensors[0]
        h, w, _ = image_tensor.shape
        x = w // 2
        y = h // 2
        x_start = x - (self.width // 2)
        x_end = x + (self.width // 2)
        y_start = y - (self.height // 2)
        y_end = y + (self.height // 2)
        cropped = image_tensor[y_start:y_end, x_start:x_end]
        return (cropped,)

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        """Cannot inverse - no storage of previous size"""
        return tensors

    def is_reversible(self):
        return False
