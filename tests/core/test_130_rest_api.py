# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import json
import math
import unittest
from unittest.mock import patch

from rmtc.system import (
    URI,
    Datetime,
    Factory,
    Package,
    RMTCException,
    Type,
    Version,
)
from rmtc.system.objects import Objects, PropertyType, Unlocked
from rmtc.track.entities import (
    Asset,
    Checkpoint,
    License,
    LicenseStatus,
    Model,
    Party,
    Run,
)
from rmtc.track.store import Proxy
from rmtc.core.system.serializers.json import JSONSerializer
from rmtc.core.interface.rest.client import API_VERSION, Client

from abstract_rmtc_test import AbstractRMTCTest


CLIENT_MODULE = "rmtc.core.interface.rest.client"
PREFIX = f"/v{API_VERSION.major}"
FIXED_TIME = Datetime("2026-01-01T00:00:00+00:00")
CLIENT_URI = "http://rmtc.test"


def _pin(entity, obj_id):
    """Give an entity a fixed id and fixed timestamps so its JSON is stable"""
    entity.obj_id = obj_id
    for prop in entity.properties.values():
        if prop.prop_type == PropertyType.DATETIME and not prop.is_array():
            with Unlocked(prop):
                prop.value = FIXED_TIME


def _strict_loads(body):
    """Parse JSON, rejecting the non-standard NaN/Infinity constants"""

    def reject(constant):
        raise ValueError(f"Invalid JSON constant {constant}")

    return json.loads(body, parse_constant=reject)


class _Response:
    """Minimal stand-in for a requests.Response"""

    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


class TestJSONSerializer(unittest.TestCase):
    """
    The JSONSerializer's promises, in memory - no store, no HTTP.

    - Wire format: the exact JSON for a fixed set of entities, so encoding
      changes can't slip in without deciding on an API_VERSION bump.
    - Encoding: how each property type is written.
    - Round trips: what comes back from serialize -> deserialize, including
      the deliberate losses.
    - Identity: `objects` makes the same entity deserialize to the same
      object, and fills in stubs when the full entity arrives.
    - Lifecycle flags: deserialized entities have nothing to push.
    """

    @classmethod
    def setUpClass(cls):
        # type registrations come from RMTC_MODULES; no store is needed
        cls.factory = Factory()

    # helpers

    def _serializer(self):
        return JSONSerializer(self.factory, Objects())

    def _wire(self, entity):
        """The JSON dict for one entity"""
        return json.loads(self._serializer().serialize([entity]))[0]

    def _round_trip(self, entity):
        """Serialize, then deserialize with a fresh serializer"""
        return self._serializer().deserialize(self._serializer().serialize([entity]))[0]

    def _type_name(self, cls):
        return str(self.factory.resolve_inverse(cls))

    def _license(self, **kwargs):
        return License(
            name="Apache-2.0",
            uri=URI("https://www.apache.org/licenses/LICENSE-2.0.txt"),
            **kwargs,
        )

    def _model(self, **kwargs):
        return Model(
            name="Demo Model",
            uri=URI("https://github.com/example/demo_model"),
            **kwargs,
        )

    # wire format contract

    def test_wire_format_contract(self):
        """
        The JSON for a fixed set of entities must equal the expected list
        below. It covers every encoding rule: references, members, ENUM,
        TYPE, PACKAGE, URI, DATETIME, VERSION, empty arrays, unset
        references and a NaN metric. The response envelope is added by the
        Server and checked in TestRestServer (tests/server).
        """
        # the expected list below is the v1 contract
        self.assertEqual(
            API_VERSION.major,
            2,
            "API_VERSION changed - update the expected wire format in this test",
        )

        party = Party(name="Mozilla Foundation")
        license = self._license(status=LicenseStatus.ACTIVE, parties=[party])
        model = self._model(
            author="Movie Studio",
            licenses=[license],
            dependencies=[Package("torch-2.1.0")],
            input_types=[Type(type_class=Asset)],
        )
        checkpoint = Checkpoint(
            name="Epoch 1",
            uri=URI("https://github.com/example/demo_model/epoch_1"),
            epoch=1,
        )
        run = Run(name="Demo Run", model=model, metric=float("nan"))
        run.add_result_checkpoints([checkpoint])

        for index, entity in enumerate([party, license, model, checkpoint, run]):
            _pin(entity, f"00000000-0000-0000-0000-{index + 1:012d}")

        actual = _strict_loads(self._serializer().serialize([party, license, model, run]))

        time = "2026-01-01T00:00:00+00:00"
        party_ref = {
            "_id": "00000000-0000-0000-0000-000000000001",
            "_type_name": "rmtc_track.Party.Party-1.0.0",
            "name": "Mozilla Foundation",
        }
        license_ref = {
            "_id": "00000000-0000-0000-0000-000000000002",
            "_type_name": "rmtc_track.License.License-1.0.0",
            "name": "Apache-2.0",
        }
        model_ref = {
            "_id": "00000000-0000-0000-0000-000000000003",
            "_type_name": "rmtc_track.Model.Model-1.0.0",
            "name": "Demo Model",
        }
        expected = [
            {
                **party_ref,
                "active": True,
                "context": "",
                "externals": [],
                "instantiated_at": time,
            },
            {
                **license_ref,
                "active": True,
                "context": "",
                "date": time,
                "excludes": [],
                "explicit": False,
                "externals": [],
                "finish": time,
                "grants": [],
                "instantiated_at": time,
                "jurisdictions": [],
                "notes": [],
                "parties": [party_ref],
                "requires": [],
                "revoked": time,
                "start": time,
                "status": "ACTIVE",
                "uri": "https://www.apache.org/licenses/LICENSE-2.0.txt",
                "version": "1.0.0",
            },
            {
                **model_ref,
                "active": True,
                "ancestors": [],
                "author": "Movie Studio",
                "context": "",
                "dependencies": ["torch-2.1.0"],
                "externals": [],
                "input_names": [],
                "input_types": ["rmtc_track.Asset.TrackedAsset-1.0.0"],
                "instantiated_at": time,
                "licenses": [license_ref],
                "location": None,
                "metric": 1.0,
                "model_id": "",
                "origin": None,
                "output_names": [],
                "output_types": [],
                "solution": None,
                "tags": [],
                "uri": "https://github.com/example/demo_model",
                "variants": [],
                "version": "1.0.0",
            },
            {
                "_id": "00000000-0000-0000-0000-000000000005",
                "_type_name": "rmtc_track.Run.TrackedRun-1.0.0",
                "name": "Demo Run",
                "active": True,
                "checkpoint": None,
                "context": "",
                "dataset": None,
                "epochs": 0,
                "externals": [],
                "instantiated_at": time,
                "metric": None,
                "model": model_ref,
                "result_model": None,
                "result_checkpoints": [
                    {
                        "_id": "00000000-0000-0000-0000-000000000004",
                        "_type_name": "rmtc_track.Checkpoint.Checkpoint-1.0.0",
                        "name": "Epoch 1",
                        "active": True,
                        "ancestors": [],
                        "author": "",
                        "context": "",
                        "dependencies": [],
                        "epoch": 1,
                        "externals": [],
                        "instantiated_at": time,
                        "licenses": [],
                        "location": None,
                        "metric": 1.0,
                        "model": None,
                        "origin": None,
                        "solution": None,
                        "tags": [],
                        "uri": "https://github.com/example/demo_model/epoch_1",
                        "variants": [],
                        "version": "1.0.0",
                    }
                ],
                "result_weights": None,
                "solution": None,
                "test": None,
                "uri": "",
                "validation": None,
                "version": "1.0.0",
            },
        ]

        self.maxDiff = None
        self.assertEqual(
            actual,
            expected,
            "REST wire format changed. Decide whether this can break existing "
            "clients - if so, bump the API_VERSION major in client.py. Then "
            "update the expected list in this test.",
        )

    # encoding per type

    def test_reference_encoding(self):
        """A reference is {_id, _type_name, name}; an unset one is null"""
        license = self._license()
        wire = self._wire(self._model(licenses=[license]))
        self.assertEqual(
            wire["licenses"],
            [
                {
                    "_id": license.obj_id,
                    "_type_name": self._type_name(License),
                    "name": "Apache-2.0",
                }
            ],
        )
        self.assertIsNone(self._wire(Run(name="Run"))["model"])

    def test_member_encoding(self):
        """A member is a nested dict with its own _type_name"""
        run = Run(name="Run")
        run.add_result_checkpoints([Checkpoint(name="Epoch 1", epoch=1)])
        nested = self._wire(run)["result_checkpoints"]
        self.assertEqual(len(nested), 1)
        self.assertEqual(nested[0]["_type_name"], self._type_name(Checkpoint))
        self.assertEqual(nested[0]["name"], "Epoch 1")
        self.assertEqual(nested[0]["epoch"], 1)

    def test_value_encoding(self):
        """ENUM by name, TYPE by type name, URI/DATETIME/VERSION/PACKAGE as strings"""
        date = Datetime("2020-05-01T11:31:46.258000")
        license = self._license(status=LicenseStatus.REVOKED, date=date)
        model = self._model(
            version=Version("2.3.4"),
            dependencies=[Package("torch-2.1.0")],
            input_types=[Type(type_class=Asset)],
        )

        wire = self._wire(license)
        self.assertEqual(wire["status"], "REVOKED")
        self.assertEqual(wire["date"], str(date))
        self.assertEqual(wire["uri"], "https://www.apache.org/licenses/LICENSE-2.0.txt")

        wire = self._wire(model)
        self.assertEqual(wire["version"], "2.3.4")
        self.assertEqual(wire["dependencies"], ["torch-2.1.0"])
        self.assertEqual(wire["input_types"], [self._type_name(Asset)])
        self.assertEqual(wire["licenses"], [])

    def test_non_finite_floats_are_null(self):
        """NaN and +/-Infinity are sent as null, so the output is strict JSON"""
        runs = [Run(name=str(v), metric=float(v)) for v in ["nan", "inf", "-inf"]]
        payload = _strict_loads(self._serializer().serialize(runs))
        self.assertEqual([item["metric"] for item in payload], [None, None, None])

    # round trips

    def test_round_trip_values(self):
        """Every property type survives serialize -> deserialize"""
        date = Datetime("2020-05-01T11:31:46.258000")
        license = self._round_trip(
            self._license(status=LicenseStatus.REVOKED, date=date, explicit=True)
        )
        self.assertIsInstance(license, License)
        self.assertEqual(license.name, "Apache-2.0")  # STRING
        self.assertEqual(license.explicit, True)  # BOOLEAN
        self.assertEqual(license.status, LicenseStatus.REVOKED)  # ENUM
        self.assertEqual(license.date, date)  # DATETIME
        self.assertEqual(
            str(license.uri), "https://www.apache.org/licenses/LICENSE-2.0.txt"
        )  # URI

        model = self._round_trip(
            self._model(
                author="Movie Studio",
                version=Version("2.3.4"),
                dependencies=[Package("torch-2.1.0")],
                input_types=[Type(type_class=Asset)],
            )
        )
        self.assertEqual(model.author, "Movie Studio")
        self.assertEqual(model.version, Version("2.3.4"))  # VERSION
        self.assertEqual([str(p) for p in model.dependencies], ["torch-2.1.0"])  # PACKAGE
        self.assertEqual(len(model.input_types), 1)  # TYPE
        self.assertIs(model.input_types[0].type_class, Asset)

        checkpoint = self._round_trip(Checkpoint(name="Epoch 7", epoch=7, metric=0.25))
        self.assertEqual(checkpoint.epoch, 7)  # INTEGER
        self.assertEqual(checkpoint.metric, 0.25)  # NUMBER

    def test_round_trip_objects(self):
        """References come back with id and name; members come back whole"""
        license = self._license()
        model = self._round_trip(self._model(licenses=[license]))
        self.assertEqual(len(model.licenses), 1)
        self.assertIsInstance(model.licenses[0], License)
        self.assertEqual(model.licenses[0].obj_id, license.obj_id)
        self.assertEqual(model.licenses[0].name, "Apache-2.0")

        checkpoint = Checkpoint(name="Epoch 1", epoch=1)
        run = Run(name="Run")
        run.add_result_checkpoints([checkpoint])
        run = self._round_trip(run)
        self.assertEqual(len(run.result_checkpoints), 1)
        rebuilt = run.result_checkpoints[0]
        self.assertIsInstance(rebuilt, Checkpoint)
        self.assertEqual(rebuilt.obj_id, checkpoint.obj_id)
        self.assertEqual(rebuilt.epoch, 1)

    def test_deliberate_losses(self):
        """
        Two known losses: Infinity comes back as NaN (both are sent as null),
        and custom properties added at runtime are dropped.
        """
        run = self._round_trip(Run(name="Run", metric=float("inf")))
        self.assertTrue(math.isnan(run.metric))

        model = self._model()
        model.add_property("custom_note", str, value="hello")
        self.assertEqual(self._wire(model)["custom_note"], "hello")
        self.assertNotIn("custom_note", self._round_trip(model).properties)

    # identity

    def test_same_entity_twice_is_same_object(self):
        """Deserializing the same entity twice returns the same Python object"""
        serializer = self._serializer()
        body = self._serializer().serialize([self._model()])
        self.assertIs(serializer.deserialize(body)[0], serializer.deserialize(body)[0])

    def test_reference_to_loaded_entity_resolves(self):
        """A reference to an already-deserialized entity resolves to that object"""
        license = self._license()
        model = self._model(licenses=[license])
        serializer = self._serializer()

        client_license = serializer.deserialize(self._serializer().serialize([license]))[0]
        client_model = serializer.deserialize(self._serializer().serialize([model]))[0]
        self.assertIs(client_model.licenses[0], client_license)

    def test_stub_filled_in_by_full_entity(self):
        """A stub is filled in, in place, when the full entity arrives later"""
        license = self._license(status=LicenseStatus.REVOKED)
        model = self._model(licenses=[license])
        serializer = self._serializer()

        client_model = serializer.deserialize(self._serializer().serialize([model]))[0]
        stub = client_model.licenses[0]
        self.assertEqual(str(stub.uri), "")

        client_license = serializer.deserialize(self._serializer().serialize([license]))[0]
        self.assertIs(client_license, stub)
        self.assertEqual(
            str(stub.uri), "https://www.apache.org/licenses/LICENSE-2.0.txt"
        )
        self.assertEqual(stub.status, LicenseStatus.REVOKED)
        self.assertFalse(stub.requires_sync())

    # lifecycle flags

    def test_full_entity_is_clean(self):
        """A fully deserialized entity and its members have no flags set"""
        run = Run(name="Run")
        run.add_result_checkpoints([Checkpoint(name="Epoch 1", epoch=1)])
        run = self._round_trip(run)
        for entity in [run, run.result_checkpoints[0]]:
            self.assertFalse(entity.requires_create())
            self.assertFalse(entity.requires_update())
            self.assertFalse(entity.requires_sync())

    def test_unloaded_reference_is_stub(self):
        """
        A reference to an entity not yet loaded becomes a stub: the right
        type, id and name, marked as needing a sync, not new and not dirty.
        """
        license = self._license()
        stub = self._round_trip(self._model(licenses=[license])).licenses[0]
        self.assertIsInstance(stub, License)
        self.assertEqual(stub.obj_id, license.obj_id)
        self.assertEqual(stub.name, "Apache-2.0")
        self.assertTrue(stub.requires_sync())
        self.assertFalse(stub.requires_create())
        self.assertFalse(stub.requires_update())

    def test_unknown_type_becomes_proxy(self):
        """An unregistered type name falls back to a Proxy, as the store does"""
        body = json.dumps(
            [
                {
                    "_id": "00000000-0000-0000-0000-000000000009",
                    "_type_name": "rmtc_track.Unknown.Unknown-1.0.0",
                    "name": "Mystery",
                }
            ]
        )
        entity = self._serializer().deserialize(body)[0]
        self.assertIsInstance(entity, Proxy)
        self.assertEqual(entity.obj_id, "00000000-0000-0000-0000-000000000009")
        self.assertEqual(entity.name, "Mystery")


class TestRestClient(AbstractRMTCTest):
    """
    The Client's promises on its own: it sends the right request, and turns
    errors into exceptions.

    `requests.get` is patched to capture the request and return a canned
    response. No socket is opened. That the Client and Server agree is
    checked with the server, in tests/server.
    """

    def _canned(self, status_code, text):
        """Patch requests.get to return a fixed response"""
        return patch(
            f"{CLIENT_MODULE}.requests.get", return_value=_Response(status_code, text)
        )

    def _client(self, uri=CLIENT_URI):
        return Client(uri, rmtc_system=self.get_system())

    # request

    def test_request_url_and_params(self):
        """The Client calls {uri}/v<major>/<resource>; limit is only sent if given"""
        body = json.dumps({"results": []})
        for uri in [CLIENT_URI, CLIENT_URI + "/", URI(CLIENT_URI)]:
            with self.subTest(uri=uri):
                with self._canned(200, body) as get:
                    client = self._client(uri)
                    client.get_models("Any")
                    client.get_entities("Any", limit=3)

                urls = [call.args[0] for call in get.call_args_list]
                params = [call.kwargs["params"] for call in get.call_args_list]
                self.assertEqual(
                    urls, [f"{CLIENT_URI}{PREFIX}/models", f"{CLIENT_URI}{PREFIX}/entities"]
                )
                self.assertEqual(params, [{"name": "Any"}, {"name": "Any", "limit": 3}])

    # errors

    def test_error_raises(self):
        """A non-200 response raises with the status and server message"""
        for status, message in [(400, "Missing name"), (500, "Internal server error")]:
            with self.subTest(status=status):
                with self._canned(status, json.dumps({"error": message})):
                    with self.assertRaises(RMTCException) as context:
                        self._client().get_models("Any")
                self.assertIn(str(status), str(context.exception))
                self.assertIn(message, str(context.exception))

    def test_no_match_is_empty_list(self):
        """No match returns [], which is distinct from an error"""
        with self._canned(200, json.dumps({"results": []})):
            self.assertEqual(self._client().get_models("Does Not Exist"), [])
