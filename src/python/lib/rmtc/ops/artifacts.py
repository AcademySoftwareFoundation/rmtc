# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
The artifacts we track through the system.

Note IXxxx classes denote abstract markers, in general
we don't permit multiple inheritance unless it's a IXxxx class
These classes don't hold member variables and don't have an __init__ or __del__
"""

import enum

from typing import Any, Optional
from abc import ABC, abstractmethod

from rmtc.track import entities

from rmtc.ops.process import Packager
from rmtc.ops.tensor import Array, Tensor
from rmtc.ops.io import IO
from rmtc.system.objects import IN, OUT
from rmtc.system import URI, RMTCException, Device, Type
from rmtc.system.containers import (
    Table,
    Order,
    RowMajorIterator,
    ColMajorIterator,
    RowTableIterator,
)


def _check_io(artifact, uri, io=None):
    if io is None:
        io = artifact.io
    if io is not None:
        if not io.is_artifact_supported(artifact):
            raise RMTCException(
                f"Can't set IO on {artifact} as isn't supported by IO {io} "
            )
        if not io.is_uri_supported(uri):
            raise RMTCException(
                f"Can't set URI on {artifact} as IO {io} does not support {uri}"
            )


class Runner(entities.Entity):
    """
    Class to run a model - responsible for taking the standard
    datatypes and converting into the model format and back
    """

    def __call__(self, model, inputs, training=False):
        return self.run(model, inputs)

    @abstractmethod
    def run(self, model, inputs):
        """
        Override this for a custom call
        """
        return model.run(inputs)

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Runner"


class Artifact(ABC):
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

    Aggregation are created in conjuction with specific reader/writers - for example
    a folder dataset will use file based reader/writers.
    """

    @abstractmethod
    def get_uri(self):
        return None

    @abstractmethod
    def get_io(self):
        """Get the IO object for this artifact."""
        return None

    @abstractmethod
    def get_dependencies(self):
        """Return artifact environment"""
        return set()

    @abstractmethod
    def set_uri(self, uri, io):
        """
        Assign a new URI and related IO that reads from that IO
        """
        pass

    @abstractmethod
    def get_device(self):
        """Return the current device - not persistent"""
        return None

    @abstractmethod
    def init(self):
        """Create any internal data."""
        return False

    @abstractmethod
    def reset(self):
        """Reset the artifact to its initial state."""
        return False

    @abstractmethod
    def is_valid(self):
        """Check if artifact is valid"""
        return False

    @abstractmethod
    def move(self, device):
        """Move object to a different execution device."""
        pass

    @abstractmethod
    def is_ephemeral(self):
        """
        Does this entity never get saved
        """
        return False


class Weights(entities.Weights, Artifact, ABC):
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
    a combined value is device sensitive.

    We make no assumptions about what weights are - safetensors, pt files, etc.
    """

    def __init__(
        self,
        name=None,
        context=None,
        uri=URI(),
        version=None,
        io=None,
        model=None,
        licenses=None,
        metric=1.0,
        dependencies=None,
        devices=None,
    ):
        """Initialize the Weights artifact."""
        super(Weights, self).__init__(
            name=name,
            context=context,
            uri=uri,
            version=version,
            model=model,
            licenses=licenses,
            metric=metric,
            dependencies=dependencies,
        )
        self.add_property("io", IO, io, direction=IN)
        self.add_property("devices", [Device], devices)

    def is_ephemeral(self):
        return self.io is None

    def get_dependencies(self):
        return self.dependencies

    def get_io(self):
        return self.io

    def get_uri(self):
        return self.uri

    def set_uri(self, uri, io):
        _check_io(self, uri, io)
        self.uri = uri
        self.io = io

    def init(self):
        return True


class Checkpoint(entities.Checkpoint, Artifact, ABC):
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
        context=None,
        uri=URI(),
        version=None,
        io=None,
        licenses=None,
        dependencies=None,
        devices=None,
        name=None,
    ):
        """Initialize the Checkpoint artifact."""
        super(Checkpoint, self).__init__(
            uri=uri,
            version=version,
            context=context,
            model=model,
            licenses=licenses,
            dependencies=dependencies,
            name=name,
        )
        self.add_property("io", IO, io, direction=IN)
        self.add_property("devices", [Device], devices)

    def is_ephemeral(self):
        return self.io is None

    def get_dependencies(self):
        return self.dependencies

    def get_io(self):
        return self.io

    def get_uri(self):
        return self.uri

    def set_uri(self, uri, io):
        _check_io(self, uri, io)
        self.uri = uri
        self.io = io

    @abstractmethod
    def to_weights(self):
        """
        Convert the checkpoint in a weights file for execution.
        """
        pass

    def init(self):
        return True


class Pod(ABC):

    @property
    def value(self):
        return self.get()

    @value.setter
    def value(self, value):
        self.set(value)

    def __repr__(self):
        return str(self.value)

    @abstractmethod
    def set(self, value):
        pass

    @abstractmethod
    def get(self):
        pass


class Asset(entities.Asset, Artifact, ABC):
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
        context=None,
        uri=URI(),
        version=None,
        io=None,
        licenses=None,
        dependencies=None,
        tensors=None,
        devices=None,
    ):
        """Initialize the Asset artifact."""
        super(Asset, self).__init__(
            uri=uri,
            version=version,
            name=name,
            context=context,
            licenses=licenses,
            dependencies=dependencies,
        )
        # NOTE:assets don't own their IOs, these are provided by the containing dataset
        self.add_property("io", IO, io, direction=IN, member=False)
        self.add_property("devices", [Device], devices)
        self._tensors = tensors
        self._device = Device.INVALID

    def is_ephemeral(self):
        return self.io is None

    def get_dependencies(self):
        return []

    def process(self, process):
        """Execute a process on the tensor"""
        if process is not None:
            self.tensors = process.run(self._tensors)

    def init(self):
        """Construct a tensor using the tensor builder"""
        if self.tensors is not None:
            return True
        tensors = []
        for structure in self.structure():
            # HACK : need to have a minimum of 1 element otherwise tensor invalid
            shape = [element if element > 0 else 1 for element in structure[0]]
            data_type = structure[1]
            tensor = Tensor.create_array(shape=shape, data_type=data_type)
            tensors.append(tensor)
        self.tensors = tuple(tensors)
        return True

    def get_device(self):
        return self._device

    def move(self, device):
        self._device = device
        # TODO : move tensors to given device

    @property
    def tensors(self):
        """Get the tensor data associated with this asset."""
        return self._tensors

    @tensors.setter
    def tensors(self, value):
        """Set the tensor data for this asset."""
        if value is not None:
            self.check_tensors(value)
        self._tensors = value

    def reset(self):
        """Reset the asset to its initial state."""
        self._tensors = None

    def is_valid(self):
        return self._tensors is not None

    def check_tensors(self, tensors):
        if tensors is None:
            raise RMTCException("Tensor is invalid")
        structure = self.structure()
        if len(structure) != len(tensors):
            raise RMTCException(
                f"Tensor {tensors} is wrong length for {self.__class__.__name__}"
            )
        for x, y in zip(structure, tensors):
            if not isinstance(y, Array):
                raise RMTCException(f"Incoming tensor {y} not the RMTC tensor format")
            t = Tensor(y)
            shape, data_type = x
            if len(t.shape) != len(shape):
                raise RMTCException(f"Incoming tensor {t.shape} missing shape elements")
            if not t.is_data_type(data_type):
                raise RMTCException(
                    f"Incoming tensor {y} does not match the tensor datatype {data_type}"
                )
            for s1, s2 in zip(t.shape, shape):
                if s2 != 0:
                    if s1 != s2:
                        raise RMTCException(
                            f"Incoming tensor {t.shape} does not match shape {shape}"
                        )

    def get_io(self):
        return self.io

    def get_uri(self):
        return self.uri

    def set_uri(self, uri, io):
        _check_io(self, uri, io)
        self.uri = uri
        self.io = io

    @abstractmethod
    def structure(self):
        pass


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

    def __repr__(self):
        return self.name.upper()


class Model(entities.Model, Artifact, ABC):
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
        model_id=None,
        context=None,
        uri=None,
        version=None,
        input_names=None,
        input_types=None,
        input_packager=None,
        input_optionals=None,
        output_names=None,
        output_types=None,
        output_packager=None,
        io=None,
        licenses=None,
        ancestors=None,
        model_type=None,
        dependencies=None,
        trainable=None,
        devices=None,
        runner=None,
    ):
        """Initialize the Model artifact."""
        super(Model, self).__init__(
            name=name,
            model_id=model_id,
            context=context,
            uri=uri,
            version=version,
            licenses=licenses,
            input_names=input_names,
            input_types=input_types,
            output_names=output_names,
            output_types=output_types,
            ancestors=ancestors,
            dependencies=dependencies,
        )

        # set of optional flags
        self.add_property("input_optionals", [bool], input_optionals, direction=IN)

        # how to read/write the model
        self.add_property("io", IO, io, direction=IN)

        # valid devices
        self.add_property("devices", [Device], devices)

        # What type of model - hints the optimiser etc.
        self.add_property(
            "model_type",
            ModelType,
            model_type,
            default=ModelType.REGRESSION,
            direction=IN,
        )

        # Can this model be trained?
        self.add_property(
            "trainable",
            bool,
            trainable,
        )

        # way to run the model inference
        # this takes in data after input processoing
        # the result is ran through the output processors
        self.add_property(
            "runner",
            Runner,
            runner,
            direction=IN,
        )

        # take the post processed RMTC tensors and package for the
        # runner
        self.add_property("input_packager", Packager, input_packager, direction=IN)

        # take the result from the runner/run and convert back
        # into RMTC tensors
        self.add_property("output_packager", Packager, output_packager, direction=IN)

    def is_ephemeral(self):
        return self.io is None

    def get_dependencies(self):
        return self.dependencies

    def get_io(self):
        return self.io

    def get_uri(self):
        return self.uri

    def set_uri(self, uri, io):
        _check_io(self, uri, io)
        self.uri = uri
        self.io = io

    def init(self):
        return True

    def add_input(self, name, asset_type, optional=False):
        self.add_input_names([name])
        self.add_input_types([asset_type])
        self.add_input_optionals([optional])

    def add_output(self, name, asset_type):
        self.add_output_names([name])
        self.add_output_types([asset_type])

    def extract_inputs_outputs(self, assets: list[Asset]) -> tuple[list[Asset]]:
        """Given a linear list of assets extract input and outputs according to the types"""
        i = 0
        inputs = []
        for asset_type in self.input_types:
            asset = assets[i]
            if not asset_type.is_derived(asset):
                raise RMTCException(f"Asset {asset} does not match type {asset_type}")
            inputs.append(asset)
            i += 1
        outputs = []
        for asset_type in self.output_types:
            asset = assets[i]
            if not asset_type.is_derived(asset):
                raise RMTCException(f"Asset {asset} does not match type {asset_type}")
            outputs.append(asset)
            i += 1
        return (inputs, outputs)

    @abstractmethod
    def get_internal_model(self):
        return None

    @abstractmethod
    def set_internal_model(self, model):
        pass

    def is_valid(self):
        return self.get_internal_model() is not None

    def valid_inputs(self, assets: list[Asset]) -> bool:
        if not isinstance(assets, list):
            return False
        if len(assets) != len(self.input_types):
            return False
        for i, asset in enumerate(assets):
            if not issubclass(asset.__class__, self.input_types[i].type_class):
                return False
            if not asset.is_valid():
                return False
        return True

    def valid_outputs(self, assets: list[Asset]) -> bool:
        if not isinstance(assets, list):
            return False
        if len(assets) != len(self.output_types):
            return False
        for i, asset in enumerate(assets):
            if not issubclass(asset.__class__, self.output_types[i].type_class):
                return False
            if not asset.is_valid():
                return False
        return True

    def __call__(self, inputs):
        """
        This method wraps inference with a runner
        Validating both input and output
        """

        # check
        for batch in inputs:
            if not self.valid_inputs(batch):
                raise RMTCException(f"Inputs {inputs}, not valid for {self}")

        # execute
        if self.runner is not None:
            outputs = self.runner(self, inputs)
        else:
            outputs = self.run(inputs)

        # check
        for batch in outputs:
            if not self.valid_outputs(batch):
                raise RMTCException(f"Outputs {outputs}, not valid for {self}")

        return outputs

    @abstractmethod
    def run(
        self,
        inputs: list[list[Asset]],  # a batch
    ) -> list[list[Asset]]:
        """
        Run inference on the provided assets.

        Performs model inference on the input assets, typically converting
        them to tensors using the configured processor, running the model,
        and converting results back to assets.

        The call method is required to do the conversion.
        """
        pass

    @abstractmethod
    def create_weights(self, run=None, **kwargs):
        """
        Create a new weights object for this model.

        Factory method for creating weights objects that are compatible
        with this specific model instance. The created weights should
        have the appropriate structure and metadata for this model.
        """
        pass

    @abstractmethod
    def create_checkpoint(self, run=None, **kwargs):
        """
        Create a new checkpoint object for this model.

        Factory method for creating checkpoint objects that are compatible
        with this specific model instance. The created checkpoint should
        have the appropriate structure for storing complete model state.
        """
        pass

    def _adopt_result(self, result, run, name):
        """
        Link a weights/checkpoint to the run it came from and name it.
        """
        if run is not None:
            result.parent = run
        if name is None:
            result.name = result.default_name()
        return result

    @abstractmethod
    def load_weights(self, weights: Weights):
        """
        Load weights into the model.

        Loads the provided weights into the model, updating the model's
        parameters. The weights should be compatible with this model's
        architecture and parameter structure.
        """
        pass

    @abstractmethod
    def load_checkpoint(self, checkpoint: Checkpoint):
        """
        Load a checkpoint into the model.

        Loads the provided checkpoint into the model, restoring the complete
        model state including weights, optimizer state, and training metadata.
        This is typically used to resume training or restore a specific model state.
        """
        pass

    def to_input(
        self,
        inputs: list[list[tuple[Array]]],
        device: Optional[Device] = None,
    ) -> Any:

        # inputs =
        # [ #samples
        #     [ #elements
        #         ( #tensors
        #             ...
        #         )
        #     ]
        # ]
        # returns are arbitrary

        # use current model device
        if device is None:
            device = self.get_device()

        # inputs is a list of samples, each a list of asset elements
        for sample in inputs:
            if not self.valid_inputs(sample):
                raise RMTCException(f"Input invalid: {inputs}")

        # build samples structure with processed assets
        data = []
        for sample in inputs:
            element = []
            for asset in sample:
                element.append(asset.tensors)
            data.append(element)

        # package into model format
        if self.input_packager:
            data = self.input_packager.run(data, device=device)

        return data

    def to_output(
        self, outputs: list[list[tuple[Array]]], device: Optional[Device] = None
    ) -> Any:

        # outputs =
        # [ #samples
        #     [ #elements
        #         ( #tensors
        #             ...
        #         )
        #     ]
        # ]
        # returns are arbitrary

        # use current model device
        if device is None:
            device = self.get_device()

        # inputs is a list of samples, each a list of asset elements
        for sample in outputs:
            if not self.valid_outputs(sample):
                raise RMTCException(f"Output invalid: {outputs}")

        # build samples structure with processed assets
        data = []
        for sample in outputs:
            element = []
            for asset in sample:
                element.append(asset.tensors)
            data.append(element)

        # package into model format
        if self.output_packager is not None:
            data = self.output_packager.run(data, device=device)

        return data

    def from_output(
        self, data: Any, device: Optional[Device] = None
    ) -> list[list[tuple[Array]]]:

        # data is abitrary, returns
        # [ #samples
        #     [ #elements
        #         ( #tensors
        #             ...
        #         )
        #     ]
        # ]

        # use current model device
        if device is None:
            device = self.get_device()

        # process into RMTC format
        if self.output_packager is not None:
            data = self.output_packager.run_inverse(data, device=device)

        # process tensors into assets
        outputs = []
        for sample in data:
            elements = []
            for i, asset_type in enumerate(self.output_types):
                asset = asset_type()  # CONSTRUCTS THE TYPE RIGHT HERE
                asset.tensors = sample[i]
                elements.append(asset)
            outputs.append(elements)

        # check the output signature
        for sample in outputs:
            if not self.valid_outputs(sample):
                raise RMTCException(f"Output invalid: {outputs}")

        return outputs

    def create_inputs(self):
        """
        Construct an empty set of inputs
        Used for model tracing
        """
        row = []
        for input_type in self.input_types:
            asset = input_type()
            asset.init()
            row.append(asset)
        inputs = [row]
        return self.to_input(inputs)

    def create_outputs(self):
        """
        Construct an empty set of outputs
        Added for symmetry
        """
        row = []
        for output_type in self.output_types:
            asset = output_type()
            asset.init()
            row.append(asset)
        outputs = [row]
        return self.to_output(outputs)


class Dataset(entities.Dataset, Table, Artifact):
    """
    Dataset is a table where rows are always a list of assets - even if a dataset of datasets
    Aggregation can have multiple columns with optional names and asset types
    Aggregation columns are homogeneous in type, not enforced if column doesn't have a type
    """

    def __init__(
        self,
        name=None,
        context=None,
        uri=None,
        version=None,
        licenses=None,
        dependencies=None,
        io=None,
        columns=None,
        types=None,
        assets=None,
    ):
        """Initialize the artifact."""
        super(Dataset, self).__init__(
            name=name,
            context=context,
            uri=uri,
            version=version,
            licenses=licenses,
            dependencies=dependencies,
            assets=assets,
        )
        self.add_property("io", IO, io, direction=IN)
        self.add_property("columns", [str], columns, direction=OUT)
        self.add_property(
            "types",
            [Type],
            types,
            default=[Type(type_class=Asset)],
            direction=OUT,
        )

        # the rows
        self._rows = []
        if assets:
            self._rows = [[asset] for asset in assets]

        # lazy cache of member obj_ids - see add_row
        self._member_ids = None

        self._device = Device.INVALID

    def is_ephemeral(self):
        return self.io is None

    def get_column_name(self, key):
        if len(self.columns) > 0:
            return self.columns[key]
        return str(key)

    def get_dependencies(self):
        return self.dependencies

    def get_io(self):
        return self.io

    def get_uri(self):
        return self.uri

    def set_uri(self, uri, io):
        _check_io(self, uri, io)
        self.uri = uri
        self.io = io

    def get_device(self):
        return self._device

    def move(self, device):
        self._device = device
        super(Dataset, self).move(device)
        for row in self:
            for asset in row:
                asset.move(device)

    def __len__(self):
        return self.rows()

    def __iter__(self):
        return RowTableIterator(self._rows, labels=self.columns)

    def __getitem__(self, index):
        if isinstance(index, int):
            return self._rows[index]
        return super(Dataset, self).__getitem__(index)

    def is_typed(self):
        return len(self.types) > 0

    def valid_types(self, types):
        if len(types) != len(self.types):
            return False
        for a, b in zip(types, self.types):
            if not issubclass(b.type_class, a.type_class):
                return False
        return True

    def _init_types(self, assets):
        """Init types from a list of assets, datasets are required to be homogeneous"""
        self.types = [Type(type_class=asset.type_class) for asset in assets]

    def _init_columns(self, assets):
        """Init types from a list of assets, datasets are required to be homogeneous"""
        self.columns = [asset.type_class.__name__ for asset in assets]

    def empty(self):
        return self.rows() == 0

    def init(self):
        return True

    def reset(self):
        # reset rows
        self._rows = []

    def is_valid(self):
        """
        Dataset is valid if columns match length of initial row
        """
        if self.empty():
            return False
        if len(self.columns) != len(self[0]):
            return False
        return True

    def add_column(self, name, assets):
        if name in self.columns:
            raise RMTCException(f"Duplicate column name {name} in dataset {self}")
        self.add_columns([name])
        if len(self._rows) != 0:
            if len(assets) != len(self._rows):
                raise RMTCException(
                    f"Can't add column of size {len(assets)}, size does not match {self}"
                )
            for i, asset in enumerate(assets):
                self._rows[i].append(asset)
        else:
            for i, asset in enumerate(assets):
                self._rows.append([asset])

    def remove_column(self, name):
        pass

    def valid_column(self, column):
        pass

    def get_column(self, key):
        """Return a named or indexed column"""
        if len(self.columns) == 0:
            return [row[0] for row in self]
        if key in self.columns:
            index = self.columns.index(key)
            return [row[index] for row in self]
        return None

    def cols(self):
        return len(self.columns)

    def init_from_row(self, row):
        if self.cols() == 0:
            self._init_columns(row)
        if not self.is_typed():  # this is bound by the new cols
            self._init_types(row[: self.cols()])

    def fill_row(self, row: list[Asset]):

        # can't add empty rows
        if len(row) == 0:
            raise RMTCException(f"Empty row being added to {self}")

        # setup types and cols if not assigned
        self.init_from_row(row)

        # add row
        self.add_row(row[: self.cols()])

        # return sub columns
        return row[self.cols() :]

    def empty_row(self, row: list[Asset]):
        if len(row) == 0:
            return row
        self.remove_row(row[: self.cols()])
        return row[self.cols() :]

    def add_row(self, row):

        # Aggregation become immediately typed when first row added
        self.init_from_row(row)

        # then we validate subsequent rows from there on
        if not self.valid_row(row):
            raise RMTCException(f"Dataset '{self}' rows not valid")

        # add it
        self._rows.append(row)

        # add to assets
        if self._member_ids is None:
            self._member_ids = {asset.obj_id for asset in self.assets}
        new_assets = [asset for asset in row if asset.obj_id not in self._member_ids]
        if new_assets:
            self.add_assets(new_assets)
            self._member_ids.update(asset.obj_id for asset in new_assets)

        return True

    def remove_row(self, row: list[Asset]):
        self._rows.remove(row)
        self.remove_assets(row)
        self._member_ids = None
        return True

    def get_row(self, key):
        if key < len(self._rows):
            return self._rows[key]
        return None

    def valid_row(self, row: list[Asset]):

        # if we have columns - then compare
        if self.columns:
            if len(row) != self.cols():
                return False

        # if we have asset types - then compare
        if self.is_typed():
            if len(self.types) != len(row):
                return False
            for asset, asset_type in zip(row, self.types):
                if not asset_type.is_instance(asset):
                    return False

        return True

    def names(self):
        return self.columns

    def rows(self):
        return len(self._rows)


class AggregationIO(IO):
    """
    Default IO - pushes read/write down to member datasets
    """

    def get_scheme(self):
        return None

    def get_artifact_type(self):
        return Aggregation

    def is_uri_supported(self, uri):
        return True

    def read(self, uri, artifact, asset_manager):
        asset_manager.read(artifact.datasets)

    def write(self, uri, artifact, asset_manager):
        asset_manager.write(artifact.datasets)


class Aggregation(Dataset, Table, Artifact):
    """
    Aggregation of datasets
    """

    def __init__(
        self,
        datasets=None,
        name=None,
        order=Order.ROW,
        io=None,
    ):
        """Initialize the aggregation."""
        if io is None:
            io = AggregationIO()
        super(Aggregation, self).__init__(
            name=name,
            io=io,
        )
        if datasets is not None:
            self.add_datasets(datasets)
        self.add_property("order", Order, order)

    def __len__(self):
        count = 0
        if self.order == Order.ROW:
            for dataset in self.datasets:
                count += len(dataset)
        else:
            count = None
            for dataset in self.datasets:
                if count is None:
                    count = len(dataset)
                else:
                    count = min(count, len(dataset))
        return count or 0

    def __getitem__(self, index):
        if isinstance(index, int):
            row = []
            for dataset in self.datasets:
                row.extend(dataset[index])
            return row
        return super(Aggregation, self).__getitem__(index)

    def __iter__(self):
        """
        Create an iterator that flattens all the dataset elements
        and returns them as a single Nx2 dataset for iteration
        NOTE: aggregation views conceptually have no assets
        """
        dataset_iterators = []
        for dataset in self.datasets:
            dataset_iterators.append(dataset.__iter__())
        if self.order == Order.ROW:
            return RowMajorIterator(dataset_iterators)
        return ColMajorIterator(dataset_iterators)

    def duplicate(self, descendent=False):
        # NOTE: this prevents an infinite duplicate bug
        # by specifically duplicating it's members
        dupe = super(Aggregation, self).duplicate(descendent=False)
        dupe.datasets = [dataset.duplicate() for dataset in self.datasets]
        return dupe

    def cols(self):
        if len(self.datasets) == 0:
            return 0
        if self.order == Order.COLUMN:
            count = 0
            for dataset in self.datasets:
                count += dataset.cols()
            return count
        return self.datasets[0].cols()

    def names(self):
        if len(self.datasets) == 0:
            return []
        if self.order == Order.ROW:
            return self.datasets[0].names()
        names = []
        for dataset in self.datasets:
            names.extend(dataset.names())
        return names

    def rows(self):
        if len(self.datasets) == 0:
            return 0
        if self.order == Order.ROW:
            count = 0
            for dataset in self.datasets:
                count += dataset.rows()
            return count
        return self.datasets[0].rows()

    def get_column(self, key):
        for dataset in self.datasets:
            col = dataset.get_column(key)
            if col is not None:
                return col
        return None

    def get_row(self, key):
        for dataset in self.datasets:
            col = dataset.get_row(key)
            if col is not None:
                return col
        return None

    def get_licenses(self):
        """Find licenses"""
        licenses = []
        for dataset in self.datasets:
            licenses.extend(dataset.licenses)
        return licenses

    def init(self):
        """Defer setup"""
        for dataset in self.datasets:
            if not dataset.init():
                return False
        return True

    def reset(self):
        """Defer reset"""
        for dataset in self.datasets:
            dataset.reset()

    def is_valid(self):
        """Defer valid test"""
        if len(self.datasets) == 0:
            return False
        for dataset in self.datasets:
            if not dataset.is_valid():
                return False
        return True

    def get_dependencies(self):
        env = []
        for dataset in self.datasets:
            if env is None:
                env = dataset.get_dependencies()
            else:
                env.extend(dataset.get_dependencies())
        return env

    def move(self, device):
        super(Aggregation, self).move(device)
        for dataset in self.datasets:
            dataset.move(device)

    def fill_row(self, row):
        if len(row) == 0:
            return []
        if self.cols() != len(row):
            raise RMTCException(f"Row length {len(row)} doesn't match {self.cols()}")
        if self.order == Order.COLUMN:
            for dataset in self.datasets:
                row = dataset.fill_row(row)
            return row

        # add to last dataset by default
        return self.datasets[-1].fill_row(row)

    def init_from_row(self, row):
        # each dataset inits from its slice of the row - init_from_row
        # returns nothing, so the slice advances by the resulting cols
        for dataset in self.datasets:
            dataset.init_from_row(row)
            row = row[dataset.cols() :]

    def empty_row(self, row):
        if len(row) == 0:
            return []
        if self.cols() != len(row):
            raise RMTCException(f"Row length {len(row)} doesn't match {self.cols()}")
        if self.order == Order.COLUMN:
            start = 0
            end = 0
            for dataset in self.datasets:
                end = start + dataset.cols()
                dataset.remove_row(row[start:end])
                start += dataset.cols()
            return row[start:-1]

        # remove to last dataset by default - AMBIGIOUS
        return self.datasets[:-1].remove_row(row)

    def add_row(self, row):
        remaining = self.fill_row(row)
        return len(remaining) == 0

    def remove_row(self, row: list[Asset]):
        remaining = self.empty_row(row)
        return len(remaining) == 0


class Collection(Asset):
    """
    A homogenous asset array of assets - NOT A DATASET
    E.g. a multi layer EXR or image sequence
    """

    def __init__(
        self,
        asset_type=None,
        name=None,
        context=None,
        uri=URI(),
        version=None,
        io=None,
        licenses=None,
        dependencies=None,
    ):
        """Initialize the asset."""
        super(Collection, self).__init__(
            uri=uri,
            version=version,
            name=name,
            context=context,
            io=io,
            licenses=licenses,
            dependencies=dependencies,
        )
        self.add_property("asset_type", Type, asset_type)
        self._assets = []
        self._tensor_cache = None

    def __len__(self):
        return len(self._assets)

    def __getitem__(self, key):
        return self._assets[key]

    def __setitem__(self, key, value):
        if not self.asset_type.is_instance(value):
            raise RMTCException(f"Invalid {value}, not of type {self.asset_type}")
        self._tensor_cache = None
        self._assets[key] = value

    def append(self, value):
        if not self.asset_type.is_instance(value):
            raise RMTCException(f"Invalid {value}, not of type {self.asset_type}")
        self._tensor_cache = None
        self._assets.append(value)

    def remove(self, value):
        self._tensor_cache = None
        self._assets.remove(value)

    @property
    def tensors(self):
        # TODO : build a batch of the tensors and return
        # this builds the tensor output in batched 'columns'
        # image with tensor ((W,H,4),) becomes ((N,W,H,4),)
        # Use a tensor cache to avoid expensive re-compute
        if self._tensor_cache is not None:
            return self._tensor_cache
        raise NotImplementedError()

    @tensors.setter
    def tensors(self, value):
        # TODO : assign the tensors from the incoming batches
        # this is striped across the batches just like aggregation
        # and overrides the number of elements
        self._tensor_cache = None
        raise NotImplementedError()

    def structure(self):
        # TODO : build structure as a 'batch'
        # image ((W,H,4),) becomes ((N,W,H,4),)
        # camera ((4,4), (3,3), (2,)) becomes ((N,4,4), (N,3,3), (N,2))
        # note - that these structures may batch again
        # leading to ((B,N,W,H,4),) for video
        raise NotImplementedError()
