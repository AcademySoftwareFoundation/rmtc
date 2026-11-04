# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
NOTE : 
These folder based datasets are for testing ONLY and
will be removed shortly.

They need to be changed to be simple collections
with the IO object being responsible for loading the files
into the asset list.

Aggregation should be abstract from their storage. Much like
assets.
"""

from rmtc.ops.artifacts import Asset, Dataset
from rmtc.system import Type, RMTCException, FileURI
from rmtc.ops.io import IO
from rmtc.system.objects import IN


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
    ):
        super(FolderIO, self).__init__()
        self.add_property(
            "asset_type",
            Type,
            asset_type,
            default=Type(type_class=Asset),
        )
        self.add_property("asset_io", IO, asset_io, member=True, direction=IN)

    def get_scheme(self):
        return "file"

    def get_artifact_type(self):
        return Dataset

    def is_artifact_supported(self, artifact):
        return isinstance(artifact, Dataset)

    def is_uri_supported(self, uri):
        return uri.scheme == "file"

    def init(self, artifact, asset_manager):
        dataset = artifact
        uri = dataset.uri
        for i, row in enumerate(dataset):
            for c, asset in enumerate(row):
                if dataset.columns:
                    c = dataset.columns[c]
                if asset.io is None:
                    asset.io = self.asset_io
                if not asset.uri.is_valid():
                    # member names are unique within the dataset folder,
                    # so no instantiated_at segment is needed
                    asset.name = f"{i:04}_{c}"  # rename
                    asset.uri = FileURI(path=uri.path / asset.io.create_name(asset))
        return True

    def read(self, uri, artifact, asset_manager):

        dataset = artifact
        folder = uri.path

        # clear it up
        dataset.reset()

        # get list of files in the directory
        artifact.assets = []
        filenames = []

        if folder.is_dir():
            for file in folder.glob("*.*"):
                if self.asset_io.is_uri_supported(FileURI(path=file)):
                    filenames.append(file)
        if len(filenames) == 0:
            return False

        # basic sort
        filenames.sort()

        # iterate
        for filename in filenames:
            uri = FileURI(path=filename)
            # TODO: this is going to make multiple entities for assets with same URI
            #       defer to the asset manager to get the singular asset
            #       this overlaps with the role of 'objects'
            asset = self.asset_type()
            asset.name = uri.path.stem
            asset.uri = uri
            asset.io = self.asset_io
            asset.reset()  # HACK: force a clear out here to read
            if dataset.columns == []:
                dataset.columns = ["1"]
            dataset.fill_row([asset])

        return True

    def write(self, uri, artifact, asset_manager):

        dataset = artifact

        # construct the folder
        uri.path.mkdir(parents=True, exist_ok=True)

        # write it out
        assets = set()
        for row in dataset:
            for asset in row:
                if asset.is_valid():
                    assets.add(asset)
        asset_manager.write(list(assets))

        return True


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

    def get_scheme(self):
        return "file"

    def get_artifact_type(self):
        return Dataset

    def is_uri_supported(self, uri):
        return uri.scheme == "file"

    def read(self, uri, artifact, asset_manager):
        """
        Load and pair image files from the specified folder.

        This artifact manages loading itself rather than deferring to
        an IO object.
        """
        dataset = artifact

        folder = uri.path
        if not folder.exists():
            raise RMTCException(f"Invalid folder path '{folder}'")
        asset_manager.reset([dataset])
        filenames = []
        if folder.is_dir():
            for file in folder.glob("*.*"):
                uri = FileURI(path=file)
                if self.asset_io.is_uri_supported(uri):
                    filenames.append(file)
        filenames.sort()
        i = 1
        src = None
        dst = None
        for filename in filenames:
            uri = FileURI(path=filename)
            if self.asset_io.is_uri_supported(uri):
                asset = self.asset_type()
                asset.name = uri.path.stem
                asset.uri = uri
                asset.io = self.asset_io
                if i % 2:
                    src = asset
                else:
                    dst = asset
                    dataset.fill_row([src, dst])
                i += 1

    def write(self, uri, artifact, asset_manager):

        dataset = artifact

        # create folder
        uri.path.mkdir(parents=True, exist_ok=True)

        # write out the rows in the dataset - don't store in the asset
        for row in dataset:
            for asset in row:
                if not asset.uri.is_valid():
                    asset.uri = FileURI(
                        path=uri.path / self.asset_io.create_name(asset)
                    )
                if asset.is_valid():
                    self.asset_io.write(asset.uri, asset, asset_manager)
