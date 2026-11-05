# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import rmtc.ops.assets as assets
import rmtc.track.entities as entities
from rmtc.system import URI

from abstract_rmtc_test import AbstractRMTCTest


class TestIsTracked(AbstractRMTCTest):
    """Ensure is_tracked() correctly marks Ops assets as excluded from the store"""

    def test_entity_default_is_tracked(self):
        """Regular tracked entities (e.g. Dataset) should be tracked by default"""
        dataset = entities.Dataset(
            name="Some Dataset",
            uri=URI("file://localhost/dataset.csv"),
        )
        self.assertTrue(dataset.is_tracked())

    def test_ops_asset_is_not_tracked(self):
        """Ops assets should never be tracked - they are volatile training data"""
        value = assets.Value(value=10.0)
        self.assertFalse(value.is_tracked())

    def test_push_excludes_untracked_assets(self):
        """
        Pushing a Dataset with attached Ops assets should push the Dataset
        but must not push the (untracked) assets themselves.
        """
        rmtc_sys = self.get_system()

        dataset = entities.Dataset(
            name="Dataset With Assets",
            uri=URI("file://localhost/dataset_with_assets.csv"),
        )
        dataset.add_assets([assets.Value(value=float(i)) for i in range(10)])

        rmtc_sys.add_entities([dataset])
        rmtc_sys.push()

        # the dataset itself should have been pushed
        db = rmtc_sys.track.open()
        dataset_ids = db.queries.get_datasets("Dataset With Assets")
        self.assertEqual(len(dataset_ids), 1)

        # but none of the untracked assets should exist in the store
        result = db.read_query(
            "MATCH (a:Asset) WHERE a._store=$store RETURN count(a) AS c",
            store=db.store.name,
        )
        db.close()
        self.assertEqual(result[0]["c"], 0)
