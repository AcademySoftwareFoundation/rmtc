# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project
import os
import json
import traceback
from flask import Flask, request, g, Response, abort
from werkzeug.exceptions import HTTPException

from rmtc import System
from rmtc.system import Config
from rmtc.system.objects import Objects
from rmtc.interface import Server as BaseServer
from rmtc.core.system.serializers.json import JSONSerializer
from rmtc.core.interface.rest.client import API_VERSION


# hard cap on ?limit= so one request can't pull the whole store
MAX_LIMIT = 100


def create_app():
    """
    Create a WSGI app as the entrypoint for a server like gunicorn
    """
    username = os.environ.get("RMTC_USER")
    password = os.environ.get("RMTC_PW")

    rmtc_sys = System(
        config=Config(name=os.environ.get("RMTC_SERVER_CONFIG")),
        credentials=(username, password),
    )
    if not rmtc_sys.track.is_valid():
        raise RuntimeError(
            "Invalid system object - login credentials or subsytems not valid"
        )
    server = Server(
        rmtc_system=rmtc_sys, cors_origin=os.environ.get("RMTC_CORS_ORIGIN")
    )
    return server.app


class Server(BaseServer):
    """
    Flask-based read-only REST API server for RMTC system access.

    Routes are served under /v<API_VERSION major>:
        GET /entities?name=<name>[&limit=<n>]
        GET /models?name=<name>[&limit=<n>]

    Responses are `{"results": [...]}`, each element an entity as produced
    by `JSONSerializer.serialize_object`; errors are `{"error": <message>}`.
    Every response carries `Cache-Control: no-store`, and
    `Access-Control-Allow-Origin` if a CORS origin is given.

    The server implements per-request connection management using Flask's
    application context. The store's entity cache is cleared before each
    request so responses always reflect the store. Requests share that cache,
    so the server runs single threaded.
    """

    def __init__(self, rmtc_system, cors_origin=None):
        """Initialize Flask server with RMTC system and setup routes."""
        super(Server, self).__init__(rmtc_system)
        self._cors_origin = cors_origin
        self._flask = Flask("RMTC")
        self._setup()

    @property
    def app(self):
        """The WSGI app, for a server such as gunicorn"""
        return self._flask

    def connected(self):
        """Check if current request has an active database connection."""
        return "connection" in g

    def close(self):
        """Close server resources (no-op in current implementation)."""
        raise NotImplementedError()

    def open(self):
        """Get or create database connection for current request.

        Returns:
            Connection: Database connection for the current request context.
        """
        if "connection" not in g:
            g.connection = self.system.track.open()
        return g.connection

    def _setup(self):
        """Configure Flask routes and request handlers.

        Sets up all REST API endpoints and request lifecycle handlers including
        automatic connection cleanup on request completion or errors.
        """
        prefix = f"/v{API_VERSION.major}"

        @self._flask.route(f"{prefix}/entities", methods=["GET"])
        def get_entities():
            """REST endpoint for entity retrieval by name."""
            name, limit, exact = self._query_args()
            entities = self.get_entities(name=name, limit=limit, exact=exact)
            return self._json(entities)

        @self._flask.route(f"{prefix}/models", methods=["GET"])
        def get_models():
            """REST endpoint for model retrieval by name."""
            name, limit, exact = self._query_args()
            entities = self.get_models(name=name, limit=limit, exact=exact)
            return self._json(entities)

        @self._flask.route(f"{prefix}/runs", methods=["GET"])
        def get_runs():
            """REST endpoint for run retrieval by name."""
            name, limit, exact = self._query_args()
            entities = self.get_runs(name=name, limit=limit, exact=exact)
            return self._json(entities)

        @self._flask.route(f"{prefix}/licenses", methods=["GET"])
        def get_licenses():
            """REST endpoint for license retrieval by name."""
            name, limit, exact = self._query_args()
            entities = self.get_licenses(name=name, limit=limit, exact=exact)
            return self._json(entities)

        @self._flask.route(f"{prefix}/solutions", methods=["GET"])
        def get_solutions():
            """REST endpoint for solution retrieval by name."""
            name, limit, exact = self._query_args()
            entities = self.get_solutions(name=name, limit=limit, exact=exact)
            return self._json(entities)

        @self._flask.route(f"{prefix}/datasets", methods=["GET"])
        def get_datasets():
            """REST endpoint for dataset retrieval by name."""
            name, limit, exact = self._query_args()
            entities = self.get_datasets(name=name, limit=limit, exact=exact)
            return self._json(entities)

        @self._flask.route(f"{prefix}/inferences", methods=["GET"])
        def get_inferences():
            """REST endpoint for inference retrieval by name."""
            name, limit, exact = self._query_args()
            entities = self.get_inferences(name=name, limit=limit, exact=exact)
            return self._json(entities)

        @self._flask.route(f"{prefix}/assets", methods=["GET"])
        def get_assets():
            """REST endpoint for asset retrieval by name."""
            name, limit, exact = self._query_args()
            entities = self.get_assets(name=name, limit=limit, exact=exact)
            return self._json(entities)

        @self._flask.before_request
        def clear_cache():
            """Drop cached entities so this request reads from the store."""
            self.system.track.store.clear()

        @self._flask.after_request
        def add_headers(response):
            """Disable caching and add the CORS header if configured."""
            response.headers["Cache-Control"] = "no-store"
            if self._cors_origin:
                response.headers["Access-Control-Allow-Origin"] = self._cors_origin
            return response

        @self._flask.errorhandler(HTTPException)
        def http_error(error):
            """Send HTTP errors (400, 404, ...) as JSON."""
            return self._json(json.dumps({"error": error.description}), error.code)

        @self._flask.errorhandler(Exception)
        def internal_error(error):
            """Log unexpected errors in full; send only a generic message."""
            self.system.log.error(f"REST request failed\n{traceback.format_exc()}")
            return self._json(json.dumps({"error": "Internal server error"}), 500)

        @self._flask.teardown_appcontext
        def reset(exception):
            """Clean up request context and close database connections."""
            if exception:
                self.system.log.error(exception)
            connection = g.pop("connection", None)
            if connection:
                connection.close()

    def _query_args(self):
        """Read and validate ?name= and ?limit=, aborting with 400 if invalid."""
        name = request.args.get("name")
        if not name:
            abort(400, description="Missing required query parameter 'name'")

        exact = request.args.get("exact", "false").lower()
        if exact not in ("true", "false"):
            abort(400, description="'exact' must be 'true' or 'false")
        exact = exact == "true"

        limit = request.args.get("limit")
        if limit is None:
            return (
                name,
                min(self.system.track.store.limit or MAX_LIMIT, MAX_LIMIT),
                exact,
            )
        if not limit.isdecimal() or not 1 <= int(limit) <= MAX_LIMIT:
            abort(400, description=f"'limit' must be an integer from 1 to {MAX_LIMIT}")

        return name, int(limit), exact

    def _json(self, body, status=200):
        """Wrap a JSON string in a Flask response"""
        return Response(body, status=status, mimetype="application/json")

    def get_entities(self, name=None, limit=None, exact=False):
        """Retrieve entities from the database by name, as a JSON string."""
        connection = self.open()
        return self._serialize(
            connection,
            connection.queries.get_entities(name=name, limit=limit, exact=exact),
        )

    def get_models(self, name=None, limit=None, exact=False):
        """Retrieve models from the database by name, as a JSON string."""
        connection = self.open()
        return self._serialize(
            connection,
            connection.queries.get_models(name=name, limit=limit, exact=exact),
        )

    def get_runs(self, name=None, limit=None, exact=False):
        """Retrieve runs from the database by name, as a JSON string."""
        connection = self.open()
        return self._serialize(
            connection, connection.queries.get_runs(name=name, limit=limit, exact=exact)
        )

    def get_licenses(self, name=None, limit=None, exact=False):
        """Retrieve licenses from the database by name, as a JSON string."""
        connection = self.open()
        return self._serialize(
            connection,
            connection.queries.get_licenses(name=name, limit=limit, exact=exact),
        )

    def get_solutions(self, name=None, limit=None, exact=False):
        """Retrieve solutions from the database by name, as a JSON string."""
        connection = self.open()
        return self._serialize(
            connection,
            connection.queries.get_solutions(name=name, limit=limit, exact=exact),
        )

    def get_datasets(self, name=None, limit=None, exact=False):
        """Retrieve datasets from the database by name, as a JSON string."""
        connection = self.open()
        return self._serialize(
            connection,
            connection.queries.get_datasets(name=name, limit=limit, exact=exact),
        )

    def get_inferences(self, name=None, limit=None, exact=False):
        """Retrieve inferences from the database by name, as a JSON string."""
        connection = self.open()
        return self._serialize(
            connection,
            connection.queries.get_inferences(name=name, limit=limit, exact=exact),
        )

    def get_assets(self, name=None, limit=None, exact=False):
        """Retrieve assets from the database by name, as a JSON string."""
        connection = self.open()
        return self._serialize(
            connection,
            connection.queries.get_assets(name=name, limit=limit, exact=exact),
        )

    def _serialize(self, connection, entity_ids):
        """Fetch and fully sync the entities, then wrap them in the response envelope"""
        entities = connection.fetch(entity_ids)
        connection.sync(entities)
        serializer = JSONSerializer(self.system.factory, Objects())
        results = [serializer.serialize_object(entity) for entity in entities]
        return json.dumps({"results": results}, allow_nan=False)
