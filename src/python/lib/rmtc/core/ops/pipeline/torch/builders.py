# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from pathlib import Path

from rmtc.core.ops.artifacts.torch.weights import TorchWeights
from rmtc.core.ops.io.torch.models import TorchScript
from rmtc.ops.pipeline import Builder
from rmtc.system import URI


class TorchScriptBuilder(Builder):

    def is_supported(self, artifact):
        if artifact.category() != "Weights":
            return False
        if artifact.model is None:
            return False
        if not len(artifact.model.input_types) == 1:
            return False
        if not len(artifact.model.output_types) == 1:
            return False
        if artifact.uri.scheme != "file":
            return False
        if not isinstance(artifact, TorchWeights):
            return False
        return True

    def __call__(self, asset_manager, artifact, options=None):
        weights = artifact

        # load into a duplicate model
        ts_model = weights.model.duplicate()
        ts_model.name = ts_model.name + " (" + weights.name + ")"
        ts_model.ancestors = [weights.model, weights]

        # load weights
        asset_manager.read([weights, ts_model])
        ts_model.load_weights(weights)

        # convert to TorchScript
        weights_resolved_uri = asset_manager.resolve([weights.uri])[0]
        # create a new filepath URI
        ts_model.uri = URI(
            scheme="file",
            host="localhost",
            path=weights_resolved_uri.path.parent / Path("torchscript_model.pt"),
        )
        ts_model.io = TorchScript()
        asset_manager.write([ts_model])

        return [ts_model]
