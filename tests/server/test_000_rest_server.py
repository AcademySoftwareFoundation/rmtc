# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import json
from unittest.mock import patch

from flask import Flask

from rmtc.system import URI, Logger
from rmtc.track.entities import License, LicenseStatus, Model
from rmtc_server.app import MAX_LIMIT, Server
from rmtc.core.interface.rest.client import API_VERSION, Client

from abstract_rmtc_test import AbstractRMTCTest


CLIENT_MODULE = "rmtc.core.interface.rest.client"
QUERIES_CLASS = "rmtc.core.track.store.cypher.connection.CypherQueries"
PREFIX = f"/v{API_VERSION.major}"
CLIENT_URI = "http://rmtc.test"


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


def _route_requests_to(test_client):
    """Build a fake requests.get that sends Client calls to a Flask test client"""

    def fake_get(url, params=None, timeout=None):
        path = "/" + url.split("://", 1)[1].split("/", 1)[1]
        response = test_client.get(path, query_string=params)
        return _Response(response.status_code, response.get_data(as_text=True))

    return fake_get


def _push_model(rmtc_sys, name, **kwargs):
    """Create a Model and push it to the store"""
    model = rmtc_sys.create_model(
        Model,
        name=name,
        uri=URI("https://github.com/example/model"),
        **kwargs,
    )
    rmtc_sys.push()
    return model




class TestRestServer(AbstractRMTCTest):
    """
    The Server's promises, through Flask's in-process test client (no
    socket) against a real store.

    Each Server is built from its own System, so responses read from the
    store rather than from the cache of the System that pushed the data.
    """

    # helpers

    def _server(self, cors_origin=None):
        return Server(self.get_system(), cors_origin=cors_origin)

    def _test_client(self, cors_origin=None):
        return self._server(cors_origin=cors_origin)._flask.test_client()

    def _get(self, test_client, resource, **params):
        return test_client.get(f"{PREFIX}/{resource}", query_string=params)

    def _results(self, test_client, resource, **params):
        """GET a resource, check it succeeded, and return its results list"""
        response = self._get(test_client, resource, **params)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return _strict_loads(response.get_data(as_text=True))["results"]

    def _assert_json_error(self, response, status):
        self.assertEqual(response.status_code, status, response.get_data(as_text=True))
        self.assertEqual(list(response.get_json().keys()), ["error"])

    # routes

    def _push_license_and_model(self, name):
        """Push a License and a Model that share a name"""
        rmtc_sys = self.get_system()
        rmtc_sys.create_license(License, name=name)
        rmtc_sys.create_model(Model, name=name, uri=URI("https://github.com/example/model"))
        rmtc_sys.push()
        return rmtc_sys
    
    def test_models_route_returns_only_models(self):
        """/models filters by category; a License with the same name is left out"""
        rmtc_sys = self._push_license_and_model("Shared Name")
        test_client = self._test_client()

        self.assertEqual(len(self._results(test_client, "entities", name="Shared Name")), 2)

        results = self._results(test_client, "models", name="Shared Name")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["_type_name"], str(rmtc_sys.factory.resolve_inverse(Model)))

    def test_entities_route_returns_any_category(self):
        """/entities matches by name across categories"""
        rmtc_sys = self._push_license_and_model("Shared Name")

        results = self._results(self._test_client(), "entities", name="Shared Name")
        type_names = sorted(result["_type_name"] for result in results)
        self.assertEqual(
            type_names,
            sorted(str(rmtc_sys.factory.resolve_inverse(c)) for c in [License, Model]),
        )

    def test_unprefixed_route_is_404(self):
        """Routes live under /v<major>; unprefixed routes are a JSON 404"""
        response = self._test_client().get("/models", query_string={"name": "Any"})
        self._assert_json_error(response, 404)

    def test_post_is_405(self):
        """The API is read only; other methods are a JSON 405"""
        response = self._test_client().post(f"{PREFIX}/models", query_string={"name": "Any"})
        self._assert_json_error(response, 405)

    # envelope

    def test_response_envelope(self):
        """The body is exactly {"results": [...]}"""
        _push_model(self.get_system(), "Envelope Model")
        response = self._get(self._test_client(), "models", name="Envelope Model")
        payload = response.get_json()
        self.assertEqual(list(payload.keys()), ["results"])
        self.assertEqual(len(payload["results"]), 1)

    def test_no_match_is_empty_results(self):
        """An unmatched name is a 200 with empty results, not an error"""
        response = self._get(self._test_client(), "entities", name="Does Not Exist")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"results": []})

    # request validation

    def test_missing_name_is_400(self):
        """A request without ?name= is a JSON 400"""
        test_client = self._test_client()
        self._assert_json_error(self._get(test_client, "models"), 400)
        self._assert_json_error(self._get(test_client, "models", name=""), 400)

    def test_limit_default(self):
        """Without ?limit= the store's configured limit applies"""
        rmtc_sys = self.get_system()
        limit = rmtc_sys.track.store.limit
        for _ in range(limit + 1):
            rmtc_sys.create_model(
                Model, name="Limit Model", uri=URI("https://github.com/example/model")
            )
        rmtc_sys.push()

        results = self._results(self._test_client(), "models", name="Limit Model")
        self.assertEqual(len(results), limit)

    def test_limit_explicit_newest_first(self):
        """?limit=2 returns the two newest matches, newest first"""
        rmtc_sys = self.get_system()
        for index in range(3):
            rmtc_sys.create_model(
                Model,
                name="Newest Model",
                uri=URI("https://github.com/example/model"),
                author=str(index),
            )
        rmtc_sys.push()

        results = self._results(self._test_client(), "models", name="Newest Model", limit=2)
        self.assertEqual([result["author"] for result in results], ["2", "1"])

    def test_limit_invalid_is_400(self):
        """Non-integer, zero, over-cap and non-ASCII digit limits are a JSON 400"""
        test_client = self._test_client()
        for limit in ["abc", "0", "-1", "1.5", str(MAX_LIMIT + 1), "²"]:
            with self.subTest(limit=limit):
                response = self._get(test_client, "models", name="Any", limit=limit)
                self._assert_json_error(response, 400)

    # store reads

    def test_server_reflects_store_changes(self):
        """An edit pushed by another System appears in the next response"""
        _push_model(self.get_system(), "Edited Model", author="Before")
        test_client = self._test_client()
        self.assertEqual(
            self._results(test_client, "models", name="Edited Model")[0]["author"], "Before"
        )

        editor_sys = self.get_system()
        editor_sys.get_models(name="Edited Model")[0].author = "After"
        editor_sys.push()

        self.assertEqual(
            self._results(test_client, "models", name="Edited Model")[0]["author"], "After"
        )

    def test_reference_name_from_store(self):
        """A reference carries the referenced entity's name, read from the store"""
        rmtc_sys = self.get_system()
        license = rmtc_sys.create_license(License, name="Ref License")
        _push_model(rmtc_sys, "Ref Model", licenses=[license])

        results = self._results(self._test_client(), "models", name="Ref Model")
        self.assertEqual(
            results[0]["licenses"],
            [
                {
                    "_id": license.obj_id,
                    "_type_name": str(rmtc_sys.factory.resolve_inverse(License)),
                    "name": "Ref License",
                }
            ],
        )

    def test_member_checkpoints_nested(self):
        """A Run's member Checkpoints are synced from the store and sent inline"""
        rmtc_sys = self.get_system()
        checkpoint = rmtc_sys.create_checkpoint(name="Epoch 1", epoch=1)
        run = rmtc_sys.create_run(name="Member Run")
        run.add_result_checkpoints([checkpoint])
        rmtc_sys.push()

        nested = self._results(self._test_client(), "entities", name="Member Run")[0][
            "result_checkpoints"
        ]
        self.assertEqual(len(nested), 1)
        self.assertEqual(nested[0]["_id"], checkpoint.obj_id)
        self.assertEqual(nested[0]["name"], "Epoch 1")
        self.assertEqual(nested[0]["epoch"], 1)

    def test_url_encoded_name(self):
        """A name with spaces and & is found when sent URL-encoded, as a browser would"""
        _push_model(self.get_system(), "Foo & Bar v2")
        response = self._test_client().get(f"{PREFIX}/models?name=Foo%20%26%20Bar%20v2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [result["name"] for result in response.get_json()["results"]], ["Foo & Bar v2"]
        )

    # errors

    def test_500_hides_and_logs_internals(self):
        """
        An unexpected error is a generic JSON 500 without the exception text,
        and the full error is logged on the server.
        """
        test_client = self._test_client()
        with patch(f"{QUERIES_CLASS}.get_models", side_effect=RuntimeError("secret")):
            with patch.object(Logger, "error") as log_error:
                response = self._get(test_client, "models", name="Any")

        self._assert_json_error(response, 500)
        self.assertNotIn("secret", response.get_data(as_text=True))
        logged = " ".join(str(call.args[0]) for call in log_error.call_args_list)
        self.assertIn("secret", logged)

    # headers

    def test_headers_on_every_response(self):
        """200, 400, 404 and 500 responses are all no-store cache control and JSON mimetype"""
        test_client = self._test_client()
        responses = {
            200: self._get(test_client, "models", name="Any"),
            400: self._get(test_client, "models"),
            404: test_client.get("/models"),
        }
        with patch(f"{QUERIES_CLASS}.get_models", side_effect=RuntimeError("secret")):
            with patch.object(Logger, "error"):
                responses[500] = self._get(test_client, "models", name="Any")

        for status, response in responses.items():
            with self.subTest(status=status):
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.headers.get("Cache-Control"), "no-store")
                self.assertEqual(response.mimetype, "application/json")

    # safe defaults

    def test_cors_header_only_when_configured(self):
        """No CORS header by default; the configured origin when one is given"""
        response = self._get(self._test_client(), "models", name="Any")
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

        origin = "http://rmtc-ui.example"
        response = self._get(self._test_client(cors_origin=origin), "models", name="Any")
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), origin)


class TestClientServerAgreement(AbstractRMTCTest):
    """
    The Client and Server agree: what the Server sends, the Client rebuilds.

    `requests.get` is patched to forward to a Flask test client. No socket
    is opened.
    """

    # helpers

    def _forwarding(self):
        """Patch requests.get to send Client calls to a fresh Server"""
        test_client = Server(self.get_system())._flask.test_client()
        return patch(
            f"{CLIENT_MODULE}.requests.get", side_effect=_route_requests_to(test_client)
        )

    def _client(self, uri=CLIENT_URI):
        return Client(uri, rmtc_system=self.get_system())

    # round trips

    def test_get_models(self):
        """get_models returns the pushed Model, rebuilt"""
        model = _push_model(self.get_system(), "Demo Model", author="Movie Studio")
        with self._forwarding():
            results = self._client().get_models("Demo Model")

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], Model)
        self.assertEqual(results[0].obj_id, model.obj_id)
        self.assertEqual(results[0].author, "Movie Studio")
        self.assertEqual(str(results[0].uri), str(model.uri))

    def test_get_entities(self):
        """get_entities returns the pushed License, rebuilt"""
        rmtc_sys = self.get_system()
        license = rmtc_sys.create_license(
            License, name="Apache-2.0", status=LicenseStatus.REVOKED
        )
        rmtc_sys.push()
        with self._forwarding():
            results = self._client().get_entities("Apache-2.0")

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], License)
        self.assertEqual(results[0].obj_id, license.obj_id)
        self.assertEqual(results[0].status, LicenseStatus.REVOKED)

    def test_special_character_name(self):
        """A name with spaces and & survives the Client -> Server round trip"""
        _push_model(self.get_system(), "Foo & Bar v2")
        with self._forwarding():
            results = self._client().get_models("Foo & Bar v2")
        self.assertEqual([model.name for model in results], ["Foo & Bar v2"])

    def test_limit(self):
        """limit=2 returns the two newest matches"""
        rmtc_sys = self.get_system()
        for index in range(3):
            rmtc_sys.create_model(
                Model,
                name="Limit Model",
                uri=URI("https://github.com/example/model"),
                author=str(index),
            )
        rmtc_sys.push()
        with self._forwarding():
            results = self._client().get_models("Limit Model", limit=2)
        self.assertEqual([model.author for model in results], ["2", "1"])

    # identity and pushing

    def test_identity_across_calls(self):
        """
        A Model fetched first gives a stub License; fetching the License later
        fills in that same object.
        """
        rmtc_sys = self.get_system()
        license = rmtc_sys.create_license(License, name="Ref License")
        _push_model(rmtc_sys, "Ref Model", licenses=[license])

        client = self._client()
        with self._forwarding():
            model = client.get_models("Ref Model")[0]
            client_license = client.get_entities("Ref License")[0]

        self.assertIs(model.licenses[0], client_license)
        self.assertFalse(client_license.requires_sync())

    def test_results_not_pushable(self):
        """Pushing fetched entities and their stubs writes nothing to the store"""
        rmtc_sys = self.get_system()
        license = rmtc_sys.create_license(License, name="Push License")
        _push_model(rmtc_sys, "Push Model", licenses=[license])

        client_sys = self.get_system()
        client = Client(CLIENT_URI, rmtc_system=client_sys)
        with self._forwarding():
            results = client.get_models("Push Model")

        self.assertEqual(client_sys.push(results + list(results[0].licenses)), [])
        self.assertEqual(len(client_sys.get_models(name="Push Model")), 1)
        self.assertEqual(
            len(client_sys.get_entities(name="Push License", categories=["License"])), 1
        )
