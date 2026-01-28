# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


import numpy as np

from rmtc.process import Process


class Batch(Process):
    """
    Tensor batching processor for combining individual tensors into batches.

    The Batch processor stacks multiple input tensors along a new batch dimension
    (axis 0) to create batched data suitable for batch processing in ML models.
    It provides bidirectional transformation between individual tensors and
    batched representations.

    This processor is commonly used in data pipelines to combine individual
    samples into batches for efficient model inference or training.
    """

    def run(self, tensors):
        """Stack individual tensors into a single batch tensor."""
        out = np.stack(tensors, axis=0)
        return [out]

    def run_inverse(self, tensors):
        """Unstack a batch tensor into individual tensors."""
        tensor = tensors[0]
        return [tensor[i] for i in range(tensor.shape[0])]


class Flatten(Process):
    """
    Tensor flattening processor for memory layout optimization.

    The Flatten processor converts input tensors to contiguous float32 arrays,
    optimizing memory layout for efficient computation. This is commonly used
    as a preprocessing step to ensure tensors have the expected data type and
    memory layout for downstream operations.

    The processor ensures C-contiguous memory layout which can improve
    performance in numerical computations and model inference.
    """

    def run(self, tensors):
        """Convert tensors to contiguous float32 arrays."""
        return np.ascontiguousarray(tensors, dtype=np.float32)

    def run_inverse(self, tensors):
        """
        Unintuitive, but tensors are assumed to have been made contingious running
        forwards, skipping that as you might expect, skips the expected state of
        the tensor when running in reverse, we need to pretend to be a no-op
        """
        return np.ascontiguousarray(tensors, dtype=np.float32)
