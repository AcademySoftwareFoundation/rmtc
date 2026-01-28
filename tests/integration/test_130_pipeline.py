# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from .abstract_rmtc_integration_test import AbstractRMTCIntegrationTest

from rmtc.pipeline import AssetManager


class MockAssetManager(AssetManager):
    pass


class TestPipeline(AbstractRMTCIntegrationTest):
    """Test provenance"""

    def test_publish(self):
        """Test publishing artifacts"""

        # create a mock asset manager
        # create a pipeline for models that confom to ONNX
        # create a model
        # publish model
        # check the ONNX model variant is created

        pass

    def test_build(self):
        """Test building artifacts into derivatives"""

        # create a torch package model
        # create a new weights file
        # create a ONNX file that derives from both
        # check sources & derivatives

        pass
