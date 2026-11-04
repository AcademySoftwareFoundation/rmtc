# Interface 

Interface (`rmtc.interface`) defines the Client & Server abstractions for a REST style architecture to bridge between 2 Systems – with the Server system connecting through to the remote storage. RMTC Core provides a Python REST client (`rmtc.core.interface.rest.client`) and a JSON serializer (`rmtc.core.system.serializers.json`); the Flask based REST server is the separate `rmtc-server` package - see [Server](server.md) for the REST server, and [Web UI](webui.md) for the browser client. 

RMTC’s domain lends itself naturally to web interfaces – this is still an early capability as it primarily operates in a traditional VFX Python session.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
