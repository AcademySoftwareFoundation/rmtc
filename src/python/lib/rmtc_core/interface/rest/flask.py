# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


import json

import requests
from flask import Flask, request, jsonify, g

from rmtc import interface
from rmtc.objects import PropertyType
from rmtc.system import (
    URI,
    Type,
    Datetime,
    Version,
    Mode,
    TypeName,
)


class JSONSerializer(interface.Serializer):
    """
    JSON serialization handler for RMTC entities and properties.

    The JSONSerializer class provides bidirectional JSON serialization for RMTC
    entities, handling complex property types, object references, and nested
    structures. It converts RMTC objects to JSON for REST API communication
    and reconstructs objects from JSON data with proper type conversion.

    The serializer handles all RMTC property types including primitives,
    complex types (URI, Datetime, Version, Type), and object references
    with support for both member objects (serialized inline) and reference
    objects (serialized as IDs).
    """

    # TODO: This is incomplete testing code only

    def serialize(self):
        """
        Serialize all internal entities to JSON string.

        Converts all entities in the serializer's object collection to their
        JSON representation, handling property type conversion and object
        relationships appropriately.
        """
        serialized_objects = []

        for obj in self.objects:
            serialized_objects.append(self.serialize_object(obj))
        return json.dumps(serialized_objects)

    def serialize_object(self, obj=None):
        """
        Serialize a single entity to JSON string.
        """

        # TODO: support list order

        # internals
        members = {}
        members["_id"] = obj.obj_id
        members["_type_name"] = obj.type_name

        # properties
        for prop in obj.properties.values():

            # create list of values for the property
            values = prop.value
            if not prop.is_array():
                values = [values]

            # for each value, build list of values out
            out = []
            for value in values:
                if prop.prop_type == PropertyType.OBJECT:
                    if not prop.member():
                        value = value.obj_id
                    else:
                        value = json.loads(self.serialize(value))
                elif prop.prop_type == PropertyType.URI:
                    value = str(value)
                elif prop.prop_type == PropertyType.DATETIME:
                    value = str(value)
                elif prop.prop_type == PropertyType.VERSION:
                    value = str(value)
                elif prop.prop_type == PropertyType.TYPE:
                    value = str(value)
                out.append(value)

            # either assign list if array, or get first element if value
            if not prop.is_array():
                members[prop.name] = out[0]
            else:
                members[prop.name] = out

        return json.dumps(members)

    def deserialize(self, string):
        """
        Deserialize JSON string to RMTC entity objects.

        Converts JSON string representation back to RMTC entities with proper
        type reconstruction and object reference resolution. Handles both
        single entities and arrays of entities.
        """

        # TODO: support list order

        json_data = json.loads(string)
        if isinstance(json_data, list):
            return [self.deserialize_object(item) for item in json_data]
        return self.deserialize_object(json_data)

    def deserialize_object(self, json_dict):
        """
        Deserialize a single JSON object to RMTC entity.

        Reconstructs an RMTC entity from its JSON representation using the
        factory pattern for object creation and proper type conversion for
        all property types. Handles object reference resolution and nested
        object deserialization.
        """

        # Create object using deferred creation (stub)
        obj = self.factory.create(TypeName(json_dict["_type_name"]))
        self.objects.add([obj])

        # internals
        if "_id" in json_dict:
            obj.obj_id = json_dict["_id"]

        # use entity properties - custom props will be missed
        for prop in obj.properties.values():

            # Skip if property not in JSON
            if prop.name not in json_dict:
                continue

            # get the values as a list
            values = json_dict[prop.name]
            if values is None:
                prop.value = None if not prop.is_array() else []
                continue

            if not prop.is_array():
                values = [values]

            # convert from JSON types
            out = []
            prop.unresolved = []
            for value in values:
                if value is None:
                    out.append(None)
                    continue

                if prop.prop_type == PropertyType.OBJECT:
                    if not prop.member():
                        if value in self.objects:
                            value = self.objects[value]
                        else:
                            value = None
                    else:
                        value = self.deserialize_object(value)
                elif prop.prop_type == PropertyType.DATETIME:
                    value = Datetime(value)
                elif prop.prop_type == PropertyType.URI:
                    value = URI(value)
                elif prop.prop_type == PropertyType.VERSION:
                    value = Version(value)
                elif prop.prop_type == PropertyType.TYPE:
                    value = Type(value)

                if value is not None:
                    out.append(value)

            # either assign list if array, or get first element if value
            if not prop.is_array():
                if len(out) == 0:
                    prop.value = None
                elif len(out) == 1:
                    prop.value = out[0]
                else:
                    # Multiple values for non-array property - take first
                    prop.value = out[0]
            else:
                prop.value = out

        return obj


class Client(interface.Client):
    """
    REST API client for communicating with RMTC servers.

    The Client class provides a REST-based interface for communicating with
    RMTC servers over HTTP. It handles request formatting, response parsing,
    and provides high-level methods for common RMTC operations like entity
    retrieval.

    The client uses the requests library for HTTP communication and integrates
    with the RMTC serialization system for proper data conversion.
    """

    # TODO: This is incomplete testing code only

    def __init__(self, uri, system=None, serializer=None):
        """Initialize REST client with server URI and optional components."""
        super(Client, self).__init__(system=system, serializer=serializer)
        self._uri = uri

    def get_entities(self, name=None):
        """Retrieve entities from the server by name.

        Args:
            name (str, optional): Entity name to search for. Defaults to None.

        Returns:
            list: List of entities matching the name, or empty list if none found
                or request fails.
        """
        data = {
            "name": str(name),
        }
        response = requests.get(f"{self._uri}/get_entities", json=data, timeout=5)
        if response.status_code == 200:
            return response.json()
        return []


class Server(interface.Server):
    """
    Flask-based REST API server for RMTC system access.

    The Server class provides a REST API interface to RMTC system functionality
    using Flask as the web framework. It handles HTTP requests, manages database
    connections, and provides endpoints for entity operations with proper
    connection lifecycle management.

    The server implements per-request connection management using Flask's
    application context and provides automatic connection cleanup on request
    completion or errors.
    """

    # TODO: This is incomplete testing code only

    def __init__(self, system, serializer=None):
        """Initialize Flask server with RMTC system and setup routes."""
        super(Server, self).__init__(system, serializer=serializer)
        self._flask = Flask("RMTC")
        self._setup()
        self._tokens = set()

    def run(self):
        """Start the Flask development server."""
        debug = self.system.mode != Mode.PRODUCTION
        self._flask.run(debug=debug)

    def connected(self):
        """Check if current request has an active database connection."""
        return "connection" in g

    def close(self):
        """Close server resources (no-op in current implementation)."""
        pass

    def open(self):
        """Get or create database connection for current request.

        Returns:
            Connection: Database connection for the current request context.
        """
        if "connection" not in g:
            g.connection = self.system.open()
        return g.connection

    def _setup(self):
        """Configure Flask routes and request handlers.

        Sets up all REST API endpoints and request lifecycle handlers including
        automatic connection cleanup on request completion or errors.
        """

        @self._flask.route("/get_entities", methods=["GET"])
        def get_entities():
            """REST endpoint for entity retrieval by name."""
            data = request.json
            entities = self.get_entities(name=URI(data["name"]))
            return jsonify(entities)

        @self._flask.teardown_appcontext
        def teardown(exception):
            """Clean up request context and close database connections."""
            if exception:
                self.system.log.error(exception)
            connection = g.pop("connection", None)
            if connection:
                connection.close()

    def get_entities(self, name=None):
        """Retrieve entities from the database by name."""
        connection = self.open()
        return connection.queries.get_entities(name=name)
