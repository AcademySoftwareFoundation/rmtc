# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.system import URI, Type, Datetime
from rmtc.objects import Data
from rmtc.track import (
    Entity,
    Weights,
    Inference,
    Model,
    Asset,
    Solution,
    Run,
    License,
    Dataset,
    Resource,
)

from .abstract_rmtc_unit_test import AbstractRMTCUnitTest


class MockEventEntity(Entity):

    def __init__(self):
        super(MockEventEntity, self).__init__()
        self.add_property("number", int)
        self._updated = False
        self._accessed = False

    def property_updated(self, prop):
        self._updated = True
        super(MockEventEntity, self).property_updated(prop)

    def property_accessed(self, prop):
        self._accessed = True
        super(MockEventEntity, self).property_accessed(prop)

    @classmethod
    def category(cls):
        return "Mock"


class TestEntities(AbstractRMTCUnitTest):

    def test_timestamps(self):
        sys = self.get_system()
        entity = sys.create_entity(Resource, name="Test Entity")
        test_time = Datetime()
        entity.add_property("test", int)
        entity.test = 100
        updated_timestamp = entity.timestamp
        self.assertTrue(test_time < updated_timestamp)
        sys.push()
        sys.clear()
        entity = sys.get_entities(name="Test Entity")[0]
        self.assertTrue(entity.timestamp > updated_timestamp)
        updated_timestamp = entity.timestamp
        entity.test = 200
        self.assertTrue(entity.timestamp > updated_timestamp)
        sys.push()
        self.assertFalse(entity.requires_update())

    def test_entity_notification(self):
        obj = MockEventEntity()
        self.assertFalse(obj._accessed)
        print(obj.number)
        self.assertTrue(obj._accessed)
        self.assertFalse(obj._updated)
        obj.number = 10
        self.assertTrue(obj._updated)

    def test_nested_datasets(self):

        # create datasets
        dataset_a = Dataset("A")
        dataset_b = Dataset("B")
        dataset_c = Dataset("C")
        dataset_d = Dataset("D")
        dataset_e = Dataset("E")
        dataset_f = Dataset("F")
        dataset_g = Dataset("G")

        # add assets
        dataset_a.add_assets([Asset("A1"), Asset("A2"), Asset("A3")])
        dataset_b.add_assets([Asset("B1"), Asset("B2"), Asset("B3")])
        dataset_c.add_assets([Asset("C1"), Asset("C2"), Asset("C3")])
        dataset_d.add_assets([Asset("D1"), Asset("D2"), Asset("D3")])
        dataset_e.add_assets([Asset("E1"), Asset("E2"), Asset("E3")])
        dataset_f.add_assets([Asset("F1"), Asset("F2"), Asset("F3")])
        dataset_g.add_assets([Asset("G1"), Asset("G2"), Asset("G3")])

        # nest them in a tree
        dataset_a.add_datasets([dataset_b, dataset_c])
        dataset_b.add_datasets([dataset_d, dataset_e])
        dataset_c.add_datasets([dataset_f, dataset_g])

        # create depth first expected order - ABDECFG
        #      A
        #    /   \
        #   B     C
        #  / \   / \
        # D   E F   G
        names = [
            "A1",
            "A2",
            "A3",
            "B1",
            "B2",
            "B3",
            "D1",
            "D2",
            "D3",
            "E1",
            "E2",
            "E3",
            "C1",
            "C2",
            "C3",
            "F1",
            "F2",
            "F3",
            "G1",
            "G2",
            "G3",
        ]

        # validate
        collected_names = []
        for row in dataset_a:
            collected_names.append(row[0].name)
        self.assertEqual(names, collected_names)

    def test_uniqueness(self):
        """Does an entity exist uniquely in the system"""
        sys = self.get_system()
        sys.delete_all()
        sys.create_license(name="Apache-2.0")
        sys.push()
        sys.clear()
        self.assertEqual(len(sys.objects.get()), 0)
        sys.get_licenses(name="Apache-2.0")
        self.assertEqual(len(sys.objects.get()), 1)

    def test_update_push(self):
        """Are the update flags being correctly set and cleared"""
        sys = self.get_system()
        sys.delete_all()
        test_a = sys.create_license(name="Apache-2.0")
        sys.push()
        test_a.add_parties(["ASWF"])
        self.assertTrue(test_a.requires_update())
        sys.push()
        self.assertFalse(test_a.requires_update())
        sys.clear()
        test_b = sys.get_licenses(name="Apache-2.0")[0]
        self.assertEqual(test_a.parties, test_b.parties)

    def test_custom_pod_properties(self):
        """Can we add a custom pod type and do a round trip to the DB"""
        sys = self.get_system()
        sys.delete_all()
        test_a = sys.create_license(name="Apache-2.0")
        test_a.add_property("test_value", int, 123)
        test_a.add_property("test_array", [int], [1, 2, 3])
        test_a.add_property("test_string", str, "Hello World!")
        self.assertTrue(test_a.requires_update())
        sys.push()
        self.assertFalse(test_a.requires_update())
        sys.clear()
        test_b = sys.get_licenses(name="Apache-2.0")[0]
        self.assertEqual(test_a.test_value, test_b.test_value)
        self.assertEqual(test_a.test_array, test_b.test_array)
        self.assertEqual(test_a.test_string, test_b.test_string)

    def test_delete(self):
        """Can we mark an entity for deletion"""
        sys = self.get_system()
        sys.delete_all()
        test_a = sys.create_license(name="Apache-2.0")
        sys.push()
        sys.clear()
        test_b = sys.get_licenses(name="Apache-2.0")[0]
        self.assertTrue(test_b in sys.objects.get())
        test_b.mark_for_delete()
        sys.push()
        self.assertFalse(test_b in sys.objects.get())
        self.assertTrue(test_b.store is None)

    def test_sync(self):
        """Test sync"""
        sys = self.get_system()
        sys.delete_all()
        uri = URI("https://www.apache.org/licenses/LICENSE-2.0.txt")
        test_a = sys.create_license(name="Apache-2.0", uri=uri)
        sys.push()
        a_id = test_a.obj_id
        sys.clear()
        test_b = sys.get_licenses(name="Apache-2.0", sync=False)[0]
        b_id = test_b.obj_id
        self.assertEqual(a_id, b_id)
        sys.pull([test_b])
        self.assertEqual(test_b.uri, test_a.uri)

    def test_on_demand(self):
        """Can we have a property update on demand - without a connection"""
        sys = self.get_system()
        sys.delete_all()
        uri = URI("https://www.apache.org/licenses/LICENSE-2.0.txt")
        test_a = sys.create_license(name="Apache-2.0", uri=uri)
        sys.push()
        sys.clear()
        test_b = sys.get_licenses(name="Apache-2.0", sync=False)[0]
        self.assertEqual(test_b.uri, test_a.uri)

    def test_inferences(self):
        """Do assets and inference relationships make sense"""
        sys = self.get_system()
        inputs = []
        for i in range(3):
            inputs.append(Asset())
        inputs = Dataset(assets=inputs)
        result = []
        for i in range(3):
            result.append(Asset())
        result_dataset = Dataset(assets=result)
        inference = sys.create_inference(
            result=result_dataset,
            inputs=inputs,
        )
        self.assertEqual(len(inference.result.assets), 3)
        self.assertEqual(inference.result.assets, result)
        sys.push()
        sys.clear()
        self.assertEqual(len(sys.objects.get()), 0)
        inferences = sys.get_inferences()
        self.assertEqual(len(inferences), 1)
        inference = inferences[0]
        self.assertTrue(inference.result != None)
        self.assertEqual(len(inference.result.assets), 3)

    def _flatten_tree(self, tree):
        result = [tree[0]]
        for value in tree[1]:
            result.extend(self._flatten_tree(value))
        return result

    def _create_provenance(self):

        license = License()

        train_dataset = Dataset()
        train_dataset.license = license

        model = Model()
        model.license = license

        weights = Weights()
        weights.model = model

        solution = Solution()

        run = Run()
        run.model = model
        run.dataset = train_dataset
        run.result_weights = weights
        run.solution = solution

        inputs = Dataset()
        inputs.license = license

        outputs = Dataset(assets=[Asset(), Asset(), Asset()])

        inference = Inference()
        inference.dataset = inputs
        inference.result = outputs
        inference.weights = weights
        inference.model = model

        return [solution, run, inference, model, license, train_dataset]

    def test_sources(self):
        """Search up"""

        entities = self._create_provenance()

        # add it to db
        sys = self.get_system()
        sys.add_entities(entities)
        sys.push()
        sys.clear()

        # query it directly
        asset = sys.get_assets()[0]
        sources = sys.trace_sources(asset)
        flat_sources = self._flatten_tree(sources)
        self.assertTrue(len(flat_sources), 4)

    def test_derivatives(self):
        """Search down"""

        entities = self._create_provenance()

        # add it to db
        sys = self.get_system()
        sys.add_entities(entities)
        sys.push()
        sys.clear()

        # query it directly
        solution = sys.get_solutions()[0]
        derviatives = sys.trace_derivatives(solution)
        flat_derviatives = self._flatten_tree(derviatives)
        self.assertTrue(len(flat_derviatives), 9)

    def test_factory(self):
        data = Data()
        rmtc_sys = self.get_system()
        prop_type = data.add_property("test_type", Type, License)
        prop_type.value = "rmtc.License.License-1.0.0"
        prop_type.value.resolve(rmtc_sys.factory)
        obj = prop_type.value()
        self.assertTrue(isinstance(obj, License))

    def test_disconnect(self):
        """Create connected entities, push, disconnect and push"""
        sys = self.get_system()

        # populate
        resource = sys.create_entity(Resource, name="Test")
        license1 = sys.create_entity(License, name="A")
        license2 = sys.create_entity(License, name="B")
        resource.add_licenses([license1, license2])
        sys.push()
        sys.clear()

        # get and check
        resource = sys.get_entities(name="Test")[0]
        licenses = resource.licenses
        self.assertEqual(len(licenses), 2)

        # disconnect & push
        license1 = licenses[0]
        resource.remove_licenses([license1])
        self.assertEqual(len(resource.licenses), 1)
        sys.push()
        sys.clear()

        # pull and check for only one
        resource = sys.get_entities(name="Test")[0]
        licenses = resource.licenses
        self.assertEqual(len(licenses), 1)
        license = licenses[0]
        self.assertEqual(license.name, "B")
