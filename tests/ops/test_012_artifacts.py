# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from itertools import chain
from unittest.mock import Mock

from rmtc.ops import artifacts
from rmtc.ops.pipeline import AssetManager
from rmtc.track.entities import (
    Asset,
    Right,
    License,
    Resource,
    LicenseStatus,
    Run,
    Solution,
)
from rmtc.core.ops.artifacts.torch.models import TorchModel
from rmtc.core.track.filters.license import RightsFilter
from rmtc.system.containers import Order
from rmtc.system.objects import Object
from rmtc.system import RMTCException

from abstract_rmtc_test import AbstractRMTCTest

class TestEntities(AbstractRMTCTest):

    def test_assign(self):
        """Test assignment roundtrips via store"""
        rmtc_sys = self.get_system()
        inference = rmtc_sys.create_inference()
        inf_obj_id = inference.obj_id
        dataset = rmtc_sys.create_dataset()
        dataset_obj_id = dataset.obj_id
        inference.inputs = dataset
        rmtc_sys.push()
        rmtc_sys.clear()
        found_inference = rmtc_sys.get_entity(obj_id=inf_obj_id)
        self.assertTrue(found_inference is not None)
        self.assertTrue(found_inference.inputs is not None)
        self.assertTrue(found_inference.inputs.obj_id == dataset_obj_id)

    def test_assign_via_prop(self):
        """Test equiavalence to assignment - specific bugfix"""
        rmtc_sys = self.get_system()
        inference = rmtc_sys.create_inference()
        inf_obj_id = inference.obj_id
        dataset = rmtc_sys.create_dataset()
        dataset_obj_id = dataset.obj_id
        prop = inference.get_property("inputs")
        self.assertTrue(prop is not None)
        prop.value = dataset
        self.assertTrue(inference.inputs is not None)
        rmtc_sys.push()
        rmtc_sys.clear()
        found_inference = rmtc_sys.get_entity(obj_id=inf_obj_id)
        self.assertTrue(found_inference is not None)
        self.assertTrue(found_inference.inputs is not None)        
        self.assertTrue(found_inference.inputs.obj_id == dataset_obj_id)

    def test_solution_rights(self):
        
        rmtc_sys = self.get_system()

        # 3 standard model rights - global
        faceswap = rmtc_sys.create_rights("Face Swap")
        upscale = rmtc_sys.create_rights("Upscale")
        deage = rmtc_sys.create_rights("De Age")
        commercial = rmtc_sys.create_rights("Commercial")
        warranty = rmtc_sys.create_rights("Warranty")
        attribution = rmtc_sys.create_rights("Attribution")
        test_show = rmtc_sys.create_rights("TST")

        # create some licenses
        academic_license = rmtc_sys.create_license(
            name = "Academic Non-Commercial License", 
            excludes = [commercial],
        )
        faces_license = rmtc_sys.create_license(
            name = "Commercial Face Dataset License", 
            grants = [faceswap, commercial],
            excludes = [upscale, deage],
        )
        apache_license = rmtc_sys.create_license(
            name = "Apache-2.0", 
            requires = [attribution],
            excludes = [warranty],
        )
        test_show_license = rmtc_sys.create_license(
            name = "Test Show", 
            grants = [test_show, attribution],
            requires = [commercial],
        )       
        
         # do some checks on license permissions
        self.assertFalse(academic_license.is_permitted([commercial]))
        self.assertTrue(test_show_license.is_permitted([commercial]))      
        self.assertTrue(apache_license.is_compatible(test_show_license))
        self.assertFalse(academic_license.is_compatible(test_show_license))

        # create some datasets
        free_faces = rmtc_sys.create_dataset(
            name = "Free Faces Dataset",
            licenses = [faces_license, academic_license],
        )  
        show_faces = rmtc_sys.create_dataset(
            name = "Show Faces Dataset",
            licenses = [faces_license, test_show_license],
        )  
        commercial_faces = rmtc_sys.create_dataset(
            name = "Commercial Faces Dataset",
            licenses = [faces_license],
        )  
        Images = rmtc_sys.create_dataset(
            name = "Generic Image Dataset",
            licenses = [apache_license],
        )  

        # faceswap
        fs_solution = rmtc_sys.create_solution(
            name = "FaceSwap Solution",
            filters = [
                RightsFilter(rights=[commercial, faceswap]),
            ]            
        )
        self.assertTrue(fs_solution.is_compliant([commercial_faces]))
        self.assertFalse(fs_solution.is_compliant([free_faces]))
        self.assertTrue(fs_solution.is_compliant([show_faces]))
             
        # show face swap
        fss_solution = rmtc_sys.create_solution(
            name = "FaceSwap Show Solution",
            filters = [
                RightsFilter(rights=[test_show, commercial, faceswap]),
            ]             
        )
        self.assertTrue(fss_solution.is_compliant([commercial_faces]))
        self.assertTrue(fss_solution.is_compliant([show_faces]))
        self.assertFalse(fss_solution.is_compliant([free_faces]))

        # upscale
        us_solution = rmtc_sys.create_solution(
            name = "UpScale Solution",
            filters = [
                RightsFilter(rights=[commercial, upscale, attribution]),
            ]
        )        
        self.assertTrue(us_solution.is_compliant([Images]))
            

    def test_license_rights(self):

        rmtc_sys = self.get_system()

        # create rights
        faceswap_right = rmtc_sys.create_rights(name="FaceSwap")
        repose_right = rmtc_sys.create_rights(name="RePose")

        # create rights on license
        license1 = rmtc_sys.create_license(name="FaceSwapLicense")
        license1.add_grants([faceswap_right])
        resource1 = rmtc_sys.create_resource(name="FaceSwapResource")        
        resource1.add_licenses([license1])     

        license2 = rmtc_sys.create_license(name="RePoseLicense")
        license2.add_grants([repose_right])       
        license2.add_excludes([faceswap_right])             
        resource2 = rmtc_sys.create_resource(name="RePoseResource")        
        resource2.add_licenses([license2])        

        # create a solution that requires faceswap right
        solution = rmtc_sys.create_solution(
            name="FaceSwapSolution",
            filters=[
                RightsFilter(
                    rights=[faceswap_right]
                ),
            ]
        )

        # solution should permit resources whose licenses grant faceswaps
        self.assertTrue(solution.is_compliant([resource1]))

        # solution should refuse resources whose licenses don't grant faceswaps
        self.assertFalse(solution.is_compliant([resource2]))

        # revoke license and no longer is_compliant
        license1.revoke()
        self.assertTrue(license1.status != LicenseStatus.ACTIVE)
        self.assertFalse(solution.is_compliant([resource1]))        

    def test_dataset_columns(self):
        dataset = artifacts.Dataset()
        count = 10
        a_assets = [Asset("A")] * count
        b_assets = [Asset("B")] * count
        c_assets = [Asset("C")] * count                
        dataset.add_column("A", a_assets)
        dataset.add_column("B", b_assets)
        dataset.add_column("C", c_assets)
        self.assertEqual(dataset.rows(), count)
        self.assertEqual(dataset.cols(), 3)
        self.assertEqual(dataset.get_column("A"), a_assets)
        self.assertEqual(dataset.get_column("B"), b_assets)
        self.assertEqual(dataset.get_column("C"), c_assets)  

    def test_dataset_aggregation_by_col(self):
        count = 10        
        a_assets = [Asset("A")] * count
        b_assets = [Asset("B")] * count
        c_assets = [Asset("C")] * count          
        dataset_a = artifacts.Dataset(assets=a_assets, columns=["A"])
        dataset_b = artifacts.Dataset(assets=b_assets, columns=["B"])
        dataset_c = artifacts.Dataset(assets=c_assets, columns=["C"])
        dataset = artifacts.Aggregation(
            datasets=[dataset_a, dataset_b, dataset_c],
            order=Order.COLUMN,
        )
        self.assertEqual(dataset.rows(), count)
        self.assertEqual(dataset.cols(), 3)
        self.assertEqual(dataset.names(), ["A", "B", "C"])
        self.assertEqual(dataset.get_column("A"), a_assets)
        self.assertEqual(dataset.get_column("B"), b_assets)
        self.assertEqual(dataset.get_column("C"), c_assets)         

    def test_dataset_aggregation_by_row(self):
        count = 10        
        a_assets = [Asset("A")] * count
        b_assets = [Asset("B")] * count
        c_assets = [Asset("C")] * count          
        dataset_a = artifacts.Dataset(assets=a_assets, columns=["ColA"])
        dataset_b = artifacts.Dataset(assets=b_assets, columns=["ColB"])
        dataset_c = artifacts.Dataset(assets=c_assets, columns=["ColC"])
        dataset = artifacts.Aggregation(
            datasets=[dataset_a, dataset_b, dataset_c],
            order=Order.ROW,
        )
        self.assertEqual(dataset.rows(), count * 3)
        self.assertEqual(dataset.cols(), 1)

    def test_dataset_iteration(self):
        count = 10        
        a_assets = [Asset("A")] * count
        b_assets = [Asset("B")] * count
        c_assets = [Asset("C")] * count          
        dataset_a = artifacts.Dataset(assets=a_assets, columns=["ColA"])
        dataset_b = artifacts.Dataset(assets=b_assets, columns=["ColB"])
        dataset_c = artifacts.Dataset(assets=c_assets, columns=["ColC"])
        datasets = [dataset_a, dataset_b, dataset_c]
        for row in artifacts.Dataset.generate_rows(datasets):
            self.assertEqual(len(row), 3)

        # confirm same behaviour with aggregations
        datasets = [artifacts.Aggregation(
            datasets=[dataset_a, dataset_b, dataset_c],
            order=Order.COLUMN,
        )]
        for row in artifacts.Dataset.generate_rows(datasets):
            self.assertEqual(len(row), 3)

    def test_dataset_filling(self):
        count = 10        
        a_assets = [Asset("A")] * count
        b_assets = [Asset("B")] * count
        c_assets = [Asset("C")] * count
        dataset_a = artifacts.Dataset(assets=a_assets, columns=["ColA"])
        dataset_b = artifacts.Dataset(assets=b_assets, columns=["ColB"])
        dataset_c = artifacts.Dataset(assets=c_assets, columns=["ColC"])
        datasets = [dataset_a, dataset_b, dataset_c]
        row = [Asset("X"), Asset("Y"), Asset("Z")]
        for dataset in datasets:
            row = dataset.fill_row(row)
        self.assertTrue(len(row) == 0)
        self.assertTrue(datasets[0][-1][0].name, "X") 
        self.assertTrue(datasets[1][-1][0].name, "Y") 
        self.assertTrue(datasets[2][-1][0].name, "Z")

        # confirm same behaviour with aggregations
        datasets = [artifacts.Aggregation(
            datasets=[dataset_a, dataset_b, dataset_c],
            order=Order.COLUMN,
        )]
        row = [Asset("U"), Asset("V"), Asset("W")]
        for dataset in datasets:
            row = dataset.fill_row(row)
        self.assertTrue(len(row) == 0)
        self.assertTrue(datasets[0][-1][0].name, "U")
        self.assertTrue(datasets[0][-1][1].name, "V")
        self.assertTrue(datasets[0][-1][2].name, "W")

    def test_dataset_is_typed_and_types_from_first_row(self):
        dataset = artifacts.Dataset(columns=["A"])
        self.assertFalse(dataset.is_typed())
        dataset.add_row([Asset("A")])
        self.assertTrue(dataset.is_typed())
        self.assertEqual(len(dataset.types), 1)
        self.assertTrue(dataset.types[0].is_instance(Asset("A")))

    def test_dataset_add_row_rejects_mismatched_type(self):
        dataset = artifacts.Dataset(columns=["A"])
        dataset.add_row([Asset("A")])
        with self.assertRaises(RMTCException):
            dataset.add_row([object()])
        self.assertEqual(dataset.rows(), 1)

    def test_dataset_add_row_rejects_wrong_row_length(self):
        dataset = artifacts.Dataset(columns=["A"])
        dataset.add_row([Asset("A")])
        with self.assertRaises(RMTCException):
            dataset.add_row([Asset("A"), Asset("B")])
        self.assertEqual(dataset.rows(), 1)

    def test_dataset_fill_row_returns_remainder(self):
        dataset = artifacts.Dataset(columns=["A"])
        remainder = dataset.fill_row([Asset("A"), Asset("B"), Asset("C")])
        self.assertEqual(len(remainder), 2)
        self.assertEqual(dataset.rows(), 1)
        self.assertEqual(dataset[-1][0].name, "A")

    def test_dataset_fill_row_rejects_empty_row(self):
        dataset = artifacts.Dataset(columns=["A"])
        with self.assertRaises(RMTCException):
            dataset.fill_row([])

    def test_dataset_remove_row(self):
        dataset = artifacts.Dataset(columns=["A"])
        row = [Asset("A")]
        dataset.add_row(row)
        self.assertEqual(dataset.rows(), 1)
        dataset.remove_row(row)
        self.assertEqual(dataset.rows(), 0)

    def test_dataset_add_row_infers_columns_and_types_when_unset(self):
        dataset = artifacts.Dataset()
        self.assertFalse(dataset.is_typed())
        self.assertEqual(dataset.cols(), 0)
        dataset.add_row([Asset("A")])
        self.assertEqual(dataset.columns, ["Asset"])
        self.assertTrue(dataset.is_typed())
        self.assertEqual(dataset.rows(), 1)

    def test_aggregation_add_row_by_col_rejects_mismatched_type(self):
        """
        NOTE: Order.COLUMN writes to member datasets sequentially with no
        rollback, so a rejected row still leaves earlier members mutated -
        dataset_a ends up with 2 rows even though the overall add_row failed.
        """
        dataset_a = artifacts.Dataset(columns=["A"])
        dataset_b = artifacts.Dataset(columns=["B"])
        dataset = artifacts.Aggregation(
            datasets=[dataset_a, dataset_b],
            order=Order.COLUMN,
        )
        dataset.add_row([Asset("A"), Asset("B")])
        with self.assertRaises(RMTCException):
            dataset.add_row([Asset("A"), object()])
        self.assertEqual(dataset_a.rows(), 2)
        self.assertEqual(dataset_b.rows(), 1)

    def test_aggregation_add_row_by_row_targets_last_dataset(self):
        dataset_a = artifacts.Dataset(columns=["Col"])
        dataset_b = artifacts.Dataset(columns=["Col"])
        dataset = artifacts.Aggregation(
            datasets=[dataset_a, dataset_b],
            order=Order.ROW,
        )
        dataset.add_row([Asset("A")])
        self.assertEqual(dataset_a.rows(), 0)
        self.assertEqual(dataset_b.rows(), 1)
        self.assertEqual(dataset.rows(), 1)

    def test_aggregation_remove_row_by_row_order_raises(self):
        """
        BUG: Aggregation.empty_row()'s Order.ROW branch does
        `self.datasets[:-1].remove_row(row)` - `self.datasets[:-1]` is a plain
        list slice with no `remove_row` method, so removal always raises.
        """
        dataset_a = artifacts.Dataset(columns=["Col"])
        dataset_b = artifacts.Dataset(columns=["Col"])
        dataset = artifacts.Aggregation(
            datasets=[dataset_a, dataset_b],
            order=Order.ROW,
        )
        row = [Asset("A")]
        dataset.add_row(row)
        with self.assertRaises(AttributeError):
            dataset.remove_row(row)



class TestModelResultNaming(AbstractRMTCTest):
    """Model.create_weights/create_checkpoint name their results from the run"""

    def setUp(self):
        super(TestModelResultNaming, self).setUp()
        import torch

        self.manager = AssetManager(readerwriter=Mock(), publisher=Mock(), log=Mock())
        Object.set_namer(self.manager.default_name)
        self.model = TorchModel(name="DepthModel", torch_model=torch.nn.Linear(2, 1))
        self.solution = Solution(name="LensBlur")
        self.run = Run(name="Training Run", model=self.model)
        self.run.solution = self.solution

    def test_create_weights_with_run(self):
        weights = self.model.create_weights(run=self.run)
        self.assertEqual(weights.parent, self.run)
        self.assertEqual(weights.model, self.model)
        self.assertEqual(weights.name, "LensBlur_DepthModel_weights")
        self.assertIsNotNone(weights.torch_weights)

    def test_create_checkpoint_with_run(self):
        checkpoint = self.model.create_checkpoint(run=self.run)
        self.assertEqual(checkpoint.parent, self.run)
        self.assertEqual(checkpoint.name, "LensBlur_DepthModel_checkpoint")
        self.assertIsNotNone(checkpoint.torch_weights)

    def test_create_weights_without_run(self):
        weights = self.model.create_weights()
        self.assertIsNone(weights.parent)
        self.assertEqual(weights.name, "DepthModel_weights")

    def test_create_weights_without_run_uses_model_solution(self):
        self.model.solution = self.solution
        self.assertEqual(
            self.model.create_weights().name, "LensBlur_DepthModel_weights"
        )

    def test_create_weights_explicit_name_kept(self):
        self.assertEqual(self.model.create_weights(run=self.run, name="x").name, "x")
        self.assertEqual(
            self.model.create_checkpoint(run=self.run, name="y").name, "y"
        )

    def test_create_weights_does_not_set_run_result(self):
        # linking the run's result is the caller's job
        self.model.create_weights(run=self.run)
        self.assertIsNone(self.run.result_weights)

    def test_create_weights_uses_installed_namer(self):
        Object.set_namer(lambda obj: "site_" + self.manager.default_name(obj))
        self.assertEqual(
            self.model.create_weights(run=self.run).name,
            "site_LensBlur_DepthModel_weights",
        )
