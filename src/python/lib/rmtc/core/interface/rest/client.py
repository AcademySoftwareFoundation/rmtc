# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import json
import requests

from rmtc.interface import Interface
from rmtc.system.objects import Objects
from rmtc.system import (
    Version,
    RMTCException,
)
from rmtc.core.system.serializers.json import JSONSerializer

# Version of the REST API format. The major version should be incremented
# whenever anything that may break a client (eg. route conventions or
# JSON encoding formats) change.
API_VERSION = Version("2.0.0")


class Client(Interface):
    """
    REST API client for communicating with RMTC servers.

    The Client class provides a RESTbased interface for communicating with
    RMTC servers over HTTP. It handles request formatting, response parsing,
    and provides highlevel methods for common RMTC operations like entity
    retrieval.

    The client uses the requests library for HTTP communication and integrates
    with the RMTC serialization system for proper data conversion.
    """

    def __init__(self, uri, rmtc_system=None, serializer=None):
        """Initialize REST client with server URI and optional components."""
        if serializer is None and rmtc_system is not None:
            serializer = JSONSerializer(rmtc_system.factory, Objects())
        super(Client, self).__init__(rmtc_system=rmtc_system, serializer=serializer)
        self._uri = str(uri).rstrip("/")

    def get_entities(self, name, limit=None):
        """Retrieve entities from the server by name."""
        return self._get("entities", name, limit)

    def get_models(self, name, limit=None):
        """Retrieve models from the server by name."""
        return self._get("models", name, limit)

    def _get(self, resource, name, limit):
        """GET a versioned resource and deserialize the entities in its envelope"""
        params = {"name": name}
        if limit is not None:
            params["limit"] = limit
        response = requests.get(
            f"{self._uri}/v{API_VERSION.major}/{resource}",
            params=params,
            timeout=5,
        )
        if response.status_code != 200:
            raise RMTCException(
                f"GET {resource} failed ({response.status_code}): {response.text}"
            )
        payload = json.loads(response.text)
        return [
            self._serializer.deserialize_object(item) for item in payload["results"]
        ]
