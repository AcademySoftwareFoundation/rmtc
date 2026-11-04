# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from pathlib import Path

import OpenImageIO as oiio
import numpy as np

from rmtc.ops.io import IO
from rmtc.system.objects import OUT
from rmtc.system import RMTCException
from rmtc.system import DataType
from rmtc.ops.assets import Image


OIIO_SUBIMAGE_NAME_ATTR = "oiio:subimagename"
OIIO_COLORSPACE_ATTR = "oiio:ColorSpace"
OIIO_FORMATS = {
    oiio.FLOAT: DataType.FLOAT32,
    oiio.HALF: DataType.FLOAT16,
    oiio.INT8: DataType.INT8,
    oiio.INT16: DataType.INT16,
    oiio.INT32: DataType.INT32,
    oiio.UINT8: DataType.UINT8,
    oiio.UINT16: DataType.UINT16,
    oiio.UINT32: DataType.UINT32,
    oiio.UNKNOWN: DataType.INVALID,
}


class EXR(IO):
    """
    Reader/writer for EXR image files with HDR support.

    The EXR class handles reading and writing of EXR (Extended Dynamic Range)
    image files using OIIO.
    """

    # Default subimage names for multipart EXRs, based on number of channels
    DEFAULT_PART_NAME = {
        1: "alpha",
        3: "rgb",
        4: "rgba",
    }

    def __init__(
        self,
        name=None,
        context=None,
        subimage_names=None,
    ):
        """Initialize the IO"""
        super(EXR, self).__init__(name=name, context=context)
        self.add_property("subimage_names", [str], subimage_names, direction=OUT)

    def create_name(self, artifact):
        return str(Path(artifact.name + ".exr"))

    def get_scheme(self):
        return "file"

    def get_artifact_type(self):
        return Image

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

    def read(self, uri, artifact, asset_manager):
        """Load EXR image from file into artifact tensor.
        Reads the EXR file using OIIO, converts from BGR to RGB color space,
        and ensures 4-channel RGBA format by adding an opaque alpha channel
        if the image has fewer than 4 channels.
        """
        mip_level = 0
        subimage = -1
        if self.subimage_names:
            # TODO: This only finds the first subimage, support multiple?
            subimage = self.get_subimage_index(str(uri.path), self.subimage_names[0])
        subimage = max(subimage, 0)
        buffer = oiio.ImageBuf(str(uri.path), subimage, mip_level)
        if buffer.has_error:
            raise RMTCException(
                f"Failed to read EXR file: {uri.path}\n{buffer.geterror()}"
            )
        spec = buffer.spec()
        tensor = buffer.get_pixels(oiio.FLOAT)
        if len(tensor.shape) == 1:
            tensor = tensor.reshape(spec.height, spec.width, spec.nchannels)

        # TODO: Do we always enforce a 4 channel image?
        h, w, c = tensor.shape
        if c == 3:
            # Add alpha channel to RGB image
            alpha = np.ones((h, w, 1))
            tensor = np.concatenate((tensor, alpha), axis=2)
        elif c == 1:
            # Treat image as an alpha channel, add RGB channels
            rgba = np.zeros((h, w, 4))
            rgba[:, :, 3] = tensor.squeeze()
            tensor = rgba

        # transpose to WHC:
        tensor = np.ascontiguousarray(tensor, dtype=np.float32)
        artifact.tensors = (tensor,)
        artifact.colorspace = spec.getattribute(OIIO_COLORSPACE_ATTR)
        artifact.data_type = OIIO_FORMATS.get(spec.format.basetype)
        artifact.layer_name = spec.getattribute(OIIO_SUBIMAGE_NAME_ATTR)

    def write(self, uri, artifact, asset_manager):
        """Save artifact tensor as EXR image file using OIIO"""
        tensor = artifact.tensors[0]
        h, w, c = tensor.shape
        tensor = np.ascontiguousarray(tensor, dtype=np.float32)
        formatted_tensor = np.copy(tensor, order="C").astype(
            np.float32
        )  # HACK - something goes awry
        spec = oiio.ImageSpec(w, h, c, oiio.FLOAT)
        if self.subimage_names:
            # TODO: This only writes the first subimage, support multiple tensors
            spec.attribute(OIIO_SUBIMAGE_NAME_ATTR, self.subimage_names[0])
        buffer = oiio.ImageBuf(spec)
        if buffer.has_error:
            raise RMTCException(f"Cannot create image buffer\n{buffer.geterror()}")
        buffer.set_pixels(oiio.ROI(), formatted_tensor)
        if buffer.has_error:
            raise RMTCException(f"Cannot set pixels buffer\n{buffer.geterror()}")

        out_exr = oiio.ImageOutput.create(str(uri.path))
        if not out_exr:
            raise RMTCException(f"Failed to create EXR file: {artifact.uri.path}\n")

        buffer.write(str(uri.path))

        if oiio.geterror():
            raise RMTCException(f"Global OIIO error\n{oiio.geterror()}")
        if buffer.has_error:
            raise RMTCException(f"Buffer has error post write\n{buffer.geterror()}")

    def get_subimage_index(self, exr_path, name):
        """Get the index of a subimage by name in a multipart EXR."""
        input_file = oiio.ImageInput.open(exr_path)
        if not input_file:
            return -1

        found_index = -1
        subimage_index = 0

        # Iterate subimages to look for name
        while input_file.seek_subimage(subimage_index, 0):
            spec = input_file.spec()
            if spec.getattribute(OIIO_SUBIMAGE_NAME_ATTR) == name:
                found_index = subimage_index
                break
            subimage_index += 1

        input_file.close()

        return found_index


class OIIOBase(IO):
    """
    Reader/writer for JPG image files.
    """

    def get_scheme(self):
        return "file"

    def get_artifact_type(self):
        return Image

    def read(self, uri, artifact, asset_manager):
        buffer = oiio.ImageBuf(str(uri.path))
        if buffer.has_error:
            raise RMTCException(f"Failed to read file: {uri.path}\n{buffer.geterror()}")
        spec = buffer.spec()
        tensor = buffer.get_pixels(oiio.FLOAT)
        if len(tensor.shape) == 1:
            tensor = tensor.reshape(spec.height, spec.width, spec.nchannels)
        h, w, c = tensor.shape
        if c < 4:
            alpha = np.ones((h, w, 1))
            tensor = np.concatenate((tensor, alpha), axis=2)
        tensor = np.ascontiguousarray(tensor, dtype=np.float32)
        artifact.tensors = (tensor,)
        artifact.colorspace = spec.getattribute(OIIO_COLORSPACE_ATTR)
        artifact.data_type = OIIO_FORMATS.get(spec.format.basetype)
        artifact.layer_name = spec.getattribute(OIIO_SUBIMAGE_NAME_ATTR)

    def write(self, uri, artifact, asset_manager):
        tensor = np.ascontiguousarray(artifact.tensors[0], dtype=np.float32)
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


class JPG(OIIOBase):
    """
    Reader/writer for JPG image files.
    """

    def create_name(self, artifact):
        return str(Path(artifact.name + ".jpg"))

    def is_uri_supported(self, uri):
        if uri.scheme == "file":
            return uri.path.suffix.lower() in [".jpg", ".jpeg"]
        return False


class PNG(OIIOBase):
    """
    Reader/writer for PNG image files.
    """

    def create_name(self, artifact):
        return str(Path(artifact.name + ".png"))

    def is_uri_supported(self, uri):
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".png"
        return False
