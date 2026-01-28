# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import json

import neo4j

from rmtc_core.track.cypher.connection import CypherConnection

from rmtc.system import Mode
from rmtc.track import Store


def _execute_neo4j_query(tx, query):
    result = tx.run(query)
    json_result = json.dumps(result.data())
    return json_result


class Neo4jConnection(CypherConnection):
    """Neo4j connection specialisation"""

    def __init__(
        self,
        store=None,
        neo4j_connection=None,
    ):
        super(Neo4jConnection, self).__init__(store=store)
        self._connection = neo4j_connection

    def lock(self, timeout=60000):
        pass

    def unlock(self):
        pass

    def read_query(self, query):
        self.store.log.debug(query)
        result_string = "[]"
        if self._connection is not None:
            with self._connection.session() as session:
                result_string = session.read_transaction(_execute_neo4j_query, query)
        result = json.loads(result_string)
        self.store.log.debug(result)
        return result

    def write_query(self, query):
        self.store.log.debug(query)
        result_string = "[]"
        if self._connection is not None:
            with self._connection.session() as session:
                result_string = session.write_transaction(_execute_neo4j_query, query)
        result = json.loads(result_string)
        self.store.log.debug(result)
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
        mode=Mode.PRODUCTION,
        uri=None,
        log=None,
        jit=None,
    ):
        super(Neo4jDatabase, self).__init__(
            factory=factory,
            uri=uri,
            mode=mode,
            name=name,
            log=log,
            jit=jit,
        )

    def connect(self, username, password):
        neo4j_connection = neo4j.GraphDatabase.driver(
            str(self.uri), auth=(username, password)
        )
        if neo4j_connection is not None:
            return Neo4jConnection(store=self, neo4j_connection=neo4j_connection)
        return None
