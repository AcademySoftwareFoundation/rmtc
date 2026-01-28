# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


import importlib

import torch
from torch import package
from torch.package import sys_importer

from rmtc.system import URI, Context, RMTCException
from rmtc.io import IO
from rmtc.artifacts import Model


class TorchWeightsFile(IO):
    """
    Reader/writer for PyTorch model weights in .pt format.

    The TorchWeightsFile class handles serialization and deserialization of
    PyTorch model weights (state dictionaries) to and from .pt files. It
    provides secure loading with weights_only=True to prevent arbitrary
    code execution during deserialization.

    This reader/writer is specifically designed for TorchWeights artifacts
    and ensures proper device context management during loading operations.
    """

    def create_uri(self, artifact):
        new_uri = URI(scheme="file", host="localhost")
        new_uri.path /= artifact.name
        new_uri.path = new_uri.path.with_suffix(".pt")
        return new_uri

    def is_artifact_supported(self, artifact):
        return isinstance(artifact, Model)

    def is_uri_supported(self, uri):
        """Check if URI points to a valid .pt file."""
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".pt"
        return False

    def read(self, artifact, uri):
        """Load PyTorch weights from file into artifact."""
        device = "cuda"
        if artifact.get_context() == Context.CPU:
            device = "cpu"
        weights = artifact
        if weights.torch_weights is None:
            if uri.exists():
                weights.torch_weights = torch.load(
                    str(uri.path), weights_only=True, map_location=device
                )

    def write(self, artifact, uri):
        """Save PyTorch weights from artifact to file."""
        weights = artifact
        if weights.torch_weights is not None:
            torch.save(weights.torch_weights, str(uri.path))
        else:
            raise RMTCException("Torch weights is empty")


class TorchCheckpointFile(IO):
    """
    Reader/writer for PyTorch training checkpoints in .pt format.

    The TorchCheckpointFile class handles serialization and deserialization of
    complete PyTorch training checkpoints including model weights, optimizer
    state, epoch information, and training metrics. This enables full training
    state restoration for resuming interrupted training sessions.

    The checkpoint format includes:
    - Model state dictionary
    - Optimizer state dictionary
    - Current epoch number
    - Optimizer name/type
    - Performance metrics
    """

    def create_uri(self, artifact):
        new_uri = URI(scheme="file", host="localhost")
        new_uri.path /= artifact.name
        new_uri.path = new_uri.path.with_suffix(".pt")
        return new_uri

    def is_artifact_supported(self, artifact):
        return isinstance(artifact, Model)

    def is_uri_supported(self, uri):
        """Check if URI points to a valid .pt file."""
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".pt"
        return False

    def read(self, artifact, uri):
        """
        Load PyTorch checkpoint from file into artifact.

        Loads the complete training state including model weights, optimizer
        state, epoch information, and metrics from the checkpoint file.
        """
        device = "cuda"
        if artifact.get_context() == Context.CPU:
            device = "cpu"

        checkpoint = artifact
        if uri.exists():
            checkpoint_state = torch.load(
                str(checkpoint.uri.path), weights_only=False, map_location=device
            )

            # Validate required keys exist
            required_keys = [
                "epoch",
                "optimizer_name",
                "model_state",
                "optimizer_state",
                "metric",
            ]
            if not all(key in checkpoint_state for key in required_keys):
                raise RMTCException(
                    f"Invalid checkpoint format, missing required keys {required_keys}"
                )

            checkpoint.epoch = checkpoint_state["epoch"]
            checkpoint.optimizer_name = checkpoint_state["optimizer_name"]
            checkpoint.torch_weights = checkpoint_state["model_state"]
            checkpoint.torch_optimizer = checkpoint_state["optimizer_state"]
            checkpoint.metric = checkpoint_state["metric"]

    def write(self, artifact, uri):
        """
        Save PyTorch checkpoint from artifact to file.

        Saves the complete training state including model weights, optimizer
        state, epoch information, and metrics to the checkpoint file.
        """
        checkpoint = artifact
        checkpoint_state = {
            "epoch": checkpoint.epoch,
            "optimizer_name": checkpoint.optimizer_name,
            "model_state": checkpoint.torch_weights,
            "optimizer_state": checkpoint.torch_optimizer,
            "metric": checkpoint.metric,
        }
        torch.save(checkpoint_state, str(uri.path))


class TorchPackage(IO):
    """
    Reader/writer for PyTorch package format models in .pt files.

    The TorchPackage class handles serialization and deserialization of
    PyTorch package format models, which can contain multiple components,
    external dependencies, and complex model structures. It manages package
    importers and exporters for safe model distribution and loading.

    PyTorch packages provide a secure way to distribute models with their
    dependencies while controlling what external modules can be accessed
    during loading and execution.
    """

    def __init__(
        self,
        package_name="",
        model_name="",
        externs=None,
    ):
        super(TorchPackage, self).__init__()
        self.add_property("model_name", str, model_name)
        self.add_property("package_name", str, package_name)
        self.add_property("externs", [str], externs)
        self._model_importer = None

    def create_uri(self, artifact):
        new_uri = URI(scheme="file", host="localhost")
        new_uri.path /= artifact.name
        new_uri.path = new_uri.path.with_suffix(".pt")
        return new_uri

    def is_artifact_supported(self, artifact):
        return isinstance(artifact, Model)

    def is_uri_supported(self, uri):
        """Check if URI points to a valid .pt file."""
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".pt"
        return False

    def read(self, artifact, uri):
        """
        Load PyTorch package model from file into artifact.

        Creates a PackageImporter and loads the specified model from the
        package using the configured package and model names.
        """
        if uri.exists():
            self._model_importer = package.PackageImporter(str(uri.path))
            artifact.torch_model = self._model_importer.load_pickle(
                self.model_name, self.package_name
            )

    def write(self, artifact, uri):
        """
        Save PyTorch package model from artifact to file.

        Creates a PackageExporter and saves the model with its dependencies,
        managing external and internal module specifications.
        """
        if self._model_importer is None:
            raise RMTCException("Can't write a previously un-imported TorchPackage")
        with package.PackageExporter(
            str(uri.path), importer=(self._model_importer, sys_importer)
        ) as exporter:
            for extern in artifact.externs:
                exporter.extern(extern)
                exporter.extern(extern + ".**")
            exporter.intern("**")
            exporter.save_pickle(
                self.model_name, self.package_name, artifact.torch_model
            )

    @staticmethod
    def package_model(
        output_path,
        package_name,
        model=None,
        model_name=None,
        interns=None,
        externs=None,
    ):
        """
        Create a PyTorch package from a model for secure distribution.

        This function packages a PyTorch model into the PyTorch package format,
        which provides a secure way to distribute models with controlled access
        to external dependencies. The package format enables safe model sharing
        while preventing arbitrary code execution during loading.

        The function supports both direct model instances and dynamic model
        instantiation from fully qualified class names. It handles dependency
        management through the interns parameter, which specifies which modules
        should be included within the package.E
        """

        if interns is None:
            interns = []
        if externs is None:
            externs = []

        # instantiate and override model if name provided
        if model_name is not None:
            parts = model_name.split(".")
            module_name = ".".join(parts[:-1])
            class_name = parts[-1]
            try:
                module = importlib.import_module(module_name)
                model = getattr(module, class_name)()
            except Exception as e:  # pylint: disable=broad-exception-caught
                raise RMTCException(
                    f"Error initializing package with string: '{model_name}'\n{e}"
                ) from e

        # if no model - then we are in error
        if model is None:
            raise RMTCException("No valid model")

        # write it out
        path = str(output_path / (package_name + ".pt"))
        resource_name = f"{package_name}.pkl"
        with package.PackageExporter(path) as exp:
            for intern in interns:
                exp.intern(f"{intern}.**")
            exp.extern(["rmtc_core"] + externs)
            exp.save_pickle(package_name, resource_name, model)

        return path


class Torchscript(IO):
    """
    Reader/writer for PyTorch model weights in .pt format.

    The TorchWeightsFile class handles serialization and deserialization of
    PyTorch model weights (state dictionaries) to and from .pt files. It
    provides secure loading with weights_only=True to prevent arbitrary
    code execution during deserialization.

    This reader/writer is specifically designed for TorchWeights artifacts
    and ensures proper device context management during loading operations.
    """

    def create_uri(self, artifact):
        new_uri = URI(scheme="file", host="localhost")
        new_uri.path /= artifact.name
        new_uri.path = new_uri.path.with_suffix(".pt")
        return new_uri

    def is_artifact_supported(self, artifact):
        return isinstance(artifact, Model)

    def is_uri_supported(self, uri):
        """Check if URI points to a valid .pt file."""
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".pt"
        return False

    def read(self, artifact, uri):
        """Load PyTorch weights from file into artifact."""
        if artifact.torch_model is None:
            artifact.torch_model = torch.jit.load(str(uri.path))

    def write(self, artifact, uri):
        """Save PyTorch weights from artifact to file."""
        if artifact.torch_model is not None:
            model = artifact.torch_model
            model = model.to("cuda")
            model.eval()
            with torch.no_grad():
                model = torch.jit.script(model)
                model = torch.jit.optimize_for_inference(model)
                model.save(str(uri.path))
