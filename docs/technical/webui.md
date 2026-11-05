# Web UI

The web UI offers a way to browse RMTC entities from the database via the REST API.

## Stack
- Package manager: `npm`
- Language: TypeScript
- Build tool: Vite
- Interface library: React
- Component Library and Styling: MUI and MUI X
- Routing: TanStack Router (planned)
- Server Queries: TanStack Query + Axios
- Local State: Zustand

## Basic Structure

`src/web/browser/src/api/client.ts` has a single axios instance, including a list of resources and a query method for the server. This is currently the only file that does any network requests.

`src/web/browser/src/components/DataTable.tsx` is a generic view whose columns dynamically adapt to the properties of the entity retrieved. It orders its columns based on frequency with which a property has non-empty values, and hides internal fields like `_id` and `_type_name`.
* The generic view requires no knowledge of entity schemas on the TypeScript side, including any custom entities created by facilities.

## Development

For local development, see the [README](../../README.md#web-ui-and-server).

The vite dev server forwards any `/v<N>/...` request to `localhost:9000`, so start the server first.

## Hosting and Deployment

`npm run build` (from `src/web/browser`) produces `src/web/browser/dist`, a folder of static files that can be served by any web server. Whichever server you use should:
* Return `index.html` for any path that isn't a file in `dist`, so that client-side routing works
* Allow browsers to cache files under `dist/assets` (their filenames contain a content hash), but not `index.html`

The Web UI includes a simple [file server](../../src/web/browser/serve/serve_ui.py) that follows these rules, and can be run with any WSGI server such as `gunicorn`. It reads the `RMTC_WEB_ROOT` environment variable as the folder containing `dist`:

```bash
RMTC_WEB_ROOT=$PWD/src/web/browser gunicorn --bind 127.0.0.1:8080 --chdir src/web/browser/serve serve_ui:app
```

There are many ways you could deploy the web UI - for example, packaging the `src/web/browser/dist` and `src/web/browser/serve` folders into a Docker image which runs the WSGI app via `gunicorn`.

## Connecting to the Server

The web UI requests the API at the relative path `/v1`, so it always calls the same host it was loaded from. When hosting, you will need a reverse proxy that sends `/v1` on the web host to the server. Note that the file server above only serves the UI files - it does not forward `/v1`.

Serving the web UI and the server from different hosts would require changing `baseURL` in `client.ts` as well as setting `RMTC_CORS_ORIGIN` on the server (see [server docs](./server.md)).

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
