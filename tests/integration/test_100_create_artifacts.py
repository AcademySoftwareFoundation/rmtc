# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import os

import rmtc.artifacts as artifacts
import rmtc.process as process
import rmtc.process as process
import rmtc_core.track.licenses.community as community_licenses
import rmtc_core.track.licenses.commercial as commercial_licenses
import rmtc_core.artifacts.torch.models as torch_models
import rmtc_core.artifacts.filesystem.datasets as filesystem_datasets
import rmtc_core.process.tensor.structure as structure_processors
import rmtc.track as track
from rmtc.system import URI

from .abstract_rmtc_integration_test import AbstractRMTCIntegrationTest


class TestCreateArtifacts(AbstractRMTCIntegrationTest):
    """Test RMTC artifact creation"""

    def test_create_artifacts(self):
        """Test creating artifacts"""
        sys = self.get_system()
        sys.delete_all()

        directory = "file://localhost" + os.getcwd()

        oss_license = sys.create_license(
            community_licenses.OSS,
            name="Apache-2.0",
            uri=URI("https://apache.org/licenses/LICENSE-2.0.html"),
            parties=["Mozilla Foundation"],
        )

        show_license = sys.create_license(
            commercial_licenses.Show,
            name="Show License",
            parties=["Production Company"],
        )

        foundation_model = sys.create_model(
            track.Model,
            name="Foundation Model",
            uri=URI("https://github.com/foundation_model"),
            author="Big Tech",
            licenses=[oss_license],
        )

        model = sys.create_model(
            torch_models.Torch,
            name="Refined Model",
            uri=URI(f"{directory}/models/test_model.pt"),
            input_type=artifacts.Image,
            output_type=artifacts.Image,
            input_shape=[-1, 3, -1, -1],  # RGB/BCHW
            output_shape=[-1, 1, -1, -1],  # A/BCHW
            asset_to_input=process.ProcessStack(
                stack=[
                    structure_processors.Batch(),
                    structure_processors.Flatten(),
                ]
            ),
            asset_to_output=process.ProcessStack(
                stack=[
                    structure_processors.Batch(),
                ]
            ),
            ancestors=[foundation_model],
        )

        dataset = sys.create_dataset(
            filesystem_datasets.CorrelatedFolder,
            name="Show Test Data",
            uri=URI(f"{directory}/datasets/show_traindata"),
            licenses=[show_license],
        )

        solution = sys.create_solution(
            name="Test Solution",
            uri=URI(f"{directory}/solutions/test"),
            input_type=artifacts.Image,
            output_type=artifacts.Image,
            description="Example Solution",
        )

        sys.push()
        sys.clear()

        # Get artifacts from the database
        model_foundation = sys.get_models("Foundation Model")[0]
        model_base = sys.get_models("Refined Model")[0]
        rmtc_license = sys.get_licenses("Show License")[0]
        dataset = sys.get_datasets("Show Test Data")[0]
        solution = sys.get_solutions("Test Solution")[0]

        self.assertEqual(model_foundation.name, "Foundation Model")
        self.assertEqual(model_base.name, "Refined Model")
        self.assertEqual(rmtc_license.name, "Show License")
        self.assertEqual(dataset.name, "Show Test Data")
        self.assertEqual(solution.description, "Example Solution")
