# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


import json
import numpy as np

from rmtc.io import IO
from rmtc.system import RMTCException, URI, Type
from rmtc.containers import ITable
from rmtc.artifacts import Values, Asset
from rmtc.objects import IN


class ValuesJSONFile(IO):
    """Write out each individual values asset into it's own JSON file"""

    def __init__(
        self,
        index=0,
    ):
        super(ValuesJSONFile, self).__init__()
        self.add_property("index", int, index)

    def create_uri(self, artifact):
        new_uri = URI(scheme="file", host="localhost")
        new_uri.path /= artifact.name
        new_uri.path = new_uri.path.with_suffix(".json")
        return new_uri

    def is_artifact_supported(self, artifact):
        return isinstance(artifact, Values)

    def is_uri_supported(self, uri):
        return uri.scheme == "file"

    def read(self, artifact, uri):
        pass

    def write(self, artifact, uri):
        if not self.is_artifact_supported(artifact):
            raise RMTCException(
                f"Mismatched artifact {artifact} with reader writer {self}"
            )
        json_data = {}
        values = artifact.tensor.tolist()
        for i, value in zip(range(len(values)), values):
            json_data[i] = value
        with open(uri.path, "w", encoding="utf8") as json_file:
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

    def is_artifact_supported(self, artifact):
        return isinstance(artifact, ITable)

    def is_uri_supported(self, uri):
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".json"
        return False

    def read(self, artifact, uri):

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
                values.tensor = tensor

                # add the row to the dataset
                row = [asset, values]
                dataset.add_row(row)

    def write(self, artifact, uri):

        # check
        dataset = artifact
        if not self.is_artifact_supported(dataset):
            raise RMTCException(
                f"Mismatched artifact {dataset} with reader writer {self}"
            )

        # update
        json_data = {}
        for row in dataset:
            json_data[row[0]] = row[1].tensor.tolist()
        with open(uri.path, "w", encoding="utf8") as json_file:
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

    def is_artifact_supported(self, artifact):
        return isinstance(artifact, ITable)

    def create_uri(self, artifact):
        new_uri = URI(scheme="file", host="localhost")
        new_uri.path /= artifact.name
        new_uri.path = new_uri.path.with_suffix(".json")
        return new_uri

    def is_uri_supported(self, uri):
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".json"
        return False

    def read(self, artifact, uri):
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

    def write(self, artifact, uri):
        dataset = artifact
        if not self.is_artifact_supported(dataset):
            raise RMTCException(
                f"Mismatched artifact {dataset} with reader writer {self}"
            )
        if dataset.uri.scheme == "file" and not dataset.uri.path.exists():
            raise RMTCException(f"Invalid JSON path '{uri}'")
        json_data = {}
        for row in dataset:
            json_data[row[0].uri] = row[1].uri
        with open(uri.path, "w", encoding="utf8") as json_file:
            json.dump(json_data, json_file, indent=4)
