# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.pipeline import IBuilder


class ONNXModelBuilder(IBuilder):

    def is_supported(self, artifact):
        return artifact is not None

    def __call__(self, asset_manager, artifact):
        asset_manager.log.info(f"ONNX Model Build stub for {artifact}")
        return []


class ONNXWeightsBuilder(IBuilder):

    def is_supported(self, artifact):
        return artifact is not None

    def __call__(self, asset_manager, artifact):
        asset_manager.log.info(f"ONNX Weights Build stub for {artifact}")
        return []
