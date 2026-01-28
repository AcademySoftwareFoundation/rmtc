# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.track import Asset
from rmtc.artifacts import Correlation

from .abstract_rmtc_unit_test import AbstractRMTCUnitTest


class TestEntities(AbstractRMTCUnitTest):

    def test_correlation(self):
        src = [Asset(name="A"), Asset(name="B"), Asset(name="C"), Asset(name="D")]
        dst = [Asset(name="A"), Asset(name="B"), Asset(name="C"), Asset(name="D")]
        dataset = Correlation(src=src, dst=dst)
        self.assertFalse(dataset.empty())
        self.assertTrue(dataset.rows() == 4)
        for row in dataset:
            self.assertTrue(len(row) == 2)
            self.assertTrue(row[0].name == row[1].name)

        src = [Asset(name="A"), Asset(name="B"), Asset(name="C"), Asset(name="D")]
        dst = [Asset(name="1"), Asset(name="2"), Asset(name="3"), Asset(name="4")]
        dataset = Correlation(src=src, dst=dst)
        i = 0
        for row in dataset:
            self.assertTrue(row[0].name == src[i].name)
            self.assertTrue(row[1].name == dst[i].name)
            i += 1
