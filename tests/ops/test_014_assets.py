# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import os
import time

import OpenImageIO as oiio
import numpy as np

import rmtc.ops.artifacts as artifacts
import rmtc.ops.assets as assets
import rmtc.ops.process as process

from abstract_rmtc_test import AbstractRMTCTest


class TestAssets(AbstractRMTCTest):

    def test_value(self):
        value = assets.Value()
        value.value = 10.0
        self.assertEqual(value.__class__, assets.Value)            
        self.assertEqual(value.value, 10.0)

    def test_values(self):
        values = assets.Values()
        values.value = [1,2,3]
        self.assertEqual(values.__class__, assets.Values)        
        self.assertEqual(values.value, [1,2,3])

    def test_label(self):
        value = assets.Label()
        value.value = "label"
        self.assertEqual(value.__class__, assets.Label)        
        self.assertEqual(value.value, "label")

    def test_labels(self):
        values = assets.Labels()
        values.value = ["label1","label2", "label3"]
        self.assertEqual(values.__class__, assets.Labels)
        self.assertEqual(values.value, ["label1","label2", "label3"])

    def test_structure(self):
        structure = assets.Structure()
        structure.add_member("x", assets.Value)
        structure.add_member("y", assets.Image)
        structure.add_member("z", assets.Values)
        self.assertEqual(structure.get_members(), ["x", "y", "z"])
        structure.x = assets.Value(10.0)
        structure.y = assets.Image()
        structure.z = assets.Values([1,2,3])        
        self.assertEqual(structure.x.__class__, assets.Value)
        self.assertEqual(structure.y.__class__, assets.Image)
        self.assertEqual(structure.z.__class__, assets.Values)                
        self.assertEqual(structure.x.value, 10.0)
        self.assertEqual(structure.z.value, [1,2,3])     
