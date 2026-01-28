# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from abc import ABC

import rmtc.track
from rmtc.objects import IN


class Process(rmtc.track.Entity, ABC):
    """
    Abstract base class for tensor processing operations.

    As part of the model we have processes - these are smaller bidirectional
    operations that act on lists of tensors.

    We operate on lists as working on batched tensors is tightly coupled
    to the requirements of the model, making the process less transportable.

    The last step in a process will likely be batching and flattening.

    Process implements need to support both forward and inverse
    operations to support the 3 main conversion requirements.

    The Process class is designed to be composable, allowing multiple
    processes to be chained together in ProcessStack instances or
    inverted using ProcessInverter.

    All concrete Process implementations must provide both forward (run)
    and inverse (run_inverse) operations, along with appropriate validation
    methods for each direction that protect against poor tensor formats.
    """

    def run(self, tensors):
        """
        Run the forward process on tensors.

        Applies the forward transformation to the input tensors. This is
        the main processing method that implements the core functionality
        of the process. The specific transformation depends on the concrete
        implementation.
        """
        pass

    def run_inverse(self, tensors):
        """
        Run the inverse process on tensors.

        Applies the inverse transformation to the input tensors, effectively
        reversing the forward operation. This enables bidirectional data
        flow and reconstruction of original data from processed results.
        """
        pass

    @classmethod
    def category(cls):
        """Get the entity type name."""
        return "Process"


class ProcessInverter(Process):
    """
    Inverts the behavior of another process.

    This class wraps another process and swaps its run and run_inverse methods,
    effectively creating an inverted version of the original process. This is
    useful for creating reverse transformations or when you need to apply a
    process in the opposite direction.

    The ProcessInverter maintains the same interface as the base Process class
    but delegates to the wrapped process with inverted method calls:
    - run() calls the wrapped process's run_inverse()
    - run_inverse() calls the wrapped process's run()
    """

    def __init__(self, process=None):
        """Initialize the ProcessInverter with a process to invert."""
        super(ProcessInverter, self).__init__()
        self.add_property("process", Process, process, direction=IN)

    def run(self, tensors):
        """
        Run the inverted process (calls run_inverse on wrapped process).

        Validates the tensors using the wrapped process's inverse validation
        method, then applies the wrapped process's inverse operation.
        """
        return self.process.run_inverse(tensors)

    def run_inverse(self, tensors):
        """
        Run the inverse of the inverted process (calls run on wrapped process).

        Validates the tensors using the wrapped process's forward validation
        method, then applies the wrapped process's forward operation.
        """
        return self.process.run(tensors)


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

    def run(self, tensors):
        """
        Run all processes in the stack sequentially.

        Executes each process in the stack in order, passing the output
        of each process as input to the next. Each process is validated
        before execution to ensure data integrity throughout the pipeline.
        """
        for entry in self.stack:
            tensors = entry.run(tensors)
        return tensors

    def run_inverse(self, tensors):
        """
        Run all processes in the stack in reverse order with inverse operations.

        Executes each process in the stack in reverse order, calling the
        run_inverse method on each. This effectively undoes the forward
        pipeline by applying inverse transformations in the opposite sequence.
        """
        for entry in reversed(self.stack):
            tensors = entry.run_inverse(tensors)
        return tensors
