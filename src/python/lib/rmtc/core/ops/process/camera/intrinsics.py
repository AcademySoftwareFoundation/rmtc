# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.ops.tensor import Array, Tensor
from rmtc.ops.process import Process
from rmtc.system import DataType


class ConvertAperture(Process):

    def __init__(
        self,
        image_width=None,
        image_height=None,
        sensor_width=None,
        sensor_height=None,
    ):
        super(ConvertAperture, self).__init__()
        self.add_property("image_width", int, image_width)
        self.add_property("image_height", int, image_height)
        self.add_property("sensor_width", int, sensor_width)
        self.add_property("sensor_height", int, sensor_height)

    def run(self, tensors: tuple[Array]) -> tuple[Array]:

        # set the sensor size
        sensor = Tensor.create_array(
            values=[self.sensor_width, self.sensor_height],
            data_type=DataType.FLOAT32,
        )
        pixel_width = self.sensor_width / self.image_width
        pixel_height = self.sensor_height / self.image_height

        # process camera intrinsics - specifically into mm
        intrinsics = tensors[1]
        fx = intrinsics[0, 0]
        fy = intrinsics[1, 1]
        cx = intrinsics[0, 2]
        cy = intrinsics[1, 2]
        fx_mm = fx * pixel_width
        fy_mm = fy * pixel_height
        cx_mm = (cx - (self.sensor_width / 2)) * pixel_width
        cy_mm = (cy - (self.sensor_height / 2)) * pixel_height
        intrinsics = Tensor.create_array(
            values=[
                [fx_mm, 0, cx_mm],
                [0, fy_mm, cy_mm],
                [0, 0, 1],
            ],
            data_type=DataType.FLOAT32,
        )

        # extrinsics
        extrinsics = tensors[0]

        # add to camera data
        return (extrinsics, intrinsics, sensor)

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        return tensors
