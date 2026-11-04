# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
The asset derivations.

We support basic VFX types, with formats that best match VFX e.g.
OpenGL style VBO buffers or width by height RGBA images.

These are not PyTorch/Tensorflow formats, the asset types in memory are intended
to be aligned with how a GPU, DCC or Game Engine uses such assets, not
how existing frameworks or research papers may represent them conventionally.

As such, asset processing for inputs and outputs is a core portion of the 
pipeline layers of RMTC when dealing with existing foundational models.

The end result is that with appropriate models - we prioritize the possibility 
for memory mappable assets in a C++ inference system, with the hope
for generic realtime inferencing within DCCs.

Note that we don't support lists of assets generically,
We support only 2D datasets, so lists of inputs have
to be managed as single datatypes so they can fill a single
slot in the 2D dataset table, it also means that batching & arrayed
elements are ecplitily managed. To provide arrayed inputs we support
by convention a 'plural' form of each asset:

* Value -> Values
* Label -> Labels
* Mesh -> Meshes

Of course, you can always use the plural types
and assume length of 1 is the same as a singular asset,
we simply provide the option for either.

For labels & values - they support the Pod interface for get/set so
the singular form can be treated as basic parameters in a model.
"""

from rmtc.ops.artifacts import Asset, Pod
from rmtc.system.objects import IN, OUT
from rmtc.system import URI, RMTCException, DataType
from rmtc.ops.tensor import Tensor


class Value(Asset, Pod):
    """
    Simple floating point value
    """

    def __init__(
        self,
        value=0,
        tensors=None,
    ):
        if tensors is None:
            tensors = (Tensor.create_array(values=[value], data_type=DataType.FLOAT32),)
        super(Value, self).__init__(tensors=tensors)

    def set(self, value):
        self.tensors[0][0] = value

    def get(self):
        return self.tensors[0][0]

    def structure(self):
        return (((1,), DataType.FLOAT32),)  # always 1


class Values(Asset, Pod):
    """
    Values asset representing a flat list of floating points
    """

    def __init__(
        self,
        values=None,
        name=None,
        context=None,
        uri=URI(),
        io=None,
        licenses=None,
        dependencies=None,
        tensors=None,
    ):
        """Initialize the Values asset."""
        super(Values, self).__init__(
            name=name,
            context=context,
            uri=uri,
            io=io,
            licenses=licenses,
            dependencies=dependencies,
            tensors=tensors,
        )
        if self.tensors is None:
            if values is None:
                values = []
            tensor = Tensor.create_array(values=values, data_type=DataType.FLOAT32)
            self.tensors = (tensor,)

    def __len__(self):
        return self.tensors[0].shape[0]

    def structure(self):
        return (((0,), DataType.FLOAT32),)  # always 1

    def set(self, value):
        self.tensors = (Tensor.create_array(values=value),)

    def get(self):
        return list(self.tensors[0])


class Label(Asset, Pod):
    """
    Single label string limited to LABEL_SIZE
    """

    def __init__(
        self,
        label="",
        tensors=None,
    ):
        super(Label, self).__init__(tensors=tensors)
        if self.tensors is None:
            labels = [label]
            tensor = Tensor.create_array(values=labels, data_type=DataType.LABEL)
            self.tensors = (tensor,)

    def set(self, value):
        labels = [value]
        tensor = Tensor.create_array(values=labels, data_type=DataType.LABEL)
        self.tensors = (tensor,)

    def get(self):
        return self.tensors[0][0]

    def structure(self):
        return (((1,), DataType.LABEL),)


class Labels(Asset, Pod):
    """
    Labels asset representing a list of string data of fixed LABEL_SIZE
    """

    def __init__(
        self,
        name=None,
        context=None,
        uri=URI(),
        io=None,
        licenses=None,
        dependencies=None,
        labels=None,
        tensors=None,
    ):
        super(Labels, self).__init__(
            uri=uri,
            name=name,
            context=context,
            io=io,
            licenses=licenses,
            dependencies=dependencies,
            tensors=tensors,
        )
        if self.tensors is None:
            tensor = Tensor.create_array(
                values=labels,
                shape=self.structure()[0][1],
                data_type=self.structure()[0][1],
            )
            self.tensors = (tensor,)

    def set(self, value):
        tensor = Tensor.create_array(
            values=value,
            shape=self.structure()[0][1],
            data_type=self.structure()[0][1],
        )
        self.tensors = (tensor,)

    def get(self):
        if self.tensors is not None:
            return self.tensors[0].tolist()
        return []

    def __len__(self):
        return self.tensors[0].shape[0]

    @property
    def labels(self):
        return self.get()

    def structure(self):
        return (((0,), DataType.LABEL),)


class Text(Labels):
    """
    Text is just a block of labels
    """

    pass


class Image(Asset):

    # TODO: this should WHC - to conform to standard image buffer shapes

    """
    Image asset representing RGBA tensor data.

    Images are stored as RGBA tensors with shape (H,W,4) containing 32-bit
    floating point values. This class provides specialized functionality for
    image data including dimension access methods and inherits all persistence
    and tensor management capabilities from the Asset base class.

    Why HWC? Because this is likely mappable to memory for performance
    outside a Python context and aligns with OpenEXR

    The tensor data represents image pixels in RGBA format where:
    - H (height): Number of pixel rows
    - W (width): Number of pixel columns
    - 4 channels: Red, Green, Blue, Alpha values
    - Values are typically 32-bit floating point in range [0.0, 1.0]
    """

    def __init__(
        self,
        name=None,
        context=None,
        uri=URI(),
        io=None,
        licenses=None,
        dependencies=None,
        colorspace=None,
        data_type=None,
        layer_name=None,
        tensors=None,
    ):
        """Initialize the Image asset."""
        super(Image, self).__init__(
            name=name,
            context=context,
            uri=uri,
            io=io,
            licenses=licenses,
            dependencies=dependencies,
            tensors=tensors,
        )
        # Color space ID (applies to R, G, B channels only)
        self.add_property("colorspace", str, colorspace)
        self.add_property(
            "data_type",
            int,
            data_type if data_type is not None else DataType.FLOAT32,
        )
        self.add_property("layer_name", str, layer_name)

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Image"

    @property
    def width(self):
        """Get the width of the image in pixels."""
        return self.tensors[0].shape[1]

    @property
    def height(self):
        """Get the height of the image in pixels."""
        return self.tensors[0].shape[0]

    @property
    def channels(self):
        """Get the channel count - generally 4 for RGBA"""
        return self.tensors[0].shape[2]

    def structure(self):
        # single pixel RGBA WHC image
        return (((0, 0, 4), DataType.FLOAT32),)


class Images(Asset):

    # TODO: this should WHC - to conform to standard image buffer shapes

    """
    Image asset representing RGBA tensor data.

    Images are stored as RGBA tensors with shape (H,W,4) containing 32-bit
    floating point values. This class provides specialized functionality for
    image data including dimension access methods and inherits all persistence
    and tensor management capabilities from the Asset base class.

    Why HWC? Because this is likely mappable to memory for performance
    outside a Python context and aligns with OpenEXR

    The tensor data represents image pixels in RGBA format where:
    - N (frames): Number of frames
    - H (height): Number of pixel rows
    - W (width): Number of pixel columns
    - 4 channels: Red, Green, Blue, Alpha values
    - Values are typically 32-bit floating point in range [0.0, 1.0]
    """

    @property
    def channels(self):
        """Get the channel count - generally 4 for RGBA"""
        return self.tensors[0].shape[3]

    @property
    def width(self):
        """Get the width of the image in pixels."""
        return self.tensors[0].shape[2]

    @property
    def height(self):
        """Get the height of the image in pixels."""
        return self.tensors[0].shape[1]

    @property
    def length(self):
        """Get the height of the image in pixels."""
        return self.tensors[0].shape[0]

    def structure(self):
        # single pixel RGBA WHC images
        return (((0, 0, 0, 4), DataType.FLOAT32),)


class Video(Images):
    """
    Video is a set of images with a framerate
    """

    def __init__(
        self,
        name=None,
        context=None,
        uri=URI(),
        io=None,
        licenses=None,
        dependencies=None,
        colorspace=None,
        data_type=None,
        layer_name=None,
        tensors=None,
        frame_rate=None,
    ):
        """Initialize the Image asset."""
        super(Video, self).__init__(
            name=name,
            context=context,
            uri=uri,
            io=io,
            licenses=licenses,
            dependencies=dependencies,
            tensors=tensors,
            colorspace=colorspace,
            layer_name=layer_name,
            data_type=data_type,
        )
        self.add_property("frame_rate", float, frame_rate)


class Mesh(Asset):
    """
    Mesh asset representing 3D geometry data compatible with Vulkan.

    Mesh data is stored as a structured tensor containing vertex and face
    information in a format optimized for Vulkan graphics API compatibility.
    The tensor structure includes vertex data with positions, normals, and
    UV coordinates, along with face indices for triangle definitions.

    The tensor data structure:
    - vertices: vertex/normal/uv representation with shape (8,N) where:
      - N is the number of vertices
      - 8 components per vertex: [x,y,z, nx,ny,nz, u,v]
        - x,y,z: vertex position coordinates
        - nx,ny,nz: normal vector components
        - u,v: texture UV coordinates
    - faces: triangle face indices with shape (3,M) where:
      - M is the number of triangular faces
      - 3 indices per face referencing vertices
    """

    def __init__(
        self,
        name=None,
        context=None,
        uri=URI(),
        io=None,
        licenses=None,
        dependencies=None,
        tensors=None,
    ):
        """Initialize the Mesh asset."""
        super(Mesh, self).__init__(
            uri=uri,
            name=name,
            context=context,
            io=io,
            licenses=licenses,
            dependencies=dependencies,
            tensors=tensors,
        )

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Mesh"

    @property
    def vertices(self):
        """
        Get the number of vertices in the mesh.

        Returns the count of vertices by accessing the first dimension of
        the tensor shape, which corresponds to the number of vertex entries
        in the (N,8) vertex data structure.
        """
        return self.tensors[0].shape[0]

    @property
    def faces(self):
        """
        Get the number of faces in the mesh.

        Returns the count of triangular faces by accessing the second dimension
        of the tensor shape, which corresponds to the number of face entries
        in the face index structure.
        """
        return self.tensors[1].shape[0]

    def structure(self):
        return (((0, 8), DataType.FLOAT32), ((0, 3), DataType.INT16))


class Structure(Asset):

    def __init__(self):
        super(Structure, self).__init__()
        self._members = []

    def get_members(self):
        return [member.name for member in self._members]

    def add_member(self, name, asset_type, asset=None):
        if not issubclass(asset_type, Asset):
            raise RMTCException(f"Member must be an asset type, not {asset_type}")
        member = self.add_property(
            name=name, type_class=asset_type, value=asset, direction=OUT
        )
        self._members.append(member)
        return member

    def structure(self):
        # TODO : structure is a collection of all the members
        raise NotImplementedError()


class Camera(Asset):
    """
    Camera extrinsics - 4x4 homogenous transform
    Camera intrinsics - aperature width & height in mm
    """

    def __init__(
        self,
        name=None,
        context=None,
        uri=URI(),
        io=None,
        licenses=None,
        dependencies=None,
        tensors=None,
    ):
        """Initialize the asset."""
        super(Camera, self).__init__(
            uri=uri,
            name=name,
            context=context,
            io=io,
            licenses=licenses,
            dependencies=dependencies,
            tensors=tensors,
        )

    @property
    def extrinsics(self):
        return self.tensors[0]

    @property
    def intrinsics(self):
        return self.tensors[1]

    @property
    def sensor(self):
        return self.tensors[2]

    @property
    def focal_length(self):
        return (self.intrinsics[0][0], self.intrinsics[1][1])

    @focal_length.setter
    def focal_length(self, value):
        self.init()
        self.intrinsics[0][0] = value[0]
        self.intrinsics[1][1] = value[1]

    @property
    def aperture(self):
        """aperature size in mm"""
        return (self.sensor[0], self.sensor[1])

    @aperture.setter
    def aperture(self, value):
        self.init()
        self.intrinsics[0] = value[0]
        self.intrinsics[1] = value[1]

    @property
    def center(self):
        """centre position on sensor in mm"""
        return (
            self.intrinsics[0][2],
            self.intrinsics[1][2],
        )

    @center.setter
    def center(self, value):
        self.init()
        self.intrinsics[0][2] = value[0]
        self.intrinsics[1][2] = value[1]

    @property
    def translation(self):
        """translation in mm"""
        return tuple(
            self.extrinsics[0][3],
            self.extrinsics[1][3],
            self.extrinsics[2][3],
        )

    @translation.setter
    def translation(self, value):
        self.init()
        self.extrinsics[0][3] = value[0]
        self.extrinsics[1][3] = value[1]
        self.extrinsics[2][3] = value[2]

    @property
    def rotation(self):
        """get rotation matrix"""
        return self.extrinsics[:3, :3]

    @rotation.setter
    def rotation(self, value):
        self.extrinsics[:3, :3] = value

    @property
    def matrix(self):
        return self.extrinsics.tolist()

    def structure(self):
        # extrinsics - 4x4 homogenous, uniform matrix, translation distance in meters
        # intrinsics - focal length xy, aperture xy & offset xy in mm
        # sensor size in mm
        return (
            ((4, 4), DataType.FLOAT32),  # COLUMN MAJOR IN M
            ((3, 3), DataType.FLOAT32),  # PINHOLE CAMERA FORMAT IN MM
            ((2,), DataType.FLOAT32),  # SENSOR SIZE IN MM
        )


class Skeleton(Asset):
    """
    N number of joints
    Stores joint names (128 characters)
    [128, N]
    Rest pose, 16 element transformation matrix tensor
    [T1, T2, ..., T16, N]
    Parent index hierarchy:
    [I, N]
    """

    def __init__(
        self,
        name=None,
        context=None,
        uri=URI(),
        io=None,
        licenses=None,
        dependencies=None,
        tensors=None,
    ):
        """Initialize the asset."""
        super(Skeleton, self).__init__(
            uri=uri,
            name=name,
            context=context,
            io=io,
            licenses=licenses,
            dependencies=dependencies,
            tensors=tensors,
        )

    def structure(self):
        return (
            ((0, 4, 4), DataType.FLOAT32),
            ((0,), DataType.LABEL),
            ((0,), DataType.INT32),
        )


class Pose(Asset):
    """
    N number of joints
    16 element transform matrix tensor
    Stores delta to skeleton
    [T1, T2, ..., T16, N]
    Holds reference to skeleton
    """

    def __init__(
        self,
        name=None,
        context=None,
        uri=URI(),
        io=None,
        licenses=None,
        skeleton=None,
        tensors=None,
    ):
        """Initialize the Values asset."""
        super(Pose, self).__init__(
            uri=uri,
            name=name,
            context=context,
            io=io,
            licenses=licenses,
            tensors=tensors,
        )
        self.add_property("skeleton", Skeleton, skeleton, member=False, direction=IN)

    def __len__(self):
        return self.tensors[0].shape[0]

    def structure(self):
        return ((0, 4, 4), DataType.FLOAT32)


class Poses(Asset):

    def __init__(
        self,
        name=None,
        context=None,
        uri=URI(),
        io=None,
        licenses=None,
        skeleton=None,
        tensors=None,
    ):
        """Initialize the Values asset."""
        super(Poses, self).__init__(
            uri=uri,
            name=name,
            context=context,
            io=io,
            licenses=licenses,
            tensors=tensors,
            skeleton=skeleton,
        )

    def __len__(self):
        return self.tensors[0].shape[0]

    def structure(self):
        return ((0, 0, 4, 4), DataType.FLOAT32)


class Animation(Poses):
    """
    Animation is a set of poses with a framerate
    """

    def __init__(
        self,
        name=None,
        context=None,
        uri=URI(),
        io=None,
        licenses=None,
        skeleton=None,
        tensors=None,
        frame_rate=None,
    ):
        """Initialize the Image asset."""
        super(Animation, self).__init__(
            uri=uri,
            name=name,
            context=context,
            io=io,
            licenses=licenses,
            tensors=tensors,
            skeleton=skeleton,
        )
        self.add_property("frame_rate", float, frame_rate)


class Transform(Asset):
    """
    A bog standard named locator
    """

    def __init__(
        self,
        name=None,
        context=None,
        uri=URI(),
        io=None,
        licenses=None,
        dependencies=None,
        tensors=None,
    ):
        """Initialize the asset."""
        super(Transform, self).__init__(
            uri=uri,
            name=name,
            context=context,
            io=io,
            licenses=licenses,
            dependencies=dependencies,
            tensors=tensors,
        )

    @property
    def translation(self):
        """translation in mm"""
        return tuple(
            self.tensors[0][0][3],
            self.tensors[0][1][3],
            self.tensors[0][2][3],
        )

    @translation.setter
    def translation(self, value):
        self.init()
        self.tensors[0][0][3] = value[0]
        self.tensors[0][1][3] = value[1]
        self.tensors[0][2][3] = value[2]

    @property
    def rotation(self):
        """get rotation matrix"""
        return self.tensors[0][:3, :3]

    @rotation.setter
    def rotation(self, value):
        self.tensors[0][:3, :3] = value

    @property
    def matrix(self):
        return self.tensors[0].tolist()

    def structure(self):
        # extrinsics - 4x4 homogenous, uniform matrix, translation distance in meters
        return (((4, 4), DataType.FLOAT32),)  # COLUMN MAJOR IN M


class Cloud(Asset):
    # TODO: define a point cloud type
    pass
