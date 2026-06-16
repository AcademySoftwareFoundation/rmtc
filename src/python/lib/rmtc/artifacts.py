# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
The artifacts we track through the system.

Note IXxxx classes denote abstract markers, in general
we don't permit multiple inheritance unless it's a IXxxx class
These classes don't hold member variables and don't have an __init__ or __del__
"""

from abc import ABC, abstractmethod
import enum

import rmtc.track
import rmtc.process
from rmtc.objects import IN
from rmtc.io import IO
from rmtc.system import URI, RMTCException, Context
from rmtc.containers import (
    ITable,
    IteratorIterator,
    PaddedTableIterator,
    StrideTableIterator,
    RowTableIterator,
)


class IArtifact(ABC):
    """
    Abstract interface for artifacts that can be read, written, and reset.

    All concrete artifact implementations must provide these fundamental operations.

    We don't model an EXR or a USD file - we manage asset tensors and defer how
    they are represented, read and written on disk via reader/writer classes.
    A reader/writer knows how to access and artifact URI and can have their
    own set of parameters.

    Artifacts in memory will hold a cache of the URI location once it's read,
    resetting the artifact will clear that cache. In general assets are only
    temporary - reading and resetting during the dataset access for training
    and writing post a call for inference.

    Datasets are created in conjuction with specific reader/writers - for example
    a folder dataset will use file based reader/writers.
    """

    @abstractmethod
    def read(self, asset_manager):
        """Read the artifact from its storage location."""
        return False

    @abstractmethod
    def write(self, asset_manager):
        """Write the artifact to its storage location."""
        return False

    @abstractmethod
    def reset(self):
        """Reset the artifact to its initial state."""
        return False

    @abstractmethod
    def is_valid(self):
        """Check if dataset is valid"""
        return False

    @abstractmethod
    def get_env(self):
        """Return artifact environment"""
        return set()

    def move(self, ctx):
        """Move object to a different execution context."""
        pass

    def get_context(self):
        """Return the current context - not persistent"""
        return Context.INVALID


class Weights(rmtc.track.Weights, IArtifact, ABC):
    """
    Model weights artifact with read/write capabilities.

    This must be subclassed - for example a TorchWeights file. Note that
    weights should not contain any optimizer information - that is specifically
    for checkpoints.

    We make the distinction to sightly reduce the size of the weights,
    it is a legal operation to convert a weights file to a checkpoint, but going
    the other direction may not result in a repeatable training as the optimizer
    data will be absent.

    Weights produced by runs will hold a singular metric rating - this can be
    a combined value is context sensitive.

    We make no assumptions about what weights are - safetensors, pt files, etc.
    """

    def __init__(
        self,
        name=None,
        project=None,
        uri=URI(),
        io=None,
        model=None,
        licenses=None,
        metric=1.0,
        env=None,
    ):
        """Initialize the Weights artifact."""
        super(Weights, self).__init__(
            name=name,
            project=project,
            uri=uri,
            model=model,
            licenses=licenses,
            metric=metric,
            env=env,
        )
        self.add_property("io", IO, io, direction=IN)

    def read(self, asset_manager):
        # TODO : Cycle is possible when IO is None
        asset_manager.read([self])

    def write(self, asset_manager):
        # TODO : Cycle is possible when IO is None
        asset_manager.read([self])

    def get_env(self):
        return self.env


class Checkpoint(rmtc.track.Checkpoint, IArtifact, ABC):
    """
    Model checkpoint artifact with read/write capabilities.

    This is a superset of the weights object - with optmizer information stored
    alongside the weights.

    Checkpoints can be converted to weights by stripping the optimizer information.
    If so the resulting weights is a derivation of the checkpoint.
    """

    def __init__(
        self,
        model=None,
        project=None,
        uri=URI(),
        io=None,
        licenses=None,
        env=None,
    ):
        """Initialize the Checkpoint artifact."""
        super(Checkpoint, self).__init__(
            uri=uri,
            project=project,
            model=model,
            licenses=licenses,
            env=env,
        )
        self.add_property("io", IO, io, direction=IN)

    @abstractmethod
    def to_weights(self):
        """
        Convert the checkpoint in a weights file for execution.
        """
        pass

    def read(self, asset_manager):
        asset_manager.read([self])

    def write(self, asset_manager):
        asset_manager.write([self])

    def get_env(self):
        return self.env


class ModelType(enum.IntEnum):
    """Model labels used for hints in training configuration"""

    INVALID = 0

    # supervised
    REGRESSION = 1  # predict continous values - linear, poly
    CLASSIFICATION = 2  # predict category - n class binning
    TRANSFORMATION = 3  # sequence prediction - LLMs

    # unsupervised
    CLUSTERING = 4  # cluster data - SVD, K-Means etc
    REDUCTION = 5  # dimensionality reduction - PCA, VAE
    ASSOCIATION = 6  # associative rule learning - Apriori, Eclat
    DETECTION = 7  # anomaly detection - AE, SVMs, rule forests

    def __str__(self):
        return self.name.upper()


class Model(rmtc.track.Model, IArtifact, ABC):
    """
    Abstract model artifact with conversion and I/O capabilities.

    This class represents a machine learning model that can be persisted,
    loaded, and used for inference. It includes type conversion capabilities
    through a process and weight/checkpoint management functionality.

    The model itself has an additional signature which is used to validate
    predictions.
    """

    def __init__(
        self,
        name=None,
        project=None,
        uri=None,
        asset_to_input=None,
        asset_to_output=None,
        io=None,
        licenses=None,
        input_type=None,
        output_type=None,
        ancestors=None,
        model_type=None,
        input_shape=None,
        output_shape=None,
        env=None,
    ):
        """Initialize the Model artifact."""
        super(Model, self).__init__(
            name=name,
            project=project,
            uri=uri,
            licenses=licenses,
            input_type=input_type,
            output_type=output_type,
            ancestors=ancestors,
            env=env,
        )
        self.add_property("input_shape", [int], input_shape, direction=IN)
        self.add_property("output_shape", [int], output_shape, direction=IN)
        self.add_property(
            "asset_to_input", rmtc.process.Process, asset_to_input, direction=IN
        )
        self.add_property(
            "asset_to_output", rmtc.process.Process, asset_to_output, direction=IN
        )
        self.add_property("io", IO, io, direction=IN)
        self.add_property(
            "model_type",
            ModelType,
            model_type,
            default=ModelType.REGRESSION,
            direction=IN,
        )

    def read(self, asset_manager):
        asset_manager.read([self])

    def write(self, asset_manager):
        asset_manager.write([self])

    def get_env(self):
        return self.env

    @abstractmethod
    def __call__(self, assets):
        """
        Run inference on the provided assets.

        Performs model inference on the input assets, typically converting
        them to tensors using the configured processor, running the model,
        and converting results back to assets.

        The call method is required to do the conversion.
        """
        pass

    @abstractmethod
    def create_weights(self, io):
        """
        Create a new weights object for this model.

        Factory method for creating weights objects that are compatible
        with this specific model instance. The created weights should
        have the appropriate structure and metadata for this model.
        """
        pass

    @abstractmethod
    def create_checkpoint(self, io):
        """
        Create a new checkpoint object for this model.

        Factory method for creating checkpoint objects that are compatible
        with this specific model instance. The created checkpoint should
        have the appropriate structure for storing complete model state.
        """
        pass

    @abstractmethod
    def load_weights(self, weights):
        """
        Load weights into the model.

        Loads the provided weights into the model, updating the model's
        parameters. The weights should be compatible with this model's
        architecture and parameter structure.
        """
        pass

    @abstractmethod
    def load_checkpoint(self, checkpoint):
        """
        Load a checkpoint into the model.

        Loads the provided checkpoint into the model, restoring the complete
        model state including weights, optimizer state, and training metadata.
        This is typically used to resume training or restore a specific model state.
        """
        pass

    def assets_to_input_tensors(self, assets):
        """
        Convert input assets to tensors for model processing.

        Validates that all assets match the expected input type, extracts
        their tensor representations, validates the tensor data, and applies
        the input processing pipeline.
        """
        if self.input_type is not None:
            for asset in assets:
                expected_type = self.input_type.type_class
                if not isinstance(asset, self.input_type.type_class):
                    raise RMTCException(
                        f"Input invalid: {asset.__class__.__name__}, {expected_type}"
                    )
        tensors = [asset.tensor for asset in assets]
        return self.asset_to_input.run(tensors)

    def assets_to_output_tensors(self, assets):
        """
        Convert output assets to tensors.

        Validates that all assets match the expected output type, extracts
        their tensor representations, validates the tensor data, and applies
        the output processing pipeline.
        """
        if self.output_type is not None:
            for asset in assets:
                if not isinstance(asset, self.output_type.type_class):
                    raise RMTCException(
                        f"Output invalid: {asset.__class__.__name__}, {self.output_type}"
                    )
        tensors = [asset.tensor for asset in assets]
        return self.asset_to_output.run(tensors)

    def output_tensors_to_assets(self, tensors):
        """
        Convert output tensors back to asset objects.

        Takes tensor data (typically from model output), validates it,
        applies the inverse output processing pipeline, and creates
        asset objects of the configured output type.
        """
        assets = []
        tensors = self.asset_to_output.run_inverse(tensors)
        for tensor in tensors:
            asset = self.output_type()
            asset.tensor = tensor
            assets.append(asset)
        return assets

    def input_tensors_to_assets(self, tensors):
        """
        Convert input tensors back to asset objects.

        Takes tensor data, validates it, applies the inverse input processing
        pipeline, and creates asset objects of the configured input type.
        This is useful for reconstructing original assets from processed tensors.
        """
        assets = []
        tensors = self.asset_to_input.run_inverse(tensors)
        for tensor in tensors:
            asset = self.input_type()
            asset.tensor = tensor
            assets.append(asset)
        return assets


class Dataset(rmtc.track.Dataset, ITable, ABC):

    def __len__(self):
        return self.rows()

    def cols(self):
        """Always 2 columns for any dataset"""
        return 2


class Repository(Dataset, IArtifact):
    """
    URI based dataset artifact with an IO pairing.
    The internal asset list is volatile and not recorded.
    The tracked assets dataset property is not used.
    """

    def __init__(
        self,
        name=None,
        project=None,
        uri=URI(),
        io=None,
        licenses=None,
        env=None,
    ):
        """Initialize the artifact."""
        super(Repository, self).__init__(
            name=name,
            project=project,
            uri=uri,
            licenses=licenses,
            env=env,
        )
        self.add_property("io", IO, io, direction=IN)
        self._rows = []

    def get_env(self):
        return self.env

    def read(self, asset_manager):
        asset_manager.read([self])

    def write(self, asset_manager):
        asset_manager.write([self])

    def __iter__(self):
        return RowTableIterator(self._rows)

    def add_row(self, row):
        if len(row) != self.cols():
            raise RMTCException(f"Dataset {self} rows must be 2 columns")
        self._rows.append(row)

    def remove_row(self, row):
        self._rows.remove(row)

    def rows(self):
        return len(self._rows)

    def empty(self):
        return len(self._rows) == 0

    def reset(self):
        self._rows = []

    def is_valid(self):
        return True


class Aggregation(Dataset, IArtifact):
    """
    A class to manage datasets of datasets.
    """

    def __init__(
        self,
        name=None,
        project=None,
        datasets=None,
    ):
        """Initialize the aggregation."""
        super(Aggregation, self).__init__(name=name, project=project, datasets=datasets)

    def __iter__(self):
        """
        Create an iterator that flattens all the dataset elements
        and returns them as a single Nx2 dataset for iteration
        NOTE: aggregation views conceptually have no assets
        """
        dataset_iterators = []
        for dataset in self.datasets:
            dataset_iterators.append(dataset.__iter__())
        return IteratorIterator(dataset_iterators)

    def _flatten(self, datasets):
        rows = []
        for dataset in datasets:
            for row in dataset:
                rows.append(row)
            rows.extend(self._flatten(dataset))
        return rows

    def add_row(self, row):
        raise RMTCException(f"Can't add rows to aggregation {self}")

    def remove_row(self, row):
        raise RMTCException(f"Can't remove rows from aggregation {self}")

    def rows(self):
        return len(self._flatten(self.datasets))

    def empty(self):
        return len(self.datasets) == 0

    def get_licenses(self):
        """Find licenses"""
        licenses = []
        for dataset in self.datasets:
            licenses.extend(dataset.licenses)
        return licenses

    def read(self, asset_manager):
        """Defer read"""
        asset_manager.read(self.datasets)

    def write(self, asset_manager):
        """Defer write"""
        asset_manager.write(self.datasets)

    def reset(self):
        """Defer reset"""
        for dataset in self.datasets:
            dataset.reset()

    def is_valid(self):
        """Defer valid test"""
        for dataset in self.datasets:
            if not dataset.is_valid():
                return False
        return True

    def get_env(self):
        env = None
        for dataset in self.datasets:
            if env is None:
                env = dataset.get_env()
            else:
                env.merge(dataset.get_env())
        return env


class AssetDataset(Dataset, IArtifact, ABC):
    """
    A convienience asset based dataset base class

    It implementes IArtifact as it's items are artifacts and so defers
    all the artifact calls back down to those items.

    Note that URI and licenses are specified on a per item basis, not on the dataset.
    """

    def __init__(self, name=None, project=None, assets=None):
        """Initialize"""
        super(AssetDataset, self).__init__(name=name, project=project, assets=assets)

    def empty(self):
        return len(self.assets) == 0

    def get_licenses(self):
        """Find licenses"""
        licenses = []
        for asset in self.assets:
            licenses.extend(asset.licenses)
        return licenses

    def read(self, asset_manager):
        """Defer read"""
        asset_manager.read(self.assets)

    def write(self, asset_manager):
        """Defer write"""
        asset_manager.write(self.assets)

    def reset(self):
        """Defer reset"""
        for asset in self.assets:
            asset.reset()

    def get_env(self):
        env = set()
        for asset in self.assets:
            env.update(asset.get_env())
        return env

    def is_valid(self):
        """Defer valid test"""
        for asset in self.assets:
            if not asset.is_valid():
                return False
        return True


class Collection(AssetDataset, IArtifact):
    """
    A concrete dataset that wraps the trackable dataset asset array and interprets it
    as an uncorrelated list: [[0,None],[1,None],[2,None]...[N,None]]

    All assets from a row are added to the collection directly, regardless of source
    or destination - they are not organised in a meaningful way.

    This dataset will not be suitable for training with, but can be used for inference
    """

    def __init__(self, name=None, project=None, assets=None):
        """Initialize"""
        super(Collection, self).__init__(name=name, project=project, assets=assets)

    def __iter__(self):
        return PaddedTableIterator(self.assets, 1)

    def add_row(self, row):
        self.add_assets(row)

    def remove_row(self, row):
        self.remove_assets(row)

    def rows(self):
        return len(self.assets)


class Correlation(AssetDataset, IArtifact):
    """
    A concrete dataset that wraps the trackable dataset asset array and interprets it
    as an interlaced correlation: [[0,1],[2,3]...[n-1,n]].
    """

    def __init__(self, name=None, project=None, src=None, dst=None):
        """Initialize"""
        if len(src) != len(dst):
            raise RMTCException(
                f"Correlations must be same size: {len(src)} vs {len(dst)}"
            )
        assets = [item for pair in zip(src, dst) for item in pair]
        super(Correlation, self).__init__(name=name, project=project, assets=assets)

    def __iter__(self):
        return StrideTableIterator(self.assets, 2)

    def add_row(self, row):
        if len(row) != 2:
            raise RMTCException(f"Correlations must be 2 elements, not {len(row)}")
        self.add_assets(row)

    def remove_row(self, row):
        if len(row) != 2:
            raise RMTCException(f"Correlations must be 2 elements, not {len(row)}")
        self.remove_assets(row)

    def rows(self):
        return len(self.assets) // 2


class Asset(rmtc.track.Asset, IArtifact, ABC):
    """
    Abstract asset artifact with tensor data and I/O capabilities.

    This represents a model inferable tensor in standard formats.

    VFX pipelines have expecations around assets like images & meshes.
    This class provides a known tensor represention for each type.

    This standard representation is then converted to the model tensor format
    for prediction. The result converted back out with the processes
    allocated to that model.

    They store tensors - but not persistently, these are drawn from the URI
    by reader/writer on demand and discarded.
    """

    def __init__(
        self,
        name=None,
        project=None,
        uri=URI(),
        io=None,
        licenses=None,
        env=None,
    ):
        """Initialize the Asset artifact."""
        super(Asset, self).__init__(
            uri=uri,
            name=name,
            project=project,
            licenses=licenses,
            env=env,
        )
        self.add_property("io", IO, io, direction=IN)

    def read(self, asset_manager):
        asset_manager.read([self])

    def write(self, asset_manager):
        asset_manager.write([self])

    def get_env(self):
        return self.env

    def process(self, process):
        """Execute a process on the tensor"""
        if process is not None:
            self._tensor = process.run([self._tensor])[0]

    @property
    def tensor(self):
        """
        Get the tensor data associated with this asset.

        Returns the tensor representation of the asset data. This is the
        primary data payload of the asset, typically used for computations
        and model operations.
        """
        return self._tensor

    @tensor.setter
    def tensor(self, value):
        """
        Set the tensor data for this asset.

        Updates the tensor representation of the asset data. This allows
        the asset to store computational results or loaded data for
        further processing.
        """
        self._tensor = value

    def reset(self):
        """
        Reset the asset to its initial state.

        Clears the tensor data, returning the asset to a clean state.
        This is useful for reusing asset instances or clearing cached
        data without affecting the asset's metadata or configuration.
        """
        self._tensor = None

    def is_valid(self):
        return self.tensor is not None


class Image(Asset):
    """
    Image asset representing RGBA tensor data.

    Images are stored as RGBA tensors with shape (H,W,4) containing 32-bit
    floating point values. This class provides specialized functionality for
    image data including dimension access methods and inherits all persistence
    and tensor management capabilities from the Asset base class.

    The tensor data represents image pixels in RGBA format where:
    - H (height): Number of pixel rows
    - W (width): Number of pixel columns
    - 4 channels: Red, Green, Blue, Alpha values
    - Values are 32-bit floating point, typically in range [0.0, 1.0]
    """

    def __init__(
        self,
        name=None,
        project=None,
        uri=URI(),
        io=None,
        licenses=None,
        env=None,
    ):
        """Initialize the Image asset."""
        super(Image, self).__init__(
            name=name,
            project=project,
            uri=uri,
            io=io,
            licenses=licenses,
            env=env,
        )

    @property
    def width(self):
        """Get the width of the image in pixels."""
        return self.tensor.shape[1]

    @property
    def height(self):
        """Get the height of the image in pixels."""
        return self.tensor.shape[0]

    @property
    def channels(self):
        """Get the channel count - generally 4 for RGBA"""
        return self.tensor.shape[2]


class Mesh(Asset):
    """
    Mesh asset representing 3D geometry data compatible with Vulkan.

    Mesh data is stored as a structured tensor containing vertex and face
    information in a format optimized for Vulkan graphics API compatibility.
    The tensor structure includes vertex data with positions, normals, and
    UV coordinates, along with face indices for triangle definitions.

    The tensor data structure:
    - vertices: vertex/normal/uv representation with shape (N,8) where:
      - N is the number of vertices
      - 8 components per vertex: [x,y,z, nx,ny,nz, u,v]
        - x,y,z: vertex position coordinates
        - nx,ny,nz: normal vector components
        - u,v: texture UV coordinates
    - faces: triangle face indices with shape (M,3) where:
      - M is the number of triangular faces
      - 3 indices per face referencing vertices
    """

    def __init__(
        self,
        name=None,
        project=None,
        uri=URI(),
        io=None,
        licenses=None,
        env=None,
    ):
        """Initialize the Mesh asset."""
        super(Mesh, self).__init__(
            uri=uri,
            name=name,
            project=project,
            io=io,
            licenses=licenses,
            env=env,
        )

    @property
    def vertices(self):
        """
        Get the number of vertices in the mesh.

        Returns the count of vertices by accessing the first dimension of
        the tensor shape, which corresponds to the number of vertex entries
        in the (N,8) vertex data structure.
        """
        return self.tensor.shape[0]

    @property
    def faces(self):
        """
        Get the number of faces in the mesh.

        Returns the count of triangular faces by accessing the second dimension
        of the tensor shape, which corresponds to the number of face entries
        in the face index structure.
        """
        return self.tensor.shape[1]


class Values(Asset):
    """
    Values asset representing a flat list of numerical data.
    """

    def __init__(
        self,
        name=None,
        project=None,
        uri=URI(),
        io=None,
        licenses=None,
        env=None,
    ):
        """Initialize the Values asset."""
        super(Values, self).__init__(
            name=name,
            project=project,
            uri=uri,
            io=io,
            licenses=licenses,
            env=env,
        )

    def __len__(self):
        """Get the number of values in the asset."""
        return self.tensor.shape[0]


class Labels(Asset):
    """
    Labels asset representing a list of string data.

    Used for labelling etc.

    This class is not implemented
    """

    def __init__(
        self,
        name=None,
        project=None,
        uri=URI(),
        io=None,
        licenses=None,
        env=None,
    ):
        """Initialize the Values asset."""
        super(Labels, self).__init__(
            uri=uri,
            name=name,
            project=project,
            io=io,
            licenses=licenses,
            env=env,
        )

    def __len__(self):
        """Get the number of labels in the asset."""
        return self.tensor.shape[0]

    @property
    def labels(self):
        return ["".join(row) for row in self.tensor]

    def __str__(self):
        return self.labels
