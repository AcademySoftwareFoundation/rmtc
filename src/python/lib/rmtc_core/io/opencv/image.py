# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


import cv2
import numpy as np

from rmtc.io import IO
from rmtc.system import URI, RMTCException
from rmtc.artifacts import Image


class EXR(IO):
    """
    Reader/writer for EXR image files with HDR support.

    The EXR class handles reading and writing of EXR (Extended Dynamic Range)
    image files using OpenCV. It automatically handles color space conversion
    between BGR (OpenCV default) and RGB formats, and ensures 4-channel RGBA
    output by adding an alpha channel when necessary.

    EXR files are commonly used in computer graphics and machine learning
    applications that require high dynamic range imaging with floating-point
    precision. The reader/writer uses half-precision floating-point format
    for efficient storage.
    """

    def create_uri(self, artifact):
        new_uri = URI(scheme="file", host="localhost")
        new_uri.path /= artifact.name
        new_uri.path = new_uri.path.with_suffix(".exr")
        return new_uri

    def is_artifact_supported(self, artifact):
        if not isinstance(artifact, Image):
            return False
        return True

    def is_uri_supported(self, uri):
        """Check if URI points to a valid .exr file."""
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".exr"
        return False

    def read(self, artifact, uri):
        """
        Load EXR image from file into artifact tensor.

        Reads the EXR file using OpenCV, converts from BGR to RGB color space,
        and ensures 4-channel RGBA format by adding an opaque alpha channel
        if the image has fewer than 4 channels.
        """
        bgr_tensor = cv2.imread(str(uri.path), cv2.IMREAD_UNCHANGED)
        if bgr_tensor is None:
            raise RMTCException(f"Failed to read EXR file: {uri.path}")
        tensor = cv2.cvtColor(bgr_tensor, cv2.COLOR_BGR2RGB)
        h, w, c = tensor.shape
        if c < 4:
            alpha = np.ones((h, w, 1))
            tensor = np.concatenate((tensor, alpha), axis=2)
        artifact.tensor = tensor

    def write(self, artifact, uri):
        """
        Save artifact tensor as EXR image file.

        Converts the tensor from RGB to BGR color space and writes as an EXR
        file using half-precision floating-point format for efficient storage.
        """
        rgb_tensor = artifact.tensor
        tensor = cv2.cvtColor(rgb_tensor, cv2.COLOR_RGB2BGR)
        cv2.imwrite(
            str(uri.path),
            tensor,
            [cv2.IMWRITE_EXR_TYPE, cv2.IMWRITE_EXR_TYPE_HALF],
        )
