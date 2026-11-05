# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import os
import time

import OpenImageIO as oiio
import numpy as np

import rmtc.ops.artifacts as artifacts
import rmtc.ops.assets as assets
import rmtc.ops.process as process
import rmtc.core.ops.io.filesystem.folders as folder_io
import rmtc.core.ops.io.oiio.image as image_io
from rmtc.ops.assets import DataType
from rmtc.system import URI, FileURI
from rmtc.core.ops.io.oiio.image import OIIO_COLORSPACE_ATTR, OIIO_SUBIMAGE_NAME_ATTR

from abstract_rmtc_test import AbstractRMTCTest


class TestImages(AbstractRMTCTest):

    def test_multipart_exr(self):
        temp_exr_path = self._create_multipart_exr()
        rmtc_sys = self.get_system()

        dataset = rmtc_sys.create_dataset(artifacts.Dataset,
            name="Multipart EXR",
            uri=FileURI(os.path.dirname(temp_exr_path)),
            io=folder_io.FolderIO(
                asset_type=assets.Image,
                asset_io=image_io.EXR(subimage_names=["depth"]),
            ),
        )
        rmtc_sys.ops.asset_manager.read([dataset])
        img_count = 0
        for row in dataset:
            rmtc_sys.ops.asset_manager.read(row)
            img = row[0]
            self.assertEqual(img.channels, 4)
            self.assertEqual(img.height, 16)
            self.assertEqual(img.width, 16)
            img_count += 1
        self.assertTrue(img_count > 0)

    def test_image_metadata(self):
        temp_exr_path = self._create_multipart_exr()
        rmtc_sys = self.get_system()

        dataset = rmtc_sys.create_dataset(artifacts.Dataset,
            name="Test EXR",
            uri=FileURI(os.path.dirname(temp_exr_path)),
            io=folder_io.FolderIO(
                asset_type=assets.Image,
                asset_io=image_io.EXR(subimage_names=["rgb"]),
            ),
        )
        rmtc_sys.ops.asset_manager.read([dataset])
        self.assertEqual(len(dataset), 1)
        img_count = 0
        for row in dataset:
            self.assertEqual(len(row), 1)
            rmtc_sys.ops.asset_manager.read(row)
            img = row[0]
            self.assertEqual(img.layer_name, "rgb")
            self.assertEqual(img.data_type, DataType.FLOAT32)
            # later versions of OIIO use interop ID strings
            self.assertTrue(img.colorspace in ("sRGB", "srgb_rec709_scene"))
            img_count += 1
        self.assertTrue(img_count > 0)

    def _create_multipart_exr(self):
        """Create a temp multipart EXR for testing."""
        height = 16
        width = 16

        # Temp EXR path
        filepath = f"{self.tmp_path}/test_multipart_{time.time()}.exr"
        out_exr = oiio.ImageOutput.create(filepath)
        if not out_exr:
            raise RuntimeError(f"Unable to create: {filepath}")

        # RGB data (3 channel)
        rgb_data = np.random.rand(height, width, 3).astype(np.float32)
        spec_rgb = oiio.ImageSpec(width, height, 3, oiio.FLOAT)
        spec_rgb.attribute(OIIO_SUBIMAGE_NAME_ATTR, "rgb")
        spec_rgb.attribute(OIIO_COLORSPACE_ATTR, "sRGB")

        # Depth data (1 channel)
        depth_data = np.linspace(0, 10, height * width, dtype=np.float32).reshape(height, width, 1)
        spec_depth = oiio.ImageSpec(width, height, 1, oiio.FLOAT)
        spec_depth.attribute(OIIO_SUBIMAGE_NAME_ATTR, "depth")

        # Write multipart exr
        out_exr.open(filepath, [spec_rgb, spec_depth])
        out_exr.write_image(rgb_data)
        out_exr.open(filepath, spec_depth, "AppendSubimage")
        out_exr.write_image(depth_data)
        out_exr.close()

        return filepath
