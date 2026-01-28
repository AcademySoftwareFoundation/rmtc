# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from __future__ import division

import random

import cv2
import numpy as np

from rmtc.process import Process


class Rotate(Process):
    """
    Rotate images in HWC numpy tensor format by a specific angle or by a random
    angle within a specified range. Useful for augmenting data during training.
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

    def run(self, tensors):
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

    def run_inverse(self, tensors):
        """
        Rotation is random, so the inverse is a no-op
        """
        return tensors


class Translate(Process):
    """
    Translate images in HWC numpy tensor format by a specific number of pixels or by a random
    amount within a specified range. Useful for augmenting data during training.
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

    def run(self, tensors):
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

    def run_inverse(self, tensors):
        """
        Transformation is applied randomly, so the inverse is a no-op
        """
        return tensors


class Scale(Process):
    """
    Scale images in HWC numpy tensor format by a specific factor or by a random
    scale within a range. Useful for augmenting data during training.
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

    def run(self, tensors):
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

            h, w, c = img_tensor.shape

            # Scale the image
            scaled_img = cv2.resize(
                img_tensor, (w, h), fx=sx, fy=sy, interpolation=cv2.INTER_AREA
            )

            if c == 1:
                # Add channels back for single-channel images
                scaled_img = scaled_img[:, :, np.newaxis]

            scaled_tensors.append(scaled_img)

        return scaled_tensors

    def run_inverse(self, tensors):
        """
        Scale is applied randomly, so the inverse is a no-op
        """
        return tensors


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

    def run(self, tensors):

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

    def run_inverse(self, tensors):
        """
        Flip is applied randomly, so the inverse is a no-op
        """
        return tensors
