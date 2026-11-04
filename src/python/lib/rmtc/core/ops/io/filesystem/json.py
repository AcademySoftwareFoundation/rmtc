# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


import json
from pathlib import Path

import numpy as np

from rmtc.ops.io import IO
from rmtc.system import RMTCException, URI, Type
from rmtc.ops.artifacts import Asset, Dataset
from rmtc.ops.assets import Values
from rmtc.system.objects import IN
from rmtc.ops.tensor import Tensor


class TensorJSONFile(IO):
    """
    Read and write RAW numpy tensors to JSON
    """

    def create_name(self, artifact):
        return str(Path(artifact.name + ".json"))

    def get_scheme(self):
        return "file"

    def get_artifact_type(self):
        return Asset

    def is_uri_supported(self, uri):
        return uri.scheme == "file"

    def read(self, uri, artifact, asset_manager):
        asset = artifact
        if not artifact.is_valid():
            with open(uri.path, "r", encoding="utf8") as jsonfile:
                json_data = json.load(jsonfile)
                tensors = []
                structure = asset.structure()
                tensor_count = len(structure)
                for i in range(tensor_count):
                    shape = structure[i][0]
                    data_type = structure[i][1]
                    tensor = Tensor.create_array(
                        values=json_data[i],
                        shape=shape,
                        data_type=data_type,
                    )
                    tensors.append(tensor)
                asset.tensors = tuple(tensors)

    def write(self, uri, artifact, asset_manager):
        asset = artifact
        if asset.is_valid():
            tensors = []
            for tensor in asset.tensors:
                tensors.append(tensor.tolist())
            # exclusive create when immutable - the write claims the path
            mode = "x" if asset_manager.is_immutable() else "w"
            with open(uri.path, mode, encoding="utf8") as json_file:
                json.dump(tensors, json_file, indent=4)


class ValuesJSONFile(IO):
    """Write out each individual values asset into it's own JSON file"""

    def __init__(
        self,
        index=0,
    ):
        super(ValuesJSONFile, self).__init__()
        self.add_property("index", int, index)

    def create_name(self, artifact):
        return str(Path(artifact.name + ".json"))

    def get_scheme(self):
        return "file"

    def get_artifact_type(self):
        return Values

    def is_uri_supported(self, uri):
        return uri.scheme == "file"

    def read(self, uri, artifact, asset_manager):

        if not self.is_artifact_supported(artifact):
            raise RMTCException(
                f"Mismatched artifact {artifact} with reader writer {self}"
            )
        with open(uri.path, "r", encoding="utf8") as json_file:
            json_data = json.load(json_file)

        # sort the data first as JSON removes that information
        values = [json_data[key] for key in sorted(json_data, key=int)]

        # assign to the tensor
        artifact.tensors = (np.array(values, dtype="float32"),)

    def write(self, uri, artifact, asset_manager):

        if not self.is_artifact_supported(artifact):
            raise RMTCException(
                f"Mismatched artifact {artifact} with reader writer {self}"
            )
        json_data = {}
        values = artifact.tensors[0].tolist()
        for i, value in zip(range(len(values)), values):
            json_data[i] = value
        mode = "x" if asset_manager.is_immutable() else "w"
        with open(uri.path, mode, encoding="utf8") as json_file:
            json.dump(json_data, json_file, indent=4)


class AssetValuesJSONFile(IO):
    """IO class to read a list of assets with labels"""

    def __init__(
        self,
        asset_type=None,
        asset_io=None,
    ):
        super(AssetValuesJSONFile, self).__init__()
        self.add_property("asset_io", IO, asset_io, direction=IN)
        self.add_property(
            "asset_type",
            Type,
            asset_type,
            default=Type(type_class=Asset),
        )

    def get_scheme(self):
        return "file"

    def get_artifact_type(self):
        return Dataset

    def is_uri_supported(self, uri):
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".json"
        return False

    def read(self, uri, artifact, asset_manager):

        # check
        dataset = artifact
        if not self.is_artifact_supported(dataset):
            raise RMTCException(
                f"Mismatched artifact {dataset} with reader writer {self}"
            )
        if dataset.uri.scheme == "file" and not dataset.uri.path.exists():
            raise RMTCException(f"Invalid JSON path '{uri}'")

        # load and iterate
        with open(uri.path, "r", encoding="utf8") as jsonfile:
            rows = json.load(jsonfile)
            for key, label in rows.items():

                # constuct our asset type
                uri = URI(string=key)
                asset = self.asset_type()
                asset.name = uri.path.stem
                asset.uri = uri
                asset.io = self.asset_io

                # constuct a values asset and set it
                values = Values()
                values.read = lambda *args, **kwargs: None  # Monkey patch read()
                tensor = np.zeros(len(label), dtype="float32")
                for i, element in enumerate(label):
                    tensor[i] = element
                values.tensors = (tensor,)

                # add the row to the dataset
                dataset.fill_row([asset, values])

    def write(self, uri, artifact, asset_manager):

        # check
        dataset = artifact
        if not self.is_artifact_supported(dataset):
            raise RMTCException(
                f"Mismatched artifact {dataset} with reader writer {self}"
            )

        # update
        json_data = {}
        for row in dataset:
            json_data[row[0]] = row[1].tensors[0].tolist()
        mode = "x" if asset_manager.is_immutable() else "w"
        with open(uri.path, mode, encoding="utf8") as json_file:
            json.dump(json_data, json_file, indent=4)


class MappedAssetsJSONFile(IO):
    """The JSON contains a Map of URI to URI"""

    def __init__(
        self,
        io_instances=None,
        asset_types=None,
    ):
        super(MappedAssetsJSONFile, self).__init__()
        self.add_property("io_instances", [IO], io_instances)
        self.add_property("asset_types", [Type], asset_types)

    def get_scheme(self):
        return "file"

    def get_artifact_type(self):
        return Dataset

    def create_name(self, artifact):
        return str(Path(artifact.name + ".json"))

    def is_uri_supported(self, uri):
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".json"
        return False

    def read(self, uri, artifact, asset_manager):

        dataset = artifact

        # check
        if not self.is_artifact_supported(dataset):
            raise RMTCException(
                f"Mismatched artifact {dataset} with reader writer {self}"
            )
        if dataset.uri.scheme == "file" and not dataset.uri.path.exists():
            raise RMTCException(f"Invalid JSON path '{uri}'")

        # load
        with open(uri.path, "r", encoding="utf8") as jsonfile:
            rows = json.load(jsonfile)
            for src, dst in rows.items():
                src_asset = self.asset_types[0](
                    uri=URI(string=src),
                    io=self.io_instances[0],
                )
                dst_asset = self.asset_types[1](
                    uri=URI(string=dst),
                    io=self.io_instances[1],
                )
                dataset.add_row([src_asset, dst_asset])

    def write(self, uri, artifact, asset_manager):

        dataset = artifact
        if not self.is_artifact_supported(dataset):
            raise RMTCException(
                f"Mismatched artifact {dataset} with reader writer {self}"
            )
        json_data = {}
        for row in dataset:
            json_data[row[0].uri] = row[1].uri
        mode = "x" if asset_manager.is_immutable() else "w"
        with open(uri.path, mode, encoding="utf8") as json_file:
            json.dump(json_data, json_file, indent=4)
