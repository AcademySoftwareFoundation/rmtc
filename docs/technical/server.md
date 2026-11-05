# Server

A REST API to support operations with the RMTC database over a network.

## Basic Architecture

The RMTC server exposes a REST API that connects directly to the store. It supports multiple clients, currently including a Python client and a Typescript Web UI.

The server is built on Flask and extends the various `get_{entity}()` methods exposed in the store as Flask routes.

### Serialization

Serialization is handled through the JSONSerializer. It takes an entity and converts its properties into an appropriate JSON format, with the property type listed together with it. All entities are serialized into their `_id`, `name`, and `_type_name`, along with their custom properties.

Reference properties (links to other entites/objects) are stored as JSON maps. Member reference properties are stored recursively with all of their properties, while non-member properties have only stubbed properties (`_id`, `name`, and `_type_name`). 

Deserialization happens through the Factory, which is able to identify registered objects by their `_id` and uses `_type_name` to reconstruct the python object. Property values stored in JSON are also populated onto the python object.

For objects that are not registered with the Factory, a Proxy object will be used in its place.

## Serving

The Server is exposed via a WSGI app that can be run with any WSGI-compatible server of your choice. We offer `gunicorn` as a default part of the package.

The WSGI entry point is the `create_app()` factory in `rmtc_server.app`:

```bash
gunicorn --workers 2 --bind 127.0.0.1:9000 "rmtc_server.app:create_app()"
```

Each worker calls `create_app()` itself, building its own `System` and store connection. Avoid `--preload`, which creates the app once before the workers fork, leaving them sharing a single store connection.

## Environment Variables

The server uses a custom `RMTC_SERVER_CONFIG` environment variable to avoid any kind of overwrites between conflicting packages. It also falls back to `RMTC_CONFIG_NAME`.

It also uses a `RMTC_CORS_ORIGIN` environment variable to set the `Access-Control-Allow-Origin` HTTP header. This is only needed for cross-origin clients.

## Versioning

Versioning is defined by the routes, query parameters, and JSON response format provided by the route. This means that the version depends on the JSONSerializer and Server classes together.

Routes are prefixed with the major API version (`/v{major}`). A breaking change bumps the major version and moves to a new prefix (e.g. `/v2`), so existing clients can keep using `/v1`.

## Routes and Query Parameters

The currently supported routes are of the shape `/v1/{resource}`, for example `/v1/entities`, `/v1/models`.

Currently supported query parameters:
* `name`: required - the entity name to search for.
* `exact`: true/false
    * This is for name matching - `false` will do a contains match rather than an exact match
* `limit`: max 100

Errors come back as JSON in the form `{"error": ...}` and every response sets the `Cache-Control: no-store` HTTP header.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
