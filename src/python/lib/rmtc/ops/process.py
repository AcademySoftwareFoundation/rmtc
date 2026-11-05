# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from abc import ABC, abstractmethod
from typing import Any, Optional
from collections.abc import Sequence

from rmtc.track.store import Entity
from rmtc.ops.tensor import Array
from rmtc.system.objects import IN
from rmtc.system import Device, RMTCException

# Packager is used to transform RMTC data to arbitrary model formats,
# it's a chainable process that has no constraints (to match PyTorch).
# It's an attempt to avoid per-model specific wrappers.

# Process is used to specifically transform the tensors into other
# tensors - it is formalised. The structure does not change.


class Packager(Entity, ABC):
    """
    Package an RMTC data block into a model specific format for passing directly
    to the model. This is to encapsulate and formalise the RMTC data block format
    seperately from the model formats. It differs to a Processor which specifically
    supports chained tensor transformations. Splitting tensor operations from model
    marshalling allows more flexibility for re-use.

    This gets converted into whatever is specifically needed - all return formats
    are legal is directly injected into the model

    The aim is prevent the need for creating per-model wrappers by hopefully creating
    a set of common packaging classes, it's not perfect as systems like PyTorch
    do not formalise model inputs and outputs.

    For really custom situations - the end user can always provide their own derivation.

    For example a 2 sample batch, for a 2 argument model, with a tuple of tensors, RMTC
    represents it as a structured data block:

    [ #sample 1
        ( # image input
            [H,W,4] # single RBGA tensor
        ),
        ( # camera input
            [P,3], # camera position
            [V,3], # camera direction
        )
    ]
    [ #sample 2
        ( # image input
            [H,W,4] # single RBGA tensor
        ),
        ( # camera input
            [P,3], # camera position
            [V,3], # camera direction
        )
    ]

    A packager could potentially convert to multiple kinds of equivalent data:

    A batched list of tensors:
    [
        [2,4,H,W], # single RBGA tensor
        [2,P,3], # camera position
        [2,V,3], # camera direction
    ]

    A dict of batched tensors:
    {
        "image": [2,4,H,W],
        "cam_pos": [2,P,3],
        "cam_dir": [2,V,3],
    }

    A single stacked tensor (with padding):
    [2,4,H,W,P',3,V',3]

    Entirely non-tensor:
    tuple(ImageType(), CameraType())
    """

    def is_valid_input(self, data: Any) -> bool:
        """Check input is OK to run - default is list[list[tuple[Array]]]"""
        if not isinstance(data, list):
            return False
        if len(data) > 0:
            sample = data[0]
            if not isinstance(sample, list):
                return False
            if len(sample) > 0:
                element = sample[0]
                if not isinstance(element, tuple):
                    return False
                if len(element) > 0:
                    tensor = element[0]
                    if not isinstance(tensor, Array):
                        return False
        return True

    def is_valid_output(self, data: Any) -> bool:
        return True

    @abstractmethod
    def run(
        self, data: list[list[tuple[Array]]], device: Optional[Device] = None
    ) -> Any:
        pass

    @abstractmethod
    def run_inverse(
        self, data: Any, device: Optional[Device] = None
    ) -> list[list[tuple[Array]]]:
        pass

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Packager"


class PackagerStack(Packager):

    def __init__(self, stack=None):
        super(PackagerStack, self).__init__()
        self.add_property("stack", [Packager], stack, direction=IN)

    def run(
        self, data: list[list[tuple[Array]]], device: Optional[Device] = None
    ) -> Any:
        for entry in self.stack:
            if not entry.is_valid_input(data):
                raise RMTCException(f"Data invalid for input to packager {entry}")
            data = entry.run(data, device)
            if not entry.is_valid_output(data):
                raise RMTCException(f"Data invalid as output from packager {entry}")
        return data

    def run_inverse(
        self, data: Any, device: Optional[Device] = None
    ) -> list[list[tuple[Array]]]:
        for entry in reversed(self.stack):
            if not entry.is_valid_output(data):
                raise RMTCException(
                    f"Data invalid for input to inverted packager {entry}"
                )
            data = entry.run_inverse(data, device)
            if not entry.is_valid_input(data):
                raise RMTCException(
                    f"Data invalid as output from inverted packager {entry}"
                )
        return data


class ProcessPackager(Packager):
    """
    Packager that runs a process on the input before packaging
    Processes are index aligned with the assets in the sample
    """

    def __init__(
        self,
        processors=None,
        packager=None,
    ):
        super(ProcessPackager, self).__init__()
        self.add_property("processors", [Process], processors, direction=IN)
        self.add_property("packager", Packager, packager, direction=IN)

    def run(
        self, data: list[list[tuple[Array]]], device: Optional[Device] = None
    ) -> Any:
        """
        Run all processes in the stack sequentially.

        Executes each process in the stack in order, passing the output
        of each process as input to the next. Each process is validated
        before execution to ensure data integrity throughout the pipeline.
        """

        # process
        if self.processors is not None:
            processed = []
            for sample in data:
                element = []
                for i, tensors in enumerate(sample):
                    if i >= len(self.processors):
                        pass
                    elif self.processors[i] is None:
                        pass
                    else:
                        tensors = self.processors[i].run(tensors)
                    element.append(tensors)
                processed.append(element)
            data = processed

        # package
        if self.packager is not None:
            data = self.packager.run(data, device)

        return data

    def run_inverse(
        self,
        data: Any,
        device: Optional[Device] = None,
    ) -> list[list[tuple[Array]]]:
        """
        Run all processes in the stack in reverse order with inverse operations.

        Executes each process in the stack in reverse order, calling the
        run_inverse method on each. This effectively undoes the forward
        pipeline by applying inverse transformations in the opposite sequence.
        """

        # unpackage
        if self.packager is not None:
            data = self.packager.run_inverse(data, device)

        # unprocess
        if self.processors is not None:
            processed = []
            for sample in data:
                element = []
                for i, tensors in enumerate(sample):
                    if i >= len(self.processors):
                        pass
                    elif self.processors[i] is None:
                        pass
                    else:
                        tensors = self.processors[i].run_inverse(tensors)
                    element.append(tensors)
                processed.append(element)
            data = processed

        return data


class Process(Entity, ABC):
    """
    Abstract base class for tensor processing operations.

    As part of the model we have processes - these are smaller bidirectional
    operations that act on lists of tensors.

    Individual assets return a tuple of tensors - processors are given the tuple

    Process implementations need to support both forward and inverse
    operations to support the 3 main conversion requirements.

    The Process class is designed to be composable, allowing multiple
    processes to be chained together in ProcessStack instances or
    inverted using ProcessInverter.

    All concrete Process implementations must provide both forward (run)
    and inverse (run_inverse) operations, along with appropriate validation
    methods for each direction that protect against poor tensor formats.
    """

    def is_valid_input(self, tensors: tuple[Array]) -> bool:
        """Check input is OK to run"""
        if not isinstance(tensors, Sequence):
            return False
        if len(tensors) == 0:
            return False
        if not isinstance(tensors[0], Array):
            return False
        return True

    def is_valid_output(self, tensors: tuple[Array]) -> bool:
        """Check output is OK, mirrors input by default"""
        return self.is_valid_input(tensors)

    def __call__(self, tensors: tuple[Array]) -> tuple[Array]:
        return self.run(tensors)

    def is_reversible(self):
        """
        Is this process reversible
        """
        return True

    @abstractmethod
    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        """
        Run the forward process on tensors.

        Applies the forward transformation to the input tensors. This is
        the main processing method that implements the core functionality
        of the process. The specific transformation depends on the concrete
        implementation.
        """
        return tensors

    @abstractmethod
    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        """
        Run the inverse process on tensors.

        Applies the inverse transformation to the input tensors, effectively
        reversing the forward operation. This enables bidirectional data
        flow and reconstruction of original data from processed results.
        """
        return tensors

    def invert(self):
        return ProcessInverter(self)

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Process"


class ProcessInverter(Process):

    def __init__(self, process):
        super(ProcessInverter, self).__init__()
        self.add_property("process", Process, process, direction=IN)

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        return self.process.run_inverse(tensors)

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        return self.process.run(tensors)


class ProcessBypass(Process):

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        return tensors

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        return tensors


class ProcessTensor(Process):

    def __init__(self, tensor=0, process=None):
        """Initialize the ProcessTensor with a process to invert."""
        super(ProcessTensor, self).__init__()
        self.add_property("tensor", int, tensor, direction=IN)
        self.add_property("process", Process, process, direction=IN)

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        """Run the processor against a sub element"""
        out = []
        for tensor in tensors:
            data = [tensor[self.tensor]]
            processed = self.process.run(data)
            out.append(
                [
                    processed if i == self.tensor else item
                    for i, item in enumerate(tensor)
                ]
            )
        return out

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        """Run the inverse processor against a sub element"""
        out = []
        for tensor in tensors:
            processed = self.process.run_inverse([tensor[self.tensor]])
            out.append(
                [
                    processed if i == self.tensor else item
                    for i, item in enumerate(tensor)
                ]
            )
        return out


class ProcessStack(Process):
    """
    Chains multiple processes together in sequence.

    This class executes a stack of processes in order for forward operations
    and in reverse order for inverse operations. Each process in the stack
    receives the output of the previous process as its input, creating a
    processing pipeline.

    For forward operations (run), processes are executed in the order they
    appear in the stack. For inverse operations (run_inverse), processes
    are executed in reverse order with their inverse methods called.
    """

    def __init__(self, stack=None):
        """Initialize the ProcessStack with a list of processes."""
        super(ProcessStack, self).__init__()
        self.add_property("stack", [Process], stack, direction=IN)

    def run(self, tensors: tuple[Array]) -> tuple[Array]:
        """
        Run all processes in the stack sequentially.

        Executes each process in the stack in order, passing the output
        of each process as input to the next. Each process is validated
        before execution to ensure data integrity throughout the pipeline.
        """
        for entry in self.stack:
            if not self.is_valid_input(tensors):
                raise RMTCException(f"Invalid tensors for input to process {entry}")
            tensors = entry.run(tensors)
            if not self.is_valid_output(tensors):
                raise RMTCException(f"Invalid tensors as output from process {entry}")
        return tensors

    def run_inverse(self, tensors: tuple[Array]) -> tuple[Array]:
        """
        Run all processes in the stack in reverse order with inverse operations.

        Executes each process in the stack in reverse order, calling the
        run_inverse method on each. This effectively undoes the forward
        pipeline by applying inverse transformations in the opposite sequence.
        """
        for entry in reversed(self.stack):
            if not self.is_valid_output(tensors):
                raise RMTCException(
                    f"Invalid tensors for input to inverted process {entry}"
                )
            tensors = entry.run_inverse(tensors)
            if not self.is_valid_input(tensors):
                raise RMTCException(
                    f"Invalid tensors as output from inverted process {entry}"
                )
        return tensors
