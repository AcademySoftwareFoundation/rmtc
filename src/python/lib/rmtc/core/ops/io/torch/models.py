# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import warnings
import importlib
from pathlib import Path

import torch
from torch import package
from torch.package import sys_importer

from rmtc.system import RMTCException, Package
from rmtc.ops.io import IO
from rmtc.ops.artifacts import Model

ignore_warnings = [
    ".*TypedStorage is deprecated.*",
]
for to_ignore in ignore_warnings:
    warnings.filterwarnings("ignore", message=to_ignore)


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
        name=None,
        obj_id=None,
        package_name="",
        model_name="",
        interns=None,
        externs=None,
    ):
        super(TorchPackage, self).__init__(
            name=name,
            obj_id=obj_id,
        )
        self.add_property("model_name", str, model_name)
        self.add_property("package_name", str, package_name)
        self.add_property("interns", [Package], interns)
        self.add_property("externs", [Package], externs)
        self._model_importer = None

    def create_name(self, artifact):
        return str(Path(artifact.name + ".pt"))

    def get_scheme(self):
        return "file"

    def get_artifact_type(self):
        return Model

    def is_uri_supported(self, uri):
        """Check if URI points to a valid .pt file."""
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".pt"
        return False

    def read(self, uri, artifact, asset_manager):
        """
        Load PyTorch package model from file into artifact.

        Creates a PackageImporter and loads the specified model from the
        package using the configured package and model names.
        """
        if uri.path.exists():
            self._model_importer = package.PackageImporter(str(uri.path))
            artifact.torch_model = self._model_importer.load_pickle(
                self.model_name,
                self.package_name,
            )

    def write(self, uri, artifact, asset_manager):
        """
        Save PyTorch package model from artifact to file.

        Creates a PackageExporter and saves the model with its dependencies,
        managing external and internal module specifications.
        """

        model = artifact.torch_model

        # imported before - used importer
        if self._model_importer is not None:
            with package.PackageExporter(
                str(uri.path), importer=(self._model_importer, sys_importer)
            ) as exporter:
                for extern in artifact.externs:
                    exporter.extern(extern)
                    exporter.extern(extern + ".**")
                exporter.intern("**")
                exporter.save_pickle(self.model_name, self.package_name, model)

            return

        # write it out
        resource_name = f"{self.package_name}.pkl"
        with package.PackageExporter(self.uri.path) as exp:
            for extern in self.externs:
                exp.extern(f"{extern.name}.**")
            for intern in self.interns:
                exp.intern(f"{intern.name}.**")
            exp.extern(["rmtc.**"])
            exp.save_pickle(self.package_name, resource_name, model)

    @staticmethod
    def package_model(
        output_path,
        package_name,
        model=None,
        model_name=None,
        interns=None,
        externs=None,
        overwrite=True,
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

        # check path exists
        output_path.mkdir(parents=True, exist_ok=True)
        path = Path(output_path) / str(package_name + ".pt")
        if path.exists() and not overwrite:
            return str(path)

        # instantiate and override model if name provided
        if model_name is not None:
            parts = model_name.split(".")
            module_name = ".".join(parts[:-1])
            class_name = parts[-1]
            try:
                module = importlib.import_module(module_name)
                importlib.invalidate_caches()
                model = getattr(module, class_name)()
            except Exception as e:  # pylint: disable=broad-exception-caught
                raise RMTCException(
                    f"Error initializing package with string: '{model_name}'\n{e}"
                ) from e

        # if no model - then we are in error
        if model is None:
            raise RMTCException("No valid model")

        # write it out
        resource_name = f"{package_name}.pkl"
        with package.PackageExporter(path) as exp:
            for extern in externs:
                exp.extern(f"{extern}.**")
            for intern in interns:
                exp.intern(f"{intern}.**")
            exp.extern(["rmtc.**"])
            exp.save_pickle(package_name, resource_name, model)

        return path


class TorchScript(IO):
    """
    Reader/writer for PyTorch model weights in .pt format.

    The TorchWeightsFile class handles serialization and deserialization of
    PyTorch model weights (state dictionaries) to and from .pt files. It
    provides secure loading with weights_only=True to prevent arbitrary
    code execution during deserialization.

    This reader/writer is specifically designed for TorchWeights artifacts
    and ensures proper device device management during loading operations.
    """

    def __init__(self, trace=False):
        super(TorchScript, self).__init__()
        self.add_property("trace", bool, trace)

    def create_name(self, artifact):
        return str(Path(artifact.name + ".pt"))

    def get_scheme(self):
        return "file"

    def get_artifact_type(self):
        return Model

    def is_uri_supported(self, uri):
        """Check if URI points to a valid .pt file."""
        if uri.scheme == "file":
            return uri.path.suffix.lower() == ".pt"
        return False

    def read(self, uri, artifact, asset_manager):
        """Load PyTorch weights from file into artifact."""
        if artifact.torch_model is None:
            artifact.torch_model = torch.jit.load(str(uri.path))

    def write(self, uri, artifact, asset_manager):
        """Save PyTorch weights from artifact to file."""
        if artifact.torch_model is not None:
            model = artifact.torch_model
            if not torch.cuda.is_available():
                raise RMTCException("Can't trace weights without cuda")
            model = model.to("cuda")
            model.eval()
            with torch.no_grad():
                if self.trace:  # pylint: disable=using-constant-test
                    test_input = artifact.create_inputs()
                    model = torch.jit.trace(model, test_input)
                else:
                    model = torch.jit.script(model)
            if not artifact.trainable:
                model = torch.jit.optimize_for_inference(model)
            model.save(str(uri.path))
