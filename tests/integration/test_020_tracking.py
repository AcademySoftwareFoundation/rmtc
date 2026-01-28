# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import rmtc_core.track.licenses.community as community_licenses
import rmtc_core.track.licenses.commercial as commercial_licenses
import rmtc.track
from rmtc.system import URI, Datetime

from .abstract_rmtc_integration_test import AbstractRMTCIntegrationTest


class TestTracking(AbstractRMTCIntegrationTest):
    """Ensure RMTC tracking is working as expected"""

    def test_create_entity(self):
        """Test creating a single entity"""
        # Create a license
        name = "Apache-1.0"
        uri = URI("https://www.apache.org/licenses/LICENSE-1.0.html")
        parties = ["Mozilla Foundation"]
        apache1_license = community_licenses.OSS(
            name,
            uri=uri,
            parties=parties,
        )

        # Push to the database
        db = self.get_system().open()
        db.create([apache1_license])
        db.update([apache1_license])
        db.close()

        # Pull from the database
        db = self.get_system().open()
        license_id = db.queries.get_licenses(name)[0]
        apache_licenses = db.fetch([license_id])
        self.assertNotEqual(apache_licenses, [])
        db.sync(apache_licenses)
        db.close()

        apache_license = apache_licenses[0]
        self.assertEqual(apache_license.properties.get("uri").value, uri)
        self.assertEqual(apache_license.properties.get("parties").value, parties)

    def test_create_models_licenses(self):
        """Test tracking for models, licenses and datasets"""

        rmtc_sys = self.get_system()

        # Create licenses
        ml_license = commercial_licenses.Agreement(
            "Example ML License",
            parties=["VFX Facility", "Production Facility"],
            place="LA, USA",
            date=Datetime("2020-05-01T11:31:46.258000"),
            start=Datetime("2020-05-01T11:31:46.258000"),
            finish=Datetime("2024-05-01T11:31:46.258000"),
            uri=URI("sharepoint://documents/ml_training_agreement.pdf"),
            reference="0123456789",
        )
        apache2_license = community_licenses.OSS(
            "Apache-2.0",
            uri=URI("https://apache.org/licenses/LICENSE-2.0.html"),
            parties=["Mozilla Foundation"],
        )
        show_license = commercial_licenses.Show(
            "Show License",
            parties=["Production Facility"],
            start=Datetime("2023-05-01T11:31:46.258000"),
            finish=Datetime("2030-05-01T11:31:46.258000"),
        )
        actor_license = commercial_licenses.Agreement(
            "John Smith Likeness",
            parties=["John Smith", "Production Company"],
            date=Datetime("2015-05-01T11:31:46.258000"),
            place="Los Angeles County, USA",
            start=Datetime("2020-05-01T11:31:46.258000"),
            finish=Datetime("2030-05-01T11:31:46.258000"),
            uri=URI("ftp://production_company.com/documents/likeness_agreement.pdf"),
            reference="0123456789",
        )

        # Update with some notes
        notes = [
            "Must not be used in a context that may damage reputation",
            "Only used for facial swap training",
        ]
        for note in notes:
            actor_license.notes.append(note)

        # Add to the Objects
        db = rmtc_sys.open()
        db.create([apache2_license, show_license, ml_license, actor_license])
        db.update([apache2_license, show_license, ml_license, actor_license])
        db.close()

        # Fetch our created license via the DB
        db = rmtc_sys.open()
        license_id = db.queries.get_licenses("John Smith Likeness")[0]
        actor_licenses = db.fetch([license_id])
        self.assertNotEqual(actor_licenses, [])
        actor_license = actor_licenses[0]
        db.sync([actor_license])
        db.close()
        self.assertEqual(actor_license.properties.get("notes").value, notes)

        # Find the licenses
        db = rmtc_sys.open()
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
        self.assertEqual(str(john_license.date), "2015-05-01T11:31:46.258000")
        self.assertEqual(john_license.reference, "0123456789")
        self.assertEqual(ml_license.jurisdiction, "LA, USA")

        # Setup a CSV dataset
        db = rmtc_sys.open()
        dataset = rmtc.track.Dataset(
            name="Show Training Data",
            uri=URI("file://localhost/show_dataset.csv"),
        )
        db.create([dataset])
        dataset.licenses.append(show_license)
        dataset.licenses.append(ml_license)
        dataset.licenses.append(john_license)
        db.update([dataset])

        # Create a generic torch model
        foundation_model = rmtc.track.Model(
            name="Foundation Model",
            uri=URI("https://github.com/foundataional_model"),
            author="Big Tech",
        )
        model = rmtc.track.Model(
            name="Refined Model",
            uri=URI("file://localhost/torch_model.pth"),
            author="Jane Smith",
        )

        # Create a specific ONNX model
        onnx_model = rmtc.track.Model(
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

        db = rmtc_sys.open()
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
        db = rmtc_sys.open()

        # Get model and dataset
        model_ids = db.queries.get_models("Refined Model")
        model = db.fetch(model_ids)[0]
        dataset_ids = db.queries.get_datasets("Show Training Data")
        dataset = db.fetch(dataset_ids)[0]

        db.sync([model, dataset])

        # Create trainer
        trainer = rmtc.track.Trainer(batch_size=5, epochs=5)

        # Create solution
        solution = rmtc.track.Solution(name="Test Solution")
        solution.models.append(model)
        solution.datasets.append(dataset)

        # Create run
        run = rmtc.track.Run(
            name="Test Run 1",
        )
        run.trainer = trainer
        run.model = model
        run.dataset = dataset
        run.model = model
        run.status = rmtc.track.RunStatus.FINISHED
        run.solution = solution

        # Push
        entities = [solution, trainer, run, ]
        db.create(entities)
        db.update(entities)
        db.close()

        db = rmtc_sys.open()
        test_run = db.fetch(db.queries.get_runs(trainer=trainer))[0]
        db.sync([test_run])
        db.sync(
            [
                test_run.trainer,
                test_run.model,
                test_run.dataset,
            ]
        )
        db.close()

        self.assertEqual(test_run.trainer.batch_size, 5)
        self.assertEqual(test_run.model.name, "Refined Model")
        self.assertEqual(test_run.dataset.name, "Show Training Data")

        # Best run

        # clear and reopen
        rmtc_sys.clear()
        db = rmtc_sys.open()

        # get best run
        solution_ids = db.queries.get_solutions("Test Solution")
        solution = db.fetch(solution_ids)[0]
        db.sync([solution])
        run = rmtc_sys.get_best_run(solution)
        db.sync([run, run.trainer, run.model])
        db.close()

        self.assertEqual(run.trainer.epochs, 5)
        self.assertEqual(run.model.name, "Refined Model")

    def test_delete_entity(self):
        """Test deleting a single entity"""

        rmtc_sys = self.get_system()

        # Create licenses
        mit_license = community_licenses.OSS(
            "MIT",
            uri=URI("https://opensource.org/license/mit"),
            parties=["Massachusetts Institute of Technology"],
        )
        apache1_license = community_licenses.OSS(
            "Apache-1.0",
            uri=URI("https://www.apache.org/licenses/LICENSE-1.0.html"),
            parties=["Mozilla Foundation"],
        )

        # Push to the database
        db = rmtc_sys.open()
        db.create([mit_license, apache1_license])
        db.update([mit_license, apache1_license])
        db.close()

        # Pull from the database
        db = rmtc_sys.open()
        license_id = db.queries.get_licenses("MIT")[0]
        mit_licenses = db.fetch([license_id])
        db.sync(mit_licenses)
        self.assertNotEqual(mit_licenses, [])

        # Delete entity from the database
        db.delete_entities(mit_licenses)
        db.close()

        # Check entity no longer exists
        db = rmtc_sys.open()
        mit_license_ids = db.queries.get_licenses("MIT")
        self.assertEqual(mit_license_ids, [])
        db.close()

        # Ensure the other entity has not been deleted
        db = rmtc_sys.open()
        apache_license_ids = db.queries.get_licenses("Apache-1.0")
        self.assertNotEqual(apache_license_ids, [])
        db.close()
