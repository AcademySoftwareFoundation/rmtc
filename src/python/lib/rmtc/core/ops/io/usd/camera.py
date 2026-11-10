# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from pathlib import Path
import math

from pxr import Usd, UsdGeom, Gf, Tf

from rmtc.ops.io import IO
from rmtc.ops.assets import Camera
from rmtc.ops.artifacts import Dataset
from rmtc.system import Type


class USDCameraSequence(IO):
    """
    Read and write an animated camera as rows in a dataset
    """

    def __init__(
        self,
        fps=24.0,
        meters_per_unit=1.0,
        file_type="a",
        asset_type=None,
    ):
        super(USDCameraSequence, self).__init__()
        self.add_property("fps", float, fps)
        self.add_property("meters_per_unit", float, meters_per_unit)
        self.add_property("file_type", str, file_type)
        self.add_property(
            "asset_type",
            Type,
            asset_type,
            default=Type(type_class=Camera),
        )

    def create_name(self, artifact):
        return str(Path(artifact.name + f".usd{self.file_type}"))

    def is_artifact_supported(self, artifact):
        if not isinstance(artifact, Dataset):
            return False
        dataset = artifact
        camera = dataset[0][0]
        if not isinstance(camera, Camera):
            return False
        return True

    def get_scheme(self):
        return "file"

    def get_artifact_type(self):
        return Dataset

    def is_uri_supported(self, uri):
        if uri.scheme == "file":
            return uri.path.suffix.lower() in [
                ".usda",
                ".usdc",
                ".usdz",
                ".usd",
            ]
        return False

    def init(self, artifact, asset_manager):
        dataset = artifact
        for i, row in enumerate(dataset):
            for c, asset in enumerate(row):
                if dataset.columns:
                    c = dataset.columns[c]
                asset.name = f"{dataset.name}_{i:04}-{c:01}"  # rename
        return True

    def read(self, uri, artifact, asset_manager):

        dataset = artifact

        # get frame count
        stage = Usd.Stage.Open(str(uri.path))
        root = stage.GetRootLayer()
        start = root.startTimeCode
        end = root.endTimeCode

        # TODO : unify to the framerate of the FPS
        frames = int(end - start)

        # collect cameras
        for frame in range(frames):  # pylint: disable=unused-variable
            camera = Camera()
            camera.init()  # TODO: load tensors
            dataset.fill_row([camera])

    def write(self, uri, artifact, asset_manager):

        # get the values
        dataset = artifact
        camera = dataset[0][0]

        # constuct a stage and export
        stage = Usd.Stage.CreateNew(str(uri.path))
        stage.SetFramesPerSecond(float(self.fps))
        stage.SetStartTimeCode(int(0))
        stage.SetEndTimeCode(int(len(dataset)))
        stage.SetTimeCodesPerSecond(float(self.fps))
        UsdGeom.SetStageMetersPerUnit(stage, float(self.meters_per_unit))
        cam = UsdGeom.Camera.Define(stage, f"/{Tf.MakeValidIdentifier(camera.name)}")

        # intrinsics - convert to meters from mm
        sensor_width = float(camera.aperture[0] * 0.001)
        sensor_height = float(camera.aperture[1] * 0.001)
        cx = float(camera.center[0] * 0.001)
        cy = float(camera.center[1] * 0.001)
        cam.CreateHorizontalApertureAttr(sensor_width)
        cam.CreateVerticalApertureAttr(sensor_height)
        cam.CreateHorizontalApertureOffsetAttr(cx)
        cam.CreateVerticalApertureOffsetAttr(cy)

        # animatable properties
        xform = UsdGeom.Xformable(cam)
        t = xform.AddTranslateOp()
        r = xform.AddRotateXYZOp()
        f = cam.CreateFocalLengthAttr()

        # set keys
        for frame, row in enumerate(dataset):
            for camera in row:

                # double check
                if not isinstance(camera, Camera):
                    continue
                if not camera.is_valid():
                    continue

                # set T & R only
                m = camera.matrix
                usd_matrix = Gf.Matrix4d(
                    m[0][0],
                    m[1][0],
                    m[2][0],
                    m[3][0],
                    m[0][1],
                    m[1][1],
                    m[2][1],
                    m[3][1],
                    m[0][2],
                    m[1][2],
                    m[2][2],
                    m[3][2],
                    m[0][3],
                    m[1][3],
                    m[2][3],
                    m[3][3],
                )
                translation = usd_matrix.ExtractTranslation()
                rotation = usd_matrix.ExtractRotation().Decompose(
                    Gf.Vec3d(1, 0, 0),
                    Gf.Vec3d(0, 1, 0),
                    Gf.Vec3d(0, 0, 1),
                )

                # compute diagonal focal length in meters
                focal_length = (
                    math.sqrt(camera.focal_length[0] * camera.focal_length[1]) * 0.001
                )

                # assign
                t.Set(
                    time=float(frame),
                    value=Gf.Vec3d(translation[0], translation[1], translation[2]),
                )
                r.Set(
                    time=float(frame),
                    value=Gf.Vec3d(rotation[0], rotation[1], rotation[2]),
                )
                f.Set(
                    time=float(frame),
                    value=float(focal_length),
                )

        # save
        stage.GetRootLayer().Save()


class USDCamera(IO):

    def create_name(self, artifact):
        return str(Path(artifact.name + ".usda"))

    def get_scheme(self):
        return "file"

    def get_artifact_type(self):
        return Camera

    def is_uri_supported(self, uri):
        """Check if URI points to a valid .exr file."""
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".usda"
        return False

    def read(self, uri, artifact, asset_manager):
        raise NotImplementedError()

    def write(self, uri, artifact, asset_manager):

        # get the values
        camera = artifact
        f = float(math.sqrt(camera.focal_length[0] * camera.focal_length[1]))
        sensor_width = float(camera.aperture[0])
        sensor_height = float(camera.aperture[1])
        cx = float(camera.center[0])
        cy = float(camera.center[1])

        # constuct a stage and export
        stage = Usd.Stage.CreateNew(str(uri.path))
        cam = UsdGeom.Camera.Define(stage, f"/{Tf.MakeValidIdentifier(camera.name)}")

        # intrinsics
        cam.CreateFocalLengthAttr(f)
        cam.CreateHorizontalApertureAttr(sensor_width)
        cam.CreateVerticalApertureAttr(sensor_height)
        cam.CreateHorizontalApertureOffsetAttr(cx)
        cam.CreateVerticalApertureOffsetAttr(cy)

        # extrinsics
        m = camera.matrix
        usd_matrix = Gf.Matrix4d(
            m[0][0],
            m[1][0],
            m[2][0],
            m[3][0],
            m[0][1],
            m[1][1],
            m[2][1],
            m[3][1],
            m[0][2],
            m[1][2],
            m[2][2],
            m[3][2],
            m[0][3],
            m[1][3],
            m[2][3],
            m[3][3],
        )
        translation = usd_matrix.ExtractTranslation()
        rotation = usd_matrix.ExtractRotation().Decompose(
            Gf.Vec3d(1, 0, 0),
            Gf.Vec3d(0, 1, 0),
            Gf.Vec3d(0, 0, 1),
        )
        xform = UsdGeom.Xformable(cam)
        t = xform.AddTranslateOp()
        r = xform.AddRotateXYZOp()
        t.Set(Gf.Vec3d(translation[0], translation[1], translation[2]))
        r.Set(Gf.Vec3d(rotation[0], rotation[1], rotation[2]))

        # save
        stage.GetRootLayer().Save()
