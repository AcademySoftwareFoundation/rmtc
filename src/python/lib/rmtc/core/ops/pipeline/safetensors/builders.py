# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.core.ops.artifacts.torch.weights import TorchWeights
from rmtc.core.ops.io.safetensors.weights import SafetensorsTorchWeightsFile
from rmtc.ops.pipeline import Builder
from rmtc.system import FileURI


class SafetensorsWeightsBuilder(Builder):

    def is_supported(self, artifact):
        if not isinstance(artifact, TorchWeights):
            return False
        if artifact.model is None:
            return False
        if artifact.uri.scheme != "file":
            return False
        return True

    def __call__(self, asset_manager, artifact, options=None):

        weights = artifact

        # new weights
        safe_weights = weights.duplicate()

        # load into a duplicate model
        model = weights.model.duplicate()

        # load weights
        asset_manager.read([safe_weights, model])
        model.load_weights(safe_weights)

        # convert to safetensors
        weights_resolved_uri = asset_manager.resolve([safe_weights.uri])[0]

        # create a new filepath URI
        safe_weights.uri = FileURI(
            path=weights_resolved_uri.path.with_suffix(".safetensors"),
        )
        safe_weights.io = SafetensorsTorchWeightsFile()
        asset_manager.write([safe_weights])

        # construct resource artifact and relate to model
        safe_weights.ancestors = [weights.model, weights]

        return [safe_weights]
