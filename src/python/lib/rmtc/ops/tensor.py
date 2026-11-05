# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import numpy as np

from rmtc.system import RMTCException, DataType

# wrap for numpy array, modicum of abstraction
Array = np.ndarray


class Tensor:
    """This is a convinience class for wrapping or creating an internal numpy tensor"""

    LABEL_SIZE = 128

    def __init__(
        self,
        array=None,
        values=None,
        shape=None,
        data_type=DataType.FLOAT32,
    ):
        # setup internal tensor
        self._tensor = array
        if array is None:
            self._tensor = self.create_array(
                values=values,
                shape=shape,
                data_type=data_type,
            )

    def get(self):
        return self._tensor

    def set(self, value):
        self._tensor = value

    def __getitem__(self, key):
        return self._tensor[key]

    def __setitem__(self, key, value):
        self._tensor[key] = value

    def is_data_type(self, data_type):
        return self._tensor.dtype == self.to_array_type(data_type)

    @property
    def shape(self):
        return self._tensor.shape

    @classmethod
    def create_array(
        cls,
        values=None,
        shape=None,
        data_type=DataType.FLOAT32,
    ):
        dtype = cls.to_array_type(data_type)
        if values is not None:
            return np.asarray(values, dtype=dtype)
        if shape is not None:
            return np.zeros(shape, dtype=dtype)
        return None

    @classmethod
    def to_array_type(cls, dtype):
        if dtype == DataType.FLOAT16:
            return np.float16
        if dtype == DataType.FLOAT32:
            return np.float32
        if dtype == DataType.FLOAT64:
            return np.float64
        if dtype == DataType.INT8:
            return np.int8
        if dtype == DataType.INT16:
            return np.int16
        if dtype == DataType.INT32:
            return np.int32
        if dtype == DataType.INT64:
            return np.int64
        if dtype == DataType.UINT8:
            return np.uint8
        if dtype == DataType.UINT16:
            return np.uint16
        if dtype == DataType.UINT32:
            return np.uint32
        if dtype == DataType.UINT64:
            return np.uint64
        if dtype == DataType.BOOL:
            return np.bool_
        if dtype == DataType.LABEL:
            return f"U{cls.LABEL_SIZE}"  # fixed unicode string
        raise RMTCException(f"Unsupported datatype {dtype}")

    @classmethod
    def from_array_type(cls, dtype):
        if dtype == np.float16:
            return DataType.FLOAT16
        if dtype == np.float32:
            return DataType.FLOAT32
        if dtype == np.float64:
            return DataType.FLOAT64
        if dtype == np.int8:
            return DataType.INT8
        if dtype == np.int16:
            return DataType.INT16
        if dtype == np.int32:
            return DataType.INT32
        if dtype == np.int64:
            return DataType.INT64
        if dtype == np.uint8:
            return DataType.UINT8
        if dtype == np.uint16:
            return DataType.UINT16
        if dtype == np.uint32:
            return DataType.UINT32
        if dtype == np.uint64:
            return DataType.UINT64
        if dtype == np.bool_:
            return DataType.BOOL
        if dtype == f"U{cls.LABEL_SIZE}":
            dtype = DataType.LABEL
        raise RMTCException(f"Unsupported datatype {dtype}")
