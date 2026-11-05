# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.system import RMTCException, Device
from rmtc.ops.artifacts import Model


class RemoteModel(Model):

    def __init__(
        self,
        name=None,
        model_id=None,
        version=None,
        credentials_id=None,
        uri=None,
        timeout=None,
        retries=None,
        max_batch=None,
        options=None,
        context=None,
        licenses=None,
        input_names=None,
        input_types=None,
        input_packager=None,
        output_names=None,
        output_types=None,
        output_packager=None,
        ancestors=None,
    ):
        super(RemoteModel, self).__init__(
            name=name,
            model_id=model_id,
            context=context,
            version=version,
            uri=uri,
            licenses=licenses,
            ancestors=ancestors,
            input_names=input_names,
            input_types=input_types,
            input_packager=input_packager,
            output_names=output_names,
            output_types=output_types,
            output_packager=output_packager,
        )
        self.add_property("credentials_id", str, credentials_id)
        self.add_property("timeout", int, timeout)
        self.add_property("retries", int, retries)
        self.add_property("max_batch", int, max_batch)
        self.add_property("options", dict, options)

    def reset(self):
        pass

    def is_valid(self):
        return True

    def load_weights(self, weights):
        raise RMTCException(f"Cloud Model {self.uri} cannot load weights {weights.uri}")

    def create_weights(self, run=None, **kwargs):
        raise NotImplementedError()

    def load_checkpoint(self, checkpoint):
        raise RMTCException(f"Cloud Models cannot load checkpoint {checkpoint.uri}")

    def create_checkpoint(self, run=None, **kwargs):
        raise RMTCException(f"Cloud Model {self.uri} cannot create checkpoint ")

    def move(self, device):
        pass

    def get_device(self):
        return Device.REM

    def set_internal_model(self, model):
        raise NotImplementedError()

    def get_internal_model(self):
        raise NotImplementedError()


class HTTPModel(Model):
    pass


class CloudModel(RemoteModel):
    pass
