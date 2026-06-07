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

from rmtc.artifacts import Image, Repository, Asset
from rmtc.system import Type, RMTCException, URI
from rmtc.io import IO
from rmtc.containers import PaddedTableIterator, ColumnTableIterator
from rmtc.objects import IN


class Folder(Repository):
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
        name=None,
        project=None,
        uri=URI(),
        licenses=None,
        asset_io=None,
        asset_type=None,
    ):
        super(Folder, self).__init__(
            name=name,
            project=project,
            uri=uri,
            licenses=licenses,
        )
        self._assets = []
        self.add_property(
            "asset_type",
            Type,
            asset_type,
            default=Type(type_class=Asset),
        )
        self.add_property("asset_io", IO, asset_io, direction=IN)

    def read(self, asset_manager):

        # resolve the URI to disk location
        resolved_uri = asset_manager.resolve([self.uri])[0]

        if self.asset_type is None:
            raise RMTCException("Invalid asset type")
        folder = resolved_uri.path
        self._assets = []
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
            self._assets.append(asset)

    def write(self, asset_manager):

        # resolve the URI to disk location
        resolved_uri = asset_manager.resolve([self.uri])[0]

        # create our path
        resolved_uri.create()

        # write out the rows in the dataset
        asset_manager.write(self._assets)

    def __iter__(self):
        return PaddedTableIterator(self._assets, 1)

    def reset(self):
        self._assets = []

    def add_row(self, row):
        for asset in row:
            if asset is not None:

                # place the asset in the folder
                asset.uri = self.asset_io.create_uri(asset)
                asset.uri.path = self.uri.path / asset.uri.path
                asset.io = self.asset_io

                # add to list
                self._assets.append(asset)

    def remove_row(self, row):
        for asset in row:
            if asset is not None:
                self._assets.remove(asset)

    def empty(self):
        return len(self._assets) == 0

    def rows(self):
        return len(self._assets)

    def is_valid(self):
        for asset in self._assets:
            if asset is None:
                return False
        return True


class CorrelatedFolder(Repository):
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
        name=None,
        project=None,
        uri=URI(),
        licenses=None,
        asset_io=None,
    ):
        """Initialize CorrelatedFolder with folder URI and EXR reader."""
        super(CorrelatedFolder, self).__init__(
            name=name,
            project=project,
            uri=uri,
            licenses=licenses,
        )
        self._src = []
        self._dst = []
        self.add_property("asset_io", IO, asset_io, direction=IN)

    def read(self, asset_manager):
        """
        Load and pair image files from the specified folder.

        This artifact manages loading itself rather than deferring to
        an IO object.
        """
        resolved_uri = asset_manager.resolve([self.uri])[0]
        folder = resolved_uri.path
        if not folder.exists():
            raise RMTCException(f"Invalid folder path '{folder}'")
        self._src = []
        self._dst = []
        filenames = []
        if folder.is_dir():
            for file in folder.glob("*.*"):
                uri = URI(scheme="file", path=file, host="localhost")
                if self.asset_io.is_uri_supported(uri):
                    filenames.append(file)
        filenames.sort()
        i = 0
        for filename in filenames:
            if filename.suffix == ".exr":  # image
                uri = URI(scheme="file", host="localhost", path=filename)
                asset = Image(
                    name=uri.path.stem,
                    uri=uri,
                    io=self.asset_io,
                )
                if i % 2:
                    self._dst.append(asset)
                else:
                    self._src.append(asset)
                i += 1
        if len(self._src) != len(self._dst):
            self._src = []
            self._dst = []
            raise RMTCException("File list lengths do not match between src and dst")

    def write(self, asset_manager):

        resolved_uri = asset_manager.resolve([self.uri])[0]

        # create our path
        resolved_uri.create()

        # write out the rows in the dataset
        asset_manager.write(self._src + self._dst)

    def reset(self):
        """Clear all loaded source and destination image lists."""
        self._src = []
        self._dst = []

    def __iter__(self):
        return ColumnTableIterator([self._src, self._dst])

    def add_row(self, row):
        self._src.append(row[0])
        self._dst.append(row[1])
        for asset in self._src + self._dst:
            asset.uri = self.io.create_uri(asset)
            asset.uri.path = self.uri.path / asset.uri.path
            asset.io = self.io

    def remove_row(self, row):
        self._src.remove(row[0])
        self._dst.remove(row[1])

    def empty(self):
        return len(self._src) == 0

    def rows(self):
        return len(self._src)

    def is_valid(self):
        for asset in self._src + self._dst:
            if asset is None:
                return False
        return True
