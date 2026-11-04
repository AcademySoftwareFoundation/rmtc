# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import os

import numpy as np

import rmtc.core.ops.io.oiio.image as image_io
import rmtc.core.ops.process.tensor.structure as structure_processors
import rmtc.core.ops.process.image.color as color_processors
import rmtc.core.ops.process.image.channels as channel_processors

from rmtc.ops.assets import Image
from rmtc.ops.process import ProcessStack
from rmtc.system import Logger, URI
from rmtc.core.system.environment.packages import PackageTracker
from rmtc.core.track.publishing.publishers.filesystem import DiskPublisher
from rmtc.core.ops.pipeline.readerwriters.filesystem import DiskReaderWriter
from rmtc.ops.pipeline import AssetManager
from rmtc.core.ops.process.packagers.tensor import Batch
from abstract_rmtc_test import AbstractRMTCTest


def load_test_image(image_name="256x256_rainbow_checkers"):
    log = Logger()
    env_manager = PackageTracker(log=log)
    publisher = DiskPublisher(log=log, immutable=False)
    readerwriter = DiskReaderWriter(
        env_manager=env_manager, 
        log=log, 
        publisher=publisher
    )
    asset_manager = AssetManager(
        log=log, 
        publisher=publisher, 
        readerwriter=readerwriter
    )
    asset = Image(
        uri=URI(
            scheme="file",
            host="localhost",
            path=f"{os.getenv('RMTC_RESOURCES')}/images/{image_name}.exr",
        ),
        io=image_io.EXR(),
    )
    asset_manager.read([asset])
    return asset


class TestAssetManagerAccessors(AbstractRMTCTest):
    """AssetManager exposes its constructed readerwriter/publisher directly,
    so callers can reach instance-level overrides like
    readerwriter.set_identity_mode(...) without touching private attrs."""

    def setUp(self):
        super(TestAssetManagerAccessors, self).setUp()
        log = Logger()
        env_manager = PackageTracker(log=log)
        self.publisher = DiskPublisher(log=log, immutable=False)
        self.readerwriter = DiskReaderWriter(
            env_manager=env_manager, log=log, publisher=self.publisher
        )
        self.asset_manager = AssetManager(
            log=log, publisher=self.publisher, readerwriter=self.readerwriter
        )

    def test_readerwriter_property_returns_constructed_instance(self):
        self.assertIs(self.asset_manager.readerwriter, self.readerwriter)

    def test_publisher_property_returns_constructed_instance(self):
        self.assertIs(self.asset_manager.publisher, self.publisher)


class TestProcessors(AbstractRMTCTest):
    """Test processors"""

    def test_stats_normalize(self):
        asset = load_test_image()
        process = color_processors.StatsNormalize()

        # check round trip
        result = process.run(asset.tensors)
        r_h, r_w, r_c = result[0].shape
        self.assertTrue(r_h, asset.height)
        self.assertTrue(r_w, asset.width)
        self.assertTrue(r_c, asset.channels)
        inverse_result = process.run_inverse(result)
        self.assertTrue(np.allclose(asset.tensors[0], inverse_result, atol=1e-3))

    def test_linear_normalize(self):
        asset = load_test_image()
        process = color_processors.LinearNormalize(
            scale_range=[0.0, 2.0],
            data_min=0.0,
            data_max=1.0,
        )

        # check round trip
        result = process.run(asset.tensors)
        r_h, r_w, r_c = result[0].shape
        self.assertTrue(r_h, asset.height)
        self.assertTrue(r_w, asset.width)
        self.assertTrue(r_c, asset.channels)
        inverse_result = process.run_inverse(result)
        self.assertTrue(np.allclose(asset.tensors[0], inverse_result, atol=1e-3))

    def test_trimalpha(self):
        asset = load_test_image()
        process = channel_processors.TrimAlpha()

        # run
        result = process.run(asset.tensors)
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
        r = asset.tensors[0][:, :, 0:1]
        a = asset.tensors[0][:, :, 3]

        # run
        result = process.run(asset.tensors)
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
        result = process.run(asset.tensors)
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
        data = [
            [asset1.tensors], 
            [asset2.tensors], 
            [asset3.tensors],
        ]

        batcher = Batch()

        # run
        result = batcher.run(data)
        self.assertEqual(result.shape[0], len(data))
        self.assertEqual(result.shape[1], asset1.width)
        self.assertEqual(result.shape[2], asset1.height)
        self.assertEqual(result.shape[3], asset1.channels)  

        # inverse
        reconstructed_data = batcher.run_inverse(result)
        self.assertEqual(len(reconstructed_data), len(data))
        self.assertEqual(len(reconstructed_data[0]), 1)
        asset1_tensors = reconstructed_data[0][0]
        self.assertEqual(len(asset1_tensors), 1)        
        self.assertEqual(asset1_tensors[0].shape[0], asset1.width)
        self.assertEqual(asset1_tensors[0].shape[1], asset1.height)
        self.assertEqual(asset1_tensors[0].shape[2], asset1.channels)  

    def text_extract(self):
        asset = load_test_image()
        process = channel_processors.ExtractChannel()

        # run
        result = process.run(asset.tensors)
        self.assertEqual(result[0].shape[2], 1)

        # inverse
        inverse_result = process.run_inverse(result)
        self.assertEqual(len(inverse_result[0].shape), 3)

    def test_stack(self):
        asset1 = load_test_image()
        asset2 = load_test_image()
        asset3 = load_test_image()
        tensors = [asset1.tensors[0], asset2.tensors[0], asset3.tensors[0]]
        process = ProcessStack(
            stack=[
                color_processors.StatsNormalize(),
                channel_processors.TrimAlpha(),
                channel_processors.MoveChannelsFirst(),
                structure_processors.Batch(),
                structure_processors.Contiguous(),
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
