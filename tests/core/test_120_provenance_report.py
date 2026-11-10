# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import rmtc.track
from rmtc.system import URI, Datetime
from rmtc.ops.scheduling import Status

import rmtc.core.track.tracing.reports as text_reports
import rmtc.core.track.entities.licenses.community as community_licenses
import rmtc.core.track.entities.licenses.commercial as commercial_licenses
from rmtc.track.entities import Party, Jurisdiction
from abstract_rmtc_test import AbstractRMTCTest


def get_categories(node, category):
    """Recursively get child node(s) which match the given entity type"""
    entities = []
    if node[0].class_category == category:
        entities.append(node[0])
    for child in node[1]:
        entities.extend(get_categories(child, category))
    return entities


def populate_store(rmtc_sys, include_unnamed_license=False):
    # Create licenses
    ml_license = commercial_licenses.Agreement(
        "Example ML License",
        parties=[
            rmtc_sys.get_create(Party, name="VFX Facility"),
            rmtc_sys.get_create(Party, name="Production Facility")],
        date=Datetime("2020-05-01T11:31:46.258000"),
        uri=URI("sharepoint://documents/ml_training_agreement.pdf"),
    )
    apache_license = community_licenses.OSS(
        "Apache-2.0",
        uri=URI("https://apache.org/licenses/LICENSE-2.0.html"),
        parties=[rmtc_sys.get_create(Party, name="Mozilla Foundation")], 
    )
    show_license = commercial_licenses.Show(
        "Show License",
        parties=[
            rmtc_sys.get_create(Party, name="Production Facility")
        ],
        start=Datetime("2023-05-01T11:31:46.258000"),
        finish=Datetime("2030-05-01T11:31:46.258000"),
    )
    actor_license = commercial_licenses.Agreement(
        "John Smith Likeness",
        parties=[
            rmtc_sys.get_create(Party, name="John Smith"), 
            rmtc_sys.get_create(Party, name="Production Company")
        ],
        date=Datetime("2015-05-01T11:31:46.258000"),
        uri=URI("ftp://production_company.com/documents/likeness_agreement.pdf"),
    )

    db = rmtc_sys.track.open()
    db.create([apache_license, show_license, ml_license, actor_license])
    db.update([apache_license, show_license, ml_license, actor_license])

    # Create a dataset
    dataset = rmtc.track.entities.Dataset(
        name="Show Training Data",
        uri=URI("file://localhost/show_dataset.csv"),
    )
    db.create([dataset])
    dataset.licenses.append(show_license)
    dataset.licenses.append(ml_license)
    dataset.licenses.append(actor_license)
    db.update([dataset])

    # Create models
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
    db.create([foundation_model, model])
    db.update([foundation_model, model])

    # Connect all up
    model.add_ancestors([foundation_model])
    model.licenses.append(apache_license)
    if include_unnamed_license:
        unnamed_license = community_licenses.OSS(
            "",
            uri=URI("https://example.com/unnamed_license.html"),
        )
        db.create([unnamed_license])
        model.licenses.append(unnamed_license)
    db.update([model])

    # Create run & solution
    solution = rmtc.track.entities.Solution(name="Test")
    run = rmtc.track.entities.Run(
        name="Test Run 1",
        model=model,
        dataset=dataset,
        solution=solution,
    )
    run.status = Status.FINISHED

    # Push
    db.create([solution, run])
    db.update([solution, run])
    db.close()


class TestProvenanceReport(AbstractRMTCTest):
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

    def test_report_formatting(self):
        """Test markdown report structure with unnamed entities in the source tree"""

        rmtc_sys = self.get_system()

        populate_store(rmtc_sys, include_unnamed_license=True)

        solutions = rmtc_sys.get_solutions("Test")
        run = rmtc_sys.get_best_run(solutions[0])
        report = text_reports.MarkdownReport(rmtc_system=rmtc_sys)
        markdown = report([run])
        lines = markdown.splitlines()

        # no bullet is empty (empty bullets corrupt Qt's markdown rendering)
        for line in lines:
            self.assertNotEqual(line.strip(), "*")

        # every heading and rule is preceded by a blank line
        for i, line in enumerate(lines):
            if i > 0 and line.startswith(("#", "---")):
                self.assertEqual(lines[i - 1], "")

        # unnamed entities render with a placeholder
        self.assertIn("* (unnamed License)", markdown)

        # named entities render unchanged
        self.assertIn("## Test Run 1 (Run)", markdown)
        self.assertIn("* Apache-2.0", markdown)
