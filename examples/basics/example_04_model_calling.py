#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import rmtc.system as system
import rmtc.ops.tensor as tensor
import rmtc.ops.artifacts as artifacts
import rmtc.ops.assets as assets

class TestModel(artifacts.Model):

    def __init__(self):
        super(TestModel, self).__init__()
        self.add_input(
            name            = "plate",
            asset_type      = assets.Image,
        )
        self.add_input(
            name            = "threshold",
            asset_type      = assets.Value,
        )
        self.add_output(
            name            = "mask",
            asset_type      = assets.Image,
        )
        self.add_output(
            name            = "metric",
            asset_type      = assets.Value,
        )        

    def is_valid(self):
        return True

    def init(self):
        return True

    def reset(self):
        return True

    def create_checkpoint(self):
        return None

    def create_weights(self):
        return None

    def load_weights(self, weights):
        return False

    def load_checkpoint(self, checkpoint):
        return False                    

    def get_internal_model(self):
        return None

    def set_internal_model(self, model):
        pass

    def move(self, device):
        pass

    def get_device(self):
        return system.Device.INVALID

    def run(inputs, device):
        return [
            [
                assets.Image(tensors=(tensor.Array([1,1,4]),)),
                assets.Value(100.0),
            ]
        ]
    
###############################################################################

# TODO : make this work again
# model               = TestModel()
# image               = assets.Image(tensors=(tensor.Array([1,1,4]),))
# threshold           = assets.Value(value=10.2)
# result              = model(plate=image, threshold=threshold)
# print(result.mask)
# print(result.metric)
