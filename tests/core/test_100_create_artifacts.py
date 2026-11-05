# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import os

import rmtc.ops.artifacts as artifacts
import rmtc.ops.assets as assets
import rmtc.ops.process as process
import rmtc.core.track.entities.licenses.community as community_licenses
import rmtc.core.track.entities.licenses.commercial as commercial_licenses
import rmtc.core.ops.artifacts.torch.models as torch_models
import rmtc.core.ops.process.image.transform as transform_processors
import rmtc.core.ops.process.image.color as color_processors
import rmtc.core.ops.process.image.channels as channel_processors
import rmtc.core.ops.process.tensor.structure as structure_processors

from rmtc.track import entities
from rmtc.track.entities import Party, Jurisdiction
from rmtc.system import URI
from rmtc.system import DataType
from rmtc.core.ops.process.torch.packagers.tensor import BatchedTorchTensor
from abstract_rmtc_test import AbstractRMTCTest


class TestCreateArtifacts(AbstractRMTCTest):
    """Test RMTC artifact creation"""

    def test_create_artifacts(self):
        """Test creating artifacts"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()

        directory = "file://localhost" + os.getcwd()

        oss_license = rmtc_sys.create_license(
            community_licenses.OSS,
            name="Apache-2.0",
            uri=URI("https://apache.org/licenses/LICENSE-2.0.html"),
            parties=[rmtc_sys.get_create(Party, name="Mozilla Foundation")], 
        )

        show_license = rmtc_sys.create_license(
            commercial_licenses.Show,
            name="Show License",
            parties=[rmtc_sys.get_create(Party, name="Production Company")],
        )

        foundation_model = rmtc_sys.create_model(
            entities.Model,
            name="Foundation Model",
            uri=URI("https://github.com/foundation_model"),
            author="Big Tech",
            licenses=[oss_license],
        )

        model = rmtc_sys.create_model(
            torch_models.TorchModel,
            name            = "Refined Model",
            uri             = URI(f"{directory}/models/test_model.pt"),
            ancestors       = [foundation_model],
            
            #inputs
            input_names     = ["Image"],
            input_types     = [assets.Image],
            input_packager  = process.ProcessPackager(
                processors  = [
                    process.ProcessStack(
                        stack=[
                            transform_processors.Resize(
                                width=776, 
                                height=776
                            ),
                            color_processors.LinearToSRGB(),
                            color_processors.StatsNormalize(
                                mean=[0.485, 0.456, 0.406], 
                                std=[0.229, 0.224, 0.225],
                            ),
                            channel_processors.TrimAlpha(),
                            channel_processors.MoveChannelsFirst(),
                        ]
                    ),    
                ],            
                packager    = BatchedTorchTensor(data_type=DataType.FLOAT32),
            ),

            #outputs
            output_names    = ["Image"],
            output_types    = [assets.Image],
            output_packager = process.ProcessPackager(
                processors   = [
                    process.ProcessStack(
                        stack=[
                            channel_processors.ExtractChannel(),
                            channel_processors.MoveChannelsFirst(), 
                        ]
                    ),
                ],
                packager    = BatchedTorchTensor(data_type=DataType.FLOAT32),
            ),
        )

        dataset = rmtc_sys.create_dataset(artifacts.Dataset,
            name="Show Test Data",
            uri=URI(f"{directory}/datasets/show_traindata"),
            licenses=[show_license],
        )

        solution = rmtc_sys.create_solution(
            name="Test Solution",
            uri=URI(f"{directory}/solutions/test"),
            input_types=[assets.Image],
            output_types=[assets.Image],
            description="Example Solution",
        )
        self.assertEqual(solution.description, "Example Solution")

        rmtc_sys.push()
        rmtc_sys.clear()

        # Get artifacts from the database
        model_foundation = rmtc_sys.get_models("Foundation Model")[0]
        model_base = rmtc_sys.get_models("Refined Model")[0]
        rmtc_license = rmtc_sys.get_licenses("Show License")[0]
        dataset = rmtc_sys.get_datasets("Show Test Data")[0]
        solution = rmtc_sys.get_solutions("Test Solution")[0]

        self.assertEqual(model_foundation.name, "Foundation Model")
        self.assertEqual(model_base.name, "Refined Model")
        self.assertEqual(rmtc_license.name, "Show License")
        self.assertEqual(dataset.name, "Show Test Data")
        self.assertEqual(solution.name, "Test Solution")        
        self.assertEqual(solution.description, "Example Solution")
