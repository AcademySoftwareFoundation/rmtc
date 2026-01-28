# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
NOTE : 
These folder based datasets are for testing ONLY and
will be removed shortly.

They need to be changed to be simple collections
with the IO object being responsible for loading the files
into the asset list.

Datasets should be abstract from their storage. Much like
assets.
"""

from rmtc.artifacts import Correlation, Asset, Dataset
from rmtc.system import Type, RMTCException, URI
from rmtc.io import IO
from rmtc.objects import IN


class FolderIO(IO):
    """
    A collection of assets in a folder

    TODO : this is a fudge, we should have a simple
    collection of correlated assets and then read as the
    rows as progressed through, using an IO object that reads
    the files from a URI.

    Basically Folder and CorrelatedFolder should not really exist
    consider this class already deprecated
    """

    def __init__(
        self,
        asset_io=None,
        asset_type=None,
        row=0,
    ):
        super(FolderIO, self).__init__()
        self.add_property(
            "asset_type",
            Type,
            asset_type,
            default=Type(type_class=Asset),
        )
        self.add_property("asset_io", IO, asset_io, direction=IN)
        self.add_property(
            "asset_type",
            Type,
            asset_type,
            default=Type(type_class=Asset),
        )
        self.add_property(
            "row",
            int,
            row,
        )

    def is_artifact_supported(self, artifact):
        return isinstance(artifact, Dataset)

    def is_uri_supported(self, uri):
        return uri.scheme == "file"

    def read(self, artifact, uri):

        folder = uri.path
        artifact.assets = []
        filenames = []
        if folder.is_dir():
            for file in folder.glob("*.*"):
                if self.asset_io.is_uri_supported(
                    URI(host="localhost", path=file, scheme="file")
                ):
                    filenames.append(file)
        if len(filenames) == 0:
            return
        for filename in filenames:
            uri = URI(scheme="file", host="localhost", path=filename)
            asset = self.asset_type()
            asset.name = uri.path.stem
            asset.uri = uri
            asset.io = self.asset_io
            row = [None, None]
            row[self.row] = asset
            artifact.add_row(row)

    def write(self, artifact, uri):

        # create our path
        uri.create()

        # write out the rows in the dataset
        for row in artifact:
            asset = row[self.row]
            asset.uri = self.asset_io.create_uri(asset)
            asset.uri.path = uri.path / asset.uri.path
            asset.io = self.asset_io
            asset.io.write(asset, asset.uri)


class CorrelatedFolderIO(IO):
    """
    Dataset for paired image files organized in alternating folder structure.

    The CorrelatedFolder loads image pairs from a folder where files
    are organized in alternating source-destination pairs. Even-indexed files
    (0, 2, 4, ...) are treated as source images, while odd-indexed files
    (1, 3, 5, ...) are treated as destination/target images.

    This dataset type is commonly used for image-to-image translation tasks,
    super-resolution, denoising, or other paired image learning scenarios
    where input-output relationships need to be maintained.
    """

    def __init__(
        self,
        asset_io=None,
        asset_type=None,
    ):
        """Initialize CorrelatedFolder with folder URI and EXR reader."""
        super(CorrelatedFolderIO, self).__init__()
        self.add_property("asset_io", IO, asset_io, direction=IN)
        self.add_property(
            "asset_type",
            Type,
            asset_type,
            default=Type(type_class=Asset),
        )

    def is_artifact_supported(self, artifact):
        return isinstance(artifact, Correlation)

    def is_uri_supported(self, uri):
        return uri.scheme == "file"

    def read(self, artifact, uri):
        """
        Load and pair image files from the specified folder.

        This artifact manages loading itself rather than deferring to
        an IO object.
        """
        folder = uri.path
        if not folder.exists():
            raise RMTCException(f"Invalid folder path '{folder}'")
        artifact.reset()
        filenames = []
        if folder.is_dir():
            for file in folder.glob("*.*"):
                uri = URI(scheme="file", path=file, host="localhost")
                if self.asset_io.is_uri_supported(uri):
                    filenames.append(file)
        filenames.sort()
        i = 1
        src = None
        dst = None
        for filename in filenames:
            uri = URI(scheme="file", host="localhost", path=filename)
            if self.asset_io.is_uri_supported(uri):
                asset = self.asset_type()
                asset.name = uri.path.stem
                asset.uri = uri
                asset.io = self.asset_io
                if i % 2:
                    src = asset
                else:
                    dst = asset
                    artifact.add_row([src, dst])
                i += 1

    def write(self, artifact, uri):

        # create our path
        uri.create()

        # write out the rows in the dataset
        for asset in artifact.assets:
            asset.uri = self.asset_io.create_uri(asset)
            asset.uri.path = uri.path / asset.uri.path
            asset.io = self.asset_io
            asset.io.write(asset, asset.uri)
