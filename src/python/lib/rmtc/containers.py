# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from abc import ABC, abstractmethod


class ITable(ABC):
    """
    Abstract base class to represent a 2D table of items - primarily datasets
    """

    @abstractmethod
    def __iter__(self):
        """Start the row iteration"""
        return iter([])

    @abstractmethod
    def add_row(self, row):
        """Add a row to the table"""
        return False

    @abstractmethod
    def remove_row(self, row):
        """Remove a row from the table"""
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


class ITableIterator(ABC):
    """
    Abstract base class that always iterates as if a 2D table of items
    by returning a rows one at a time
    """

    @abstractmethod
    def __next__(self):
        """Return next row (list of lists)"""
        return [[]]


class PaddedTableIterator(ITableIterator):

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


class StrideTableIterator(ITableIterator):
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


class RowTableIterator(ITableIterator):
    """
    Iterator to move row by row across a 2D table
    Somewhat redundant, but provides a consistent iterator
    """

    def __init__(
        self,
        rows,
    ):
        self._rows = rows
        self._idx = 0

    def __next__(self):
        if self._idx >= len(self._rows):
            raise StopIteration
        row = self._rows[self._idx]
        self._idx += 1
        return row

    def __iter__(self):
        return self


class ColumnTableIterator(ITableIterator):
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


class IteratorIterator:
    """
    An iterator of iterators - provide a list of iterators
    and it will sequentially iterate over them
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


class IterableIterator(IteratorIterator):
    """
    An iterator of iterables - provide a list of iterables
    and it will sequentially iterate over them
    """

    def __init__(self, iterables):
        iterators = [iterable.__iter__() for iterable in iterables]
        super(IterableIterator, self).__init__(iterators)
