# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


import OpenImageIO as oiio
import numpy as np

from rmtc.io import IO
from rmtc.system import URI, RMTCException
from rmtc.artifacts import Image


class EXR(IO):
    """
    Reader/writer for EXR image files with HDR support.

    The EXR class handles reading and writing of EXR (Extended Dynamic Range)
    image files using OIIO.
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

    def make_legal_uri(self, uri):
        uri.path = uri.path.with_suffix(".exr")
        return uri

    def is_uri_supported(self, uri):
        """Check if URI points to a valid .exr file.

        Args:
            uri (URI): URI to validate.

        Returns:
            bool: True if URI is a file scheme with .exr extension.
        """
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".exr"
        return False

    def read(self, artifact, uri):
        """Load EXR image from file into artifact tensor.
        Reads the EXR file using OIIO, converts from BGR to RGB color space,
        and ensures 4-channel RGBA format by adding an opaque alpha channel
        if the image has fewer than 4 channels.
        """
        buffer = oiio.ImageBuf(str(uri.path))
        if buffer.has_error:
            raise RMTCException(
                f"Failed to read EXR file: {uri.path}\n{buffer.geterror()}"
            )
        spec = buffer.spec()
        tensor = buffer.get_pixels(oiio.FLOAT)
        if len(tensor.shape) == 1:
            tensor = tensor.reshape(spec.height, spec.width, spec.nchannels)
        h, w, c = tensor.shape
        if c < 4:
            alpha = np.ones((h, w, 1))
            tensor = np.concatenate((tensor, alpha), axis=2)
        artifact.tensor = tensor

    def write(self, artifact, uri):
        """Save artifact tensor as EXR image file using OIIO"""
        tensor = np.ascontiguousarray(artifact.tensor, dtype=np.float32)
        h, w, c = tensor.shape
        spec = oiio.ImageSpec(w, h, c, oiio.FLOAT)
        buffer = oiio.ImageBuf(spec)
        if buffer.has_error:
            raise RMTCException(f"Cannot create image buffer\n{buffer.geterror()}")
        buffer.set_pixels(oiio.ROI.All, tensor)
        if buffer.has_error:
            raise RMTCException(f"Cannot set pixels buffer\n{buffer.geterror()}")
        success = buffer.write(str(uri.path))
        if not success:
            raise RMTCException(
                f"Failed to write EXR file: {artifact.uri.path}\n{oiio.geterror()}"
            )
        if oiio.geterror():
            raise RMTCException(f"Global OIIO error\n{oiio.geterror()}")
        if buffer.has_error:
            raise RMTCException(f"Buffer has error post write\n{buffer.geterror()}")


class JPG(IO):
    """
    Reader/writer for JPG image files.
    """

    def create_uri(self, artifact):
        new_uri = URI(scheme="file", host="localhost")
        new_uri.path /= artifact.name
        new_uri.path = new_uri.path.with_suffix(".jpg")
        return new_uri

    def is_artifact_supported(self, artifact):
        if not isinstance(artifact, Image):
            return False
        return True

    def make_legal_uri(self, uri):
        uri.path = uri.path.with_suffix(".jpg")
        return uri

    def is_uri_supported(self, uri):
        """Check if URI points to a valid .jpg file."""
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".jpg"
        return False

    def read(self, artifact, uri):
        """Load EXR image from file into artifact tensor.
        Reads the EXR file using OIIO, converts from BGR to RGB color space,
        and ensures 4-channel RGBA format by adding an opaque alpha channel
        if the image has fewer than 4 channels.
        """
        buffer = oiio.ImageBuf(str(uri.path))
        if buffer.has_error:
            raise RMTCException(
                f"Failed to read JPG file: {uri.path}\n{buffer.geterror()}"
            )
        spec = buffer.spec()
        tensor = buffer.get_pixels(oiio.FLOAT)
        if len(tensor.shape) == 1:
            tensor = tensor.reshape(spec.height, spec.width, spec.nchannels)
        h, w, c = tensor.shape
        if c < 4:
            alpha = np.ones((h, w, 1))
            tensor = np.concatenate((tensor, alpha), axis=2)
        artifact.tensor = tensor

    def write(self, artifact, uri):
        """Save artifact tensor as JPG image file using OIIO"""
        tensor = np.ascontiguousarray(artifact.tensor, dtype=np.float32)
        h, w, c = tensor.shape
        spec = oiio.ImageSpec(w, h, c, oiio.FLOAT)
        buffer = oiio.ImageBuf(spec)
        if buffer.has_error:
            raise RMTCException(f"Cannot create image buffer\n{buffer.geterror()}")
        buffer.set_pixels(oiio.ROI.All, tensor)
        if buffer.has_error:
            raise RMTCException(f"Cannot set pixels buffer\n{buffer.geterror()}")
        success = buffer.write(str(uri.path))
        if not success:
            raise RMTCException(
                f"Failed to write JPG file: {artifact.uri.path}\n{oiio.geterror()}"
            )
        if oiio.geterror():
            raise RMTCException(f"Global OIIO error\n{oiio.geterror()}")
        if buffer.has_error:
            raise RMTCException(f"Buffer has error post write\n{buffer.geterror()}")
