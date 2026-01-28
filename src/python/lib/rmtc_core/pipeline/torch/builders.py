# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.pipeline import IBuilder


class TorchscriptModelBuilder(IBuilder):

    def __call__(self, artifact):
        return None


class TorchscriptWeightsBuilder(IBuilder):

    def __call__(self, artifact):
        return None
