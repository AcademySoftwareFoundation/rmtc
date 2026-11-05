# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import json
import warnings
import neo4j

from rmtc.core.track.store.cypher.connection import CypherConnection
from rmtc.track.store import Store
from rmtc.system import RMTCException

ignore_warnings = [".*The configuration may change in the future.*"]
for to_ignore in ignore_warnings:
    warnings.filterwarnings("ignore", message=to_ignore)


def _execute_neo4j_query(tx, query, **kwargs):
    result = tx.run(query, **kwargs)
    json_result = json.dumps(result.data())
    return json_result


class Neo4jConnection(CypherConnection):
    """Neo4j connection specialisation"""

    def __init__(
        self,
        store,
        neo4j_connection,
    ):
        super(Neo4jConnection, self).__init__(
            store=store,
        )
        self._connection = neo4j_connection

    def lock(self, timeout=60000):
        raise NotImplementedError()

    def unlock(self):
        raise NotImplementedError()

    def read_query(self, query, **kwargs):

        # Set notification threshold to severe errors only
        self.store.log.debug(f"Query: {query}")
        self.store.log.debug(f"Kwargs: {kwargs}")
        result_string = "[]"
        if self._connection is not None:
            with self._connection.session(notifications_min_severity="OFF") as session:
                result_string = session.execute_read(
                    _execute_neo4j_query,
                    query,
                    **kwargs,
                )
        result = json.loads(result_string)
        self.store.log.debug(f"Result: {result}")
        return result

    def write_query(self, query, **kwargs):
        self.store.log.debug(f"Query: {query}")
        self.store.log.debug(f"Kwargs: {kwargs}")
        result_string = "[]"
        if self._connection is not None:
            with self._connection.session(notifications_min_severity="OFF") as session:
                result_string = session.execute_write(
                    _execute_neo4j_query,
                    query,
                    **kwargs,
                )
        result = json.loads(result_string)
        self.store.log.debug(f"Result: {result}")
        return result

    def close(self):
        if self._connection is not None:
            self._connection.close()
            self._connection = None


class Neo4jDatabase(Store):
    """Neo4j database wrapper for store"""

    def __init__(
        self,
        name="neo4j",
        factory=None,
        immutable=True,
        uri=None,
        log=None,
        jit=None,
        limit=None,
        timeout=None,
    ):
        super(Neo4jDatabase, self).__init__(
            factory=factory,
            uri=uri,
            immutable=immutable,
            name=name,
            log=log,
            jit=jit,
            limit=limit,
            timeout=timeout,
        )

    def supports_datetime(self):
        # Datetime not supported in JSON encoder for Neo4j
        return False

    def connect(self, username, password):
        neo4j_connection = neo4j.GraphDatabase.driver(
            str(self.uri), auth=(username, password)
        )
        try:
            neo4j_connection.verify_connectivity()
        except Exception as e:  # pylint: disable=broad-exception-caught
            neo4j_connection.close()
            raise RMTCException(
                f"Cannot verify connection to: '{self.uri}'\n{e}"
            ) from e
        return Neo4jConnection(
            store=self,
            neo4j_connection=neo4j_connection,
        )
