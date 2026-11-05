# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import rmtc.core.track.entities.licenses.community as community_licenses
import rmtc.core.track.entities.licenses.commercial as commercial_licenses
import rmtc.track
from rmtc.system import URI, Datetime
from rmtc.ops.scheduling import Status
from rmtc.track.entities import Party, Jurisdiction

from abstract_rmtc_test import AbstractRMTCTest


class TestTracking(AbstractRMTCTest):
    """Ensure RMTC tracking is working as expected"""

    def test_create_entity(self):
        """Test creating a single entity"""
        # Create a license
        name = "Apache-1.0"
        uri = URI("https://www.apache.org/licenses/LICENSE-1.0.html")
        parties = [Party("Mozilla Foundation")]
        apache1_license = community_licenses.OSS(
            name,
            uri=uri,
            parties=parties,
        )

        # Push to the database
        db = self.get_system().track.open()
        db.create([apache1_license] + parties)
        db.update([apache1_license] + parties)
        db.close()

        # Pull from the database
        db = self.get_system().track.open()
        license_id = db.queries.get_licenses(name)[0]
        apache_licenses = db.fetch([license_id])
        self.assertNotEqual(apache_licenses, [])
        db.sync(apache_licenses)
        apache_license = apache_licenses[0]
        self.assertEqual(apache_license.properties.get("uri").value, uri)
        db.sync(apache_license.parties)
        self.assertEqual(apache_license.properties.get("parties").value, parties)
        db.close()
        
    def test_create_models_licenses(self):
        """Test tracking for models, licenses and datasets"""

        rmtc_sys = self.get_system()

        # Create licenses
        ml_license = commercial_licenses.Agreement(
            "Example ML License",
            parties=[
                rmtc_sys.get_create(Party, name="VFX Facility"),
                rmtc_sys.get_create(Party, name="Production Facility")
            ],
            jurisdictions=[rmtc_sys.get_create(Jurisdiction, name="US/LA")],
            date=Datetime("2020-05-01T11:31:46.258000"),
            start=Datetime("2020-05-01T11:31:46.258000"),
            finish=Datetime("2024-05-01T11:31:46.258000"),
            uri=URI("sharepoint://documents/ml_training_agreement.pdf"),
            externals=["0123456789"],
        )
        apache2_license = community_licenses.OSS(
            "Apache-2.0",
            uri=URI("https://apache.org/licenses/LICENSE-2.0.html"),
            parties=[rmtc_sys.get_create(Party, name="Mozilla Foundation")], 
        )
        show_license = commercial_licenses.Show(
            "Show License",
            parties=[rmtc_sys.get_create(Party, name="Production Facility")],
            start=Datetime("2023-05-01T11:31:46.258000"),
            finish=Datetime("2030-05-01T11:31:46.258000"),
        )
        actor_license = commercial_licenses.Agreement(
            "John Smith Likeness",
            parties=[
                rmtc_sys.get_create(Party, name="John Smith"),
                rmtc_sys.get_create(Party, name="Production Company")],
            date=Datetime("2015-05-01T11:31:00"),
            start=Datetime("2020-05-01T11:31:46.258000"),
            finish=Datetime("2030-05-01T11:31:46.258000"),
            uri=URI("ftp://production_company.com/documents/likeness_agreement.pdf"),
            externals=["0123456789"],
        )

        # Update with some notes
        notes = [
            "Must not be used in a context that may damage reputation",
            "Only used for facial swap training",
        ]
        for note in notes:
            actor_license.notes.append(note)

        # Add to the Objects
        db = rmtc_sys.track.open()
        db.create([apache2_license, show_license, ml_license, actor_license])
        db.update([apache2_license, show_license, ml_license, actor_license])
        db.close()

        # Fetch our created license via the DB
        db = rmtc_sys.track.open()
        license_id = db.queries.get_licenses("John Smith Likeness")[0]
        actor_licenses = db.fetch([license_id])
        self.assertNotEqual(actor_licenses, [])
        actor_license = actor_licenses[0]
        db.sync([actor_license])
        db.close()
        self.assertEqual(actor_license.properties.get("notes").value, notes)

        # Find the licenses
        db = rmtc_sys.track.open()
        apache_license = db.fetch(db.queries.get_licenses("Apache-2.0"))[0]
        show_license = db.fetch(db.queries.get_licenses("Show License"))[0]
        ml_license = db.fetch(db.queries.get_licenses("Example ML License"))[0]
        john_license = db.fetch(db.queries.get_licenses("John Smith Likeness"))[0]
        db.sync([apache_license, show_license, ml_license, john_license])
        db.close()

        self.assertEqual(apache_license.name, "Apache-2.0")
        self.assertEqual(show_license.name, "Show License")
        self.assertEqual(str(show_license.start), "2023-05-01T11:31:46.258000")
        self.assertEqual(str(show_license.finish), "2030-05-01T11:31:46.258000")
        self.assertEqual(str(john_license.date), "2015-05-01T11:31:00")
        self.assertEqual(john_license.externals, ["0123456789"])
        self.assertEqual(ml_license.jurisdictions[0].name, "US/LA")

        # Setup a CSV dataset
        db = rmtc_sys.track.open()
        dataset = rmtc.track.entities.Dataset(
            name="Show Training Data",
            uri=URI("file://localhost/show_dataset.csv"),
        )
        db.create([dataset])
        dataset.licenses.append(show_license)
        dataset.licenses.append(ml_license)
        dataset.licenses.append(john_license)
        db.update([dataset])

        # Create a generic torch model
        foundation_model = rmtc.track.entities.Model(
            name="Foundation Model",
            uri=URI("https://github.com/foundataional_model"),
            author="Big Tech",
        )
        model = rmtc.track.entities.Model(
            name="Refined Model",
            uri=URI("file://localhost/torch_model.pth"),
            author="Jane Smith",
        )

        # Create a specific ONNX model
        onnx_model = rmtc.track.entities.Model(
            name="ONNX Model",
            uri=URI("file://localhost/onnx_model.onnx"),
        )
        db.create([foundation_model, model, onnx_model])

        # Connect all up
        model.add_ancestors([foundation_model])
        model.licenses.append(apache_license)
        model.dataset = dataset
        model.variants.append(onnx_model)

        # Push it
        db.update([model])
        db.close()

        db = rmtc_sys.track.open()
        refined_model = db.fetch(db.queries.get_models("Refined Model"))[0]
        db.sync([refined_model])
        db.sync(
            refined_model.ancestors
            + [refined_model.dataset]
            + refined_model.licenses
            + refined_model.variants
        )
        db.close()

        self.assertEqual(refined_model.ancestors[0].name, "Foundation Model")
        self.assertEqual(refined_model.dataset.name, "Show Training Data")
        self.assertEqual(refined_model.licenses[0].name, "Apache-2.0")
        self.assertEqual(refined_model.variants[0].name, "ONNX Model")
        self.assertEqual(
            str(refined_model.variants[0].uri), "file://localhost/onnx_model.onnx"
        )

        # Create training run

        # Clear and reopen
        rmtc_sys.clear()
        db = rmtc_sys.track.open()

        # Get model and dataset
        model_ids = db.queries.get_models("Refined Model")
        model = db.fetch(model_ids)[0]
        dataset_ids = db.queries.get_datasets("Show Training Data")
        dataset = db.fetch(dataset_ids)[0]

        db.sync([model, dataset])

        # Create solution
        solution = rmtc.track.entities.Solution(name="Test Solution")

        # Create run
        run = rmtc.track.entities.Run(
            name="Test Run 1",
        )
        run.model = model
        run.metric = 0.001
        run.dataset = dataset
        run.model = model
        run.status = Status.FINISHED
        run.solution = solution

        # Push
        entities = [solution, run]
        db.create(entities)
        db.update(entities)
        db.close()

        db = rmtc_sys.track.open()
        test_run = db.fetch(db.queries.get_runs())[0]
        db.sync([test_run])
        db.sync(
            [
                test_run.model,
                test_run.dataset,
            ]
        )
        db.close()

        self.assertEqual(test_run.model.name, "Refined Model")
        self.assertEqual(test_run.dataset.name, "Show Training Data")

        # Best run

        # clear and reopen
        rmtc_sys.clear()
        db = rmtc_sys.track.open()

        # get best run
        solution_ids = db.queries.get_solutions("Test Solution")
        self.assertTrue(len(solution_ids) > 0) 
        solution = db.fetch(solution_ids)[0]
        db.sync([solution])
        run_id = db.queries.get_best_run(solution)
        self.assertTrue(run_id is not None)         
        run = db.fetch([run_id])[0]
        self.assertTrue(run is not None)        
        db.sync([run, run.model])
        db.close()

        self.assertEqual(run.model.name, "Refined Model")

    def test_delete_entity(self):
        """Test deleting a single entity"""

        rmtc_sys = self.get_system()

        # Create licenses
        mit_license = community_licenses.OSS(
            "MIT",
            uri=URI("https://opensource.org/license/mit"),
            parties=[rmtc_sys.get_create(Party, name="Massachusetts Institute of Technology")],
        )
        apache1_license = community_licenses.OSS(
            "Apache-1.0",
            uri=URI("https://www.apache.org/licenses/LICENSE-1.0.html"),
            parties=[rmtc_sys.get_create(Party, name="Mozilla Foundation")], 
        )

        # Push to the database
        db = rmtc_sys.track.open()
        db.create([mit_license, apache1_license])
        db.update([mit_license, apache1_license])
        db.close()

        # Pull from the database
        db = rmtc_sys.track.open()
        license_id = db.queries.get_licenses("MIT")[0]
        mit_licenses = db.fetch([license_id])
        db.sync(mit_licenses)
        self.assertNotEqual(mit_licenses, [])

        # Delete entity from the database
        db.delete_entities(mit_licenses)
        db.close()

        # Check entity no longer exists
        db = rmtc_sys.track.open()
        mit_license_ids = db.queries.get_licenses("MIT")
        self.assertEqual(mit_license_ids, [])
        db.close()

        # Ensure the other entity has not been deleted
        db = rmtc_sys.track.open()
        apache_license_ids = db.queries.get_licenses("Apache-1.0")
        self.assertNotEqual(apache_license_ids, [])
        db.close()
