# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import subprocess
import os
from pathlib import Path

from rmtc.core.ops.artifacts.torch.weights import TorchWeights
from rmtc.core.ops.io.torch.models import TorchScript
from rmtc.ops.pipeline import Builder
from rmtc.ops.assets import Image
from rmtc.track.entities import Resource
from rmtc.system import URI


class CATBuilder(Builder):

    def is_supported(self, artifact):
        if artifact.category() != "Weights":
            return False
        if artifact.model is None:
            return False
        if not len(artifact.model.input_types) == 1:
            return False
        if not len(artifact.model.output_types) == 1:
            return False
        if not artifact.model.input_types[0].is_class(Image):
            return False
        if not artifact.model.output_types[0].is_class(Image):
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

        # create cat file
        cat_path = ts_model.uri.path.parent / Path("cat_file.cat")
        self._run_nuke_script(
            torchscript=str(ts_model.uri.path),
            cat_path=str(cat_path),
            channels_in=self._get_channels_in(ts_model),
            channels_out=self._get_channels_out(ts_model),
            model_id=ts_model.name,
        )

        # construct resource artifact and relate to model
        cat_resource = Resource(
            name=ts_model.name + " CAT Resource",
            uri=URI(scheme="file", host="localhost", path=cat_path),
        )
        ts_model.add_variants([cat_resource])

        return [ts_model, cat_resource]

    def _get_channels_in(self, model):

        # Guess the type from the model shape
        # TODO : this is weakly enforced, bolster
        shape = model.input_shape
        if shape is not None and len(shape) == 4:
            _b, c, _h, _w = shape
            if c == 4:
                return "rgba.red, rgba.green, rgba.blue, rgba.alpha"
            if c == 3:
                return "rgba.red, rgba.green, rgba.blue"
            if c == 1:
                return "rgba.alpha"
        return "rgba.red, rgba.green, rgba.blue, rgba.alpha"

    def _get_channels_out(self, model):

        # Guess the type from the model shape
        # TODO : this is weakly enforced, bolster
        shape = model.output_shape
        if shape is not None and len(shape) == 4:
            _b, c, _h, _w = shape
            if c == 4:
                return "rgba.red, rgba.green, rgba.blue, rgba.alpha"
            if c == 3:
                return "rgba.red, rgba.green, rgba.blue"
            if c == 1:
                return "rgba.alpha"
        return "rgba.red, rgba.green, rgba.blue, rgba.alpha"

    def _run_nuke_script(
        self, model_id, torchscript, cat_path, channels_in, channels_out
    ):
        current_path = os.path.dirname(__file__)
        script_path = current_path + "/pytorch_to_cat.py"
        args = [
            "nuke",
            "-i",  # HACK : -t does not actually execute the node
            script_path,
            "--cat_path",
            cat_path,
            "--torchscript",
            torchscript,
            "--channels_in",
            channels_in,
            "--channels_out",
            channels_out,
            "--model_id",
            model_id,
        ]
        subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=True,
        )
