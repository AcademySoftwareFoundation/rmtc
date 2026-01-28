# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


from rmtc.artifacts import Repository
from rmtc.containers import ColumnTableIterator


class MappedAssets(Repository):
    """
    Paring of assets with JSON rows for specific labelling or annotation.
    """

    def __init__(
        self,
        name=None,
        project=None,
        uri=None,
        io=None,
        licenses=None,
    ):
        super(MappedAssets, self).__init__(
            name=name,
            project=project,
            uri=uri,
            io=io,
            licenses=licenses,
        )
        self._assets = []
        self._values = []

    def read(self, asset_manager):
        asset_manager.read([self])

    def write(self, asset_manager):
        asset_manager.write([self])

    def reset(self):
        """Clear all loaded source and destination image lists."""
        self._assets = []
        self._values = []

    def __iter__(self):
        return ColumnTableIterator([self._assets, self._values])

    def add_row(self, row):

        asset = row[0]
        values = row[1]

        self._assets.append(asset)
        self._values.append(values)

    def remove_row(self, row):
        self._assets.remove(row[0])
        self._values.remove(row[1])

    def empty(self):
        return len(self._assets) == 0

    def rows(self):
        return len(self._assets)

    def is_valid(self):
        for asset in self._assets + self._values:
            if asset is None:
                return False
        return True
