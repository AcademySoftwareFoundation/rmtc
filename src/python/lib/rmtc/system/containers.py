# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from itertools import chain, zip_longest
import enum
from abc import ABC, abstractmethod


class Order(enum.IntEnum):
    ROW = 0
    COLUMN = 1


class Table(ABC):
    """
    Abstract base class to represent a 2D table of items - primarily datasets
    """

    @abstractmethod
    def names(self):
        """Get names of columns"""
        return []

    @abstractmethod
    def __iter__(self):
        """Start the row iteration"""
        return iter([])

    @abstractmethod
    def fill_row(self, row):
        """
        Add a row to the table by consuming the row
        If a table has a fixed column structure, it may not add all elements in the row
        Returns sublist of row it could not fit in the table
        """
        return []

    @abstractmethod
    def empty_row(self, row):
        """
        Remove row from table by consuming it
        If a table has a fixed column structure, it may not remove all elements in row
        Returns sublist of row it could not remove from the table
        """
        return []

    @abstractmethod
    def add_row(self, row):
        """
        Add whole row to the table - NQA
        """
        return False

    @abstractmethod
    def remove_row(self, row):
        """
        Remove whole row from table - NQA
        """
        return False

    @abstractmethod
    def rows(self):
        """Get the total number of rows"""
        return 0

    @abstractmethod
    def cols(self):
        """Get the total number of cols"""
        return 0

    @abstractmethod
    def empty(self):
        """Is this dataset empty"""
        return True

    @classmethod
    def generate_rows(cls, table_iterables):
        """
        Generator function to iterate through rows in iterables of tables
        """
        for row in zip_longest(*table_iterables):  # [[[1,2]],[[3]]...] etc.
            flattened_row = chain.from_iterable(row)  # iterable(1,2,3)
            yield list(flattened_row)  # [1,2,3] etc.


class TableIterator(ABC):
    """
    Abstract base class that always iterates as if a 2D table of items
    by returning a rows one at a time
    """

    @abstractmethod
    def __next__(self):
        """Return next row (list of lists)"""
        return [[]]


class PaddedTableIterator(TableIterator):

    def __init__(
        self,
        items,
        padding=1,
    ):
        self._items = items
        self._idx = 0
        self._padding = [None for x in range(padding)]

    def __next__(self):
        if self._idx >= len(self._items):
            raise StopIteration
        row = [self._items[self._idx]] + self._padding
        self._idx += 1
        return row

    def __iter__(self):
        return self


class StrideTableIterator(TableIterator):
    """Strided iterator to move across a linear array as a 2D table"""

    def __init__(
        self,
        items,
        stride=1,
    ):
        self._items = items
        self._stride = stride
        self._idx = 0

    def __next__(self):
        if (self._idx * self._stride) >= len(self._items):
            raise StopIteration
        row = self._items[self._idx : self._idx + self._stride]
        self._idx += self._stride
        return row

    def __iter__(self):
        return self


class RowTableIterator(TableIterator):
    """
    Iterator to move row by row across a 2D table
    Somewhat redundant, but provides a consistent iterator
    Iterator has an optional label key to permit access
    """

    def __init__(
        self,
        rows,
        labels=None,
    ):
        self._rows = rows
        self._idx = 0
        self._labels = labels

    def __getitem__(self, name):
        if self._labels is not None:
            try:
                i = self._labels.index(name)
                return self._rows[self._idx][i]
            except ValueError:
                pass
        return None

    def __next__(self):
        if self._idx >= len(self._rows):
            raise StopIteration
        row = self._rows[self._idx]
        self._idx += 1
        return row

    def __iter__(self):
        return self


class ColumnTableIterator(TableIterator):
    """
    Iterator to move column by column across a 2D table

    The table can be spartan, with some columns having fewer
    elements, in which case those cells are filled with None

    Iteration stops at the maximally indexed valid cell
    """

    def __init__(
        self,
        columns,
    ):
        self._columns = columns
        self._idx = 0
        self._max_rows = 0
        for col in self._columns:
            self._max_rows = max(self._max_rows, len(col))

    def __next__(self):
        if self._idx >= self._max_rows:
            raise StopIteration
        row = []
        for column in self._columns:
            item = None
            if self._idx < len(column):
                item = column[self._idx]
            row.append(item)
        self._idx += 1
        return row

    def __iter__(self):
        return self


class RowMajorIterator(TableIterator):
    """
    Iterate through the iterators one after the other
    """

    def __init__(self, iterators):
        self._iterators = iterators
        self._idx = 0

    def __iter__(self):
        return self

    def __next__(self):
        while self._idx < len(self._iterators):
            try:
                return self._iterators[self._idx].__next__()
            except StopIteration:
                self._idx += 1
        raise StopIteration


class ColMajorIterator(TableIterator):
    """
    Iterate through all the iterators at the same time and merge the result
    """

    def __init__(self, iterators):
        self._iterators = iterators

    def __iter__(self):
        return self

    def __next__(self):
        try:
            result = []
            for iterator in self._iterators:
                result.extend(iterator.__next__())
            return result
        except StopIteration:
            pass
        raise StopIteration
