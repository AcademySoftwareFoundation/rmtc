# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import os

import numpy as np

import rmtc_core.io.oiio.image as image_io
import rmtc_core.process.tensor.structure as structure_processors
import rmtc_core.process.image.color as color_processors
import rmtc_core.process.image.channels as channel_processors

from rmtc.system import URI
from rmtc.artifacts import Image
from rmtc.process import ProcessStack
from rmtc.system import Logger
from rmtc_core.pipeline.filesystem.asset_managers import FilesystemManager

from .abstract_rmtc_integration_test import AbstractRMTCIntegrationTest


def load_test_image(image_name="256x256_rainbow_checkers"):
    log = Logger()
    asset_manager = FilesystemManager(log)
    asset = Image(
        uri=URI(
            scheme="file",
            host="localhost",
            path=f"{os.getenv('RMTC_RESOURCES')}/images/{image_name}.exr",
        ),
        io=image_io.EXR(),
    )
    asset.read(asset_manager)
    return asset


class TestProcessors(AbstractRMTCIntegrationTest):
    """Test processors"""

    def test_stats_normalize(self):
        asset = load_test_image()
        process = color_processors.StatsNormalize()

        # check round trip
        result = process.run([asset.tensor])
        r_h, r_w, r_c = result[0].shape
        self.assertTrue(r_h, asset.height)
        self.assertTrue(r_w, asset.width)
        self.assertTrue(r_c, asset.channels)
        inverse_result = process.run_inverse(result)
        self.assertTrue(np.allclose(asset.tensor, inverse_result, atol=1e-3))

    def test_linear_normalize(self):
        asset = load_test_image()
        process = color_processors.LinearNormalize(
            scale_range=[0.0, 2.0],
            data_min=0.0,
            data_max=1.0,
        )

        # check round trip
        result = process.run([asset.tensor])
        r_h, r_w, r_c = result[0].shape
        self.assertTrue(r_h, asset.height)
        self.assertTrue(r_w, asset.width)
        self.assertTrue(r_c, asset.channels)
        inverse_result = process.run_inverse(result)
        self.assertTrue(np.allclose(asset.tensor, inverse_result, atol=1e-3))

    def test_trimalpha(self):
        asset = load_test_image()
        process = channel_processors.TrimAlpha()

        # run
        result = process.run([asset.tensor])
        h, w, c = result[0].shape
        self.assertTrue(h, asset.height)
        self.assertTrue(w, asset.width)
        self.assertTrue(c, asset.channels - 1)

        # inverse
        inverse_result = process.run_inverse(result)
        h, w, c = inverse_result[0].shape
        self.assertTrue(h, asset.height)
        self.assertTrue(w, asset.width)
        self.assertTrue(c, asset.channels)

    def test_makemono(self):
        asset = load_test_image()
        process = color_processors.MakeMonochrome()
        r = asset.tensor[:, :, 0:1]
        a = asset.tensor[:, :, 3]

        # run
        result = process.run([asset.tensor])
        result_r = result[0][:, :, 0:1]
        result_g = result[0][:, :, 1:2]
        result_b = result[0][:, :, 2:3]
        result_a = result[0][:, :, 3]
        self.assertTrue(np.array_equal(result_r, r))
        self.assertTrue(np.array_equal(result_g, r))
        self.assertTrue(np.array_equal(result_b, r))
        self.assertTrue(np.array_equal(result_a, a))

    def test_movechannels(self):
        asset = load_test_image()
        self.assertEqual(asset.channels, 4)
        h = asset.height
        w = asset.width
        c = asset.channels
        process = channel_processors.MoveChannelsFirst()

        # run
        result = process.run([asset.tensor])
        r_c, r_h, r_w = result[0].shape
        self.assertEqual(r_c, 4)
        self.assertEqual(r_c, c)
        self.assertEqual(r_h, h)
        self.assertEqual(r_w, w)

        # inverse
        inverse_result = process.run_inverse(result)
        r_h, r_w, r_c = inverse_result[0].shape
        self.assertEqual(r_c, 4)
        self.assertEqual(r_c, c)
        self.assertEqual(r_h, h)
        self.assertEqual(r_w, w)

    def test_batch(self):
        asset1 = load_test_image()
        asset2 = load_test_image()
        asset3 = load_test_image()
        tensors = [asset1.tensor, asset2.tensor, asset3.tensor]
        process = structure_processors.Batch()

        # run
        result = process.run(tensors)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].shape[0], 3)

        # inverse
        inverse_result = process.run_inverse(result)
        self.assertEqual(len(inverse_result), 3)
        self.assertEqual(len(inverse_result[0].shape), 3)

    def test_flatten(self):
        asset = load_test_image()
        process = structure_processors.Flatten()

        # run
        result = process.run([asset.tensor])
        self.assertTrue(result[0].flags.c_contiguous)

    def text_extract(self):
        asset = load_test_image()
        process = channel_processors.ExtractChannel()

        # run
        result = process.run([asset.tensor])
        self.assertEqual(result[0].shape[2], 1)

        # inverse
        inverse_result = process.run_inverse(result)
        self.assertEqual(len(inverse_result[0].shape), 3)

    def test_stack(self):
        asset1 = load_test_image()
        asset2 = load_test_image()
        asset3 = load_test_image()
        tensors = [asset1.tensor, asset2.tensor, asset3.tensor]
        process = ProcessStack(
            stack=[
                color_processors.StatsNormalize(),
                channel_processors.TrimAlpha(),
                channel_processors.MoveChannelsFirst(),
                structure_processors.Batch(),
                structure_processors.Flatten(),
            ]
        )

        # run
        result = process.run(tensors)
        self.assertTrue(result[0].flags.c_contiguous)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].shape[0], len(tensors))  # batch of 3
        self.assertEqual(result[0].shape[1], asset1.channels - 1)  # RGB

        # run inverse
        inverse_result = process.run_inverse(result)
        self.assertEqual(len(inverse_result), len(tensors))
        self.assertEqual(inverse_result[0].shape[0], asset1.height)
        self.assertEqual(inverse_result[0].shape[1], asset1.width)
        self.assertEqual(inverse_result[0].shape[2], asset1.channels)
