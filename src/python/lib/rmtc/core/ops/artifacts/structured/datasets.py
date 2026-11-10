# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


from rmtc.ops.artifacts import Dataset
from rmtc.system.containers import ColumnTableIterator


class MappedAssets(Dataset):
    """
    Paring of assets with JSON rows for specific labelling or annotation.
    """

    def __init__(
        self,
        name=None,
        context=None,
        uri=None,
        io=None,
        licenses=None,
        columns=None,
    ):
        super(MappedAssets, self).__init__(
            name=name,
            context=context,
            uri=uri,
            io=io,
            licenses=licenses,
            columns=columns,
        )
        self._assets = []
        self._values = []

    def reset(self):
        """Clear all loaded source and destination image lists."""
        super(MappedAssets, self).reset()
        self._assets = []
        self._values = []

    def __iter__(self):
        return ColumnTableIterator([self._assets, self._values])

    def fill_row(self, row):
        if len(row) == 0:
            return []
        self._assets.append(row[0])
        self._values.append(row[1])
        return super(MappedAssets, self).fill_row(row)

    def empty_row(self, row):
        if len(row) == 0:
            return []
        self._assets.remove(row[0])
        self._values.remove(row[1])
        return super(MappedAssets, self).empty_row(row)

    def is_valid(self):
        return len(self._assets + self._values) > 0
