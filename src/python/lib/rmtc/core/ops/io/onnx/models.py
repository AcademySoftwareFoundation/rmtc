# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.core.ops.artifacts.onnx.models import ONNXModel

from rmtc.ops.io import IO
from rmtc.system import Device


class ONNXSessionFile(IO):
    """
    Reader/writer for ONNX models.
    """

    def __init__(
        self,
        device=Device.GPU,
    ):
        super(ONNXSessionFile, self).__init__()
        self.add_property("device", Device, device)

    def create_name(self, artifact):
        raise NotImplementedError()

    def get_scheme(self):
        return "file"

    def get_artifact_type(self):
        return ONNXModel

    def is_uri_supported(self, uri):
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".onnx"
        return False

    def read(self, uri, artifact, asset_manager):
        import onnxruntime as ort

        if self.load_session:
            # TODO : assumption GPU = CUDA
            providers = ["CPUExecutionProvider"]
            if self.device == Device.GPU:
                providers = ["CUDAExecutionProvider"] + providers
            artifact.session = ort.InferenceSession(uri.path, providers=providers)
        artifact.device = self.device

    def write(self, uri, artifact, asset_manager):
        raise NotImplementedError()


class ONNXModelFile(IO):
    """
    Reader/writer for ONNX models.
    """

    def create_name(self, artifact):
        raise NotImplementedError()

    def get_scheme(self):
        return "file"

    def get_artifact_type(self):
        return ONNXModel

    def is_uri_supported(self, uri):
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".onnx"
        return False

    def read(self, uri, artifact, asset_manager):
        import onnx

        artifact.model = onnx.load(uri.path)
        artifact.device = self.device

    def write(self, uri, artifact, asset_manager):
        import onnx

        if artifact.model:
            onnx.save(artifact.model, uri.path)
