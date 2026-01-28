# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import rmtc.track
from rmtc.system import URI, Datetime

import rmtc_core.track.licenses.community as community_licenses
import rmtc_core.track.licenses.commercial as commercial_licenses

from .abstract_rmtc_integration_test import AbstractRMTCIntegrationTest


def get_categories(node, category):
    """Recursively get child node(s) which match the given entity type"""
    entities = []
    if node[0].class_category == category:
        entities.append(node[0])
    for child in node[1]:
        entities.extend(get_categories(child, category))
    return entities


def populate_store(rmtc_sys):

    # Create licenses
    ml_license = commercial_licenses.Agreement(
        "Example ML License",
        parties=["VFX Facility", "Production Facility"],
        date=Datetime("2020-05-01T11:31:46.258000"),
        uri=URI("sharepoint://documents/ml_training_agreement.pdf"),
    )
    apache_license = community_licenses.OSS(
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
        uri=URI("ftp://production_company.com/documents/likeness_agreement.pdf"),
    )

    db = rmtc_sys.open()
    db.create([apache_license, show_license, ml_license, actor_license])
    db.update([apache_license, show_license, ml_license, actor_license])

    # Create a dataset
    dataset = rmtc.track.Dataset(
        name="Show Training Data",
        uri=URI("file://localhost/show_dataset.csv"),
    )
    db.create([dataset])
    dataset.licenses.append(show_license)
    dataset.licenses.append(ml_license)
    dataset.licenses.append(actor_license)
    db.update([dataset])

    # Create models
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
    db.create([foundation_model, model])
    db.update([foundation_model, model])

    # Connect all up
    model.add_ancestors([foundation_model])
    model.licenses.append(apache_license)
    db.update([model])

    # Create trainer
    trainer = rmtc.track.Trainer(batch_size=5, epochs=5)
    db.create([trainer])
    db.update([trainer])

    # Create run & solution
    solution = rmtc.track.Solution(name="Test Solution")

    solution.models.append(model)
    run = rmtc.track.Run(
        name="Test Run 1",
        trainer=trainer,
        model=model,
        dataset=dataset,
        solution=solution,
    )
    run.status = rmtc.track.RunStatus.FINISHED

    # Push
    db.create([solution, run])
    db.update([solution, run])
    db.close()


class TestProvenanceReport(AbstractRMTCIntegrationTest):
    """Test provenance"""

    def test_sources(self):
        """Test sources"""

        rmtc_sys = self.get_system()

        populate_store(rmtc_sys)

        # Check provenance
        solutions = rmtc_sys.get_solutions("Test")
        solution = solutions[0]
        self.assertTrue(solution is not None)
        run = rmtc_sys.get_best_run(solution)
        self.assertTrue(run is not None)
        sources = rmtc_sys.trace_sources(run)

        self.assertEqual(
            sorted(set([m.name for m in get_categories(sources, "Dataset")])),
            sorted(["Show Training Data"]),
        )
        self.assertEqual(
            sorted(set([m.name for m in get_categories(sources, "Model")])),
            sorted(
                [
                    "Refined Model",
                    "Foundation Model",
                ]
            ),
        )
        self.assertEqual(
            sorted(set([l.name for l in get_categories(sources, "License")])),
            sorted(
                [
                    "Example ML License",
                    "Apache-2.0",
                    "Show License",
                    "John Smith Likeness",
                ]
            ),
        )
