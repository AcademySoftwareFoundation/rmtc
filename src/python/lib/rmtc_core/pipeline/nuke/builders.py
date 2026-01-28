# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.pipeline import IBuilder


class CatWrapperModelBuilder(IBuilder):

    def __call__(self, artifact):
        return None


class CatWrapperWeightsBuilder(IBuilder):

    def __call__(self, artifact):
        return None
