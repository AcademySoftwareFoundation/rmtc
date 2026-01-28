# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from contextlib import contextmanager

import re

import age

from rmtc_core.track.cypher.connection import CypherConnection

from rmtc.track import Store
from rmtc.system import Mode, RMTCException


class AGEConnection(CypherConnection):
    """
    Apache AGE database connection implementation for PostgreSQL-based graph operations.

    The AGEConnection class provides a concrete implementation of CypherConnection
    specifically designed for Apache AGE (A Graph Extension for PostgreSQL). It
    handles the translation between Cypher queries and AGE's SQL-wrapped Cypher
    syntax, managing query execution, result parsing, and transaction control.
    """

    LOCK_KEY = 1234

    def __init__(
        self,
        store=None,
        age_connection=None,
    ):
        """Initialize AGEConnection with store and PostgreSQL connection."""
        super(AGEConnection, self).__init__(store=store)
        self._connection = age_connection

    def _run_query(self, query):
        """Execute a Cypher query through Apache AGE's SQL interface."""

        # get all AS statements to add to return string
        keys = []
        pattern = re.compile(r"AS ([A-z0-9]+)")
        for match in pattern.finditer(query):
            keys.append(match.group(1))

        # build AGE query - SELECT * FROM cypher('graph', $$ $$) AS (result agtype)
        age_query = f"SELECT * FROM cypher('{self.store.name}', $$\n{query}\n$$)"
        if len(keys) > 0:
            columns = " agtype, ".join(keys) + " agtype"
            age_query = age_query + f" AS ({columns});"
        else:
            age_query = age_query + " AS (result agtype);"

        self.store.log.debug(age_query)

        # run query
        entries = []
        with self._connection.cursor() as cursor:
            try:
                cursor.execute(age_query)
            except Exception as ex:  # pylint: disable=broad-exception-caught
                raise RMTCException(f"Invalid query:\n{age_query}") from ex
            for values in cursor:
                entry = {}
                for key, value in zip(keys, values):
                    entry[key] = value
                entries.append(entry)

        self.store.log.debug(entries)

        return entries

    def write_query(self, query):
        """Execute a write Cypher query with transaction management."""
        result = []
        try:
            result = self._run_query(query)
            self._connection.commit()
        except Exception as ex:  # pylint: disable=broad-exception-caught
            self._connection.rollback()
            raise RMTCException(f"Invalid query:\n{query}") from ex
        return result

    def read_query(self, query):
        """Execute a read-only Cypher query."""
        result = []
        try:
            result = self._run_query(query)
        except Exception as ex:  # pylint: disable=broad-exception-caught
            raise RMTCException(f"Invalid query:\n{query}") from ex
        return result

    def close(self):
        """Close the connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def lock(self, timeout=60000):
        """
        Get a database advisory lock for the given key. This will block until the
        lock is acquired or the timeout expires.

        The lock is released once the connection is closed.
        """
        timeout_query = f"SET LOCAL lock_timeout = '{timeout}ms'"
        lock_query = f"SELECT pg_advisory_lock({AGEConnection.LOCK_KEY});"

        # run queries
        with self._connection.cursor() as cursor:
            try:
                cursor.execute(timeout_query)
                cursor.execute(lock_query)
            except Exception as ex:  # pylint: disable=broad-exception-caught
                raise RMTCException(f"Invalid query:\n{lock_query}") from ex

    def unlock(self):
        """Release the database advisory lock."""
        query = f"SELECT pg_advisory_unlock({AGEConnection.LOCK_KEY});"

        # run query
        with self._connection.cursor() as cursor:
            try:
                cursor.execute(query)
            except Exception as ex:  # pylint: disable=broad-exception-caught
                raise RMTCException(f"Invalid query:\n{query}") from ex


class AGEDatabase(Store):
    """
    Apache AGE database store implementation.

    The AGEDatabase class provides a complete graph database store implementation
    using Apache AGE, which adds graph database capabilities to PostgreSQL.
    It manages database connections, graph creation, and provides the interface
    for RMTC entity persistence and querying.

    Apache AGE combines the reliability and ACID properties of PostgreSQL with
    graph database capabilities, making it suitable for production ML tracking
    systems that require both relational and graph data models.
    """

    def __init__(
        self,
        name="rmtc",
        db_name="postgres",
        factory=None,
        mode=Mode.PRODUCTION,
        uri=None,
        log=None,
        jit=None,
    ):
        """Initialize AGEDatabase with PostgreSQL and graph configuration."""
        super(AGEDatabase, self).__init__(
            name=name,
            factory=factory,
            uri=uri,
            mode=mode,
            log=log,
            jit=jit,
        )
        self._db_name = db_name

    @property
    def lock_key(self):
        return self._lock_key

    @property
    def db_name(self):
        return self._db_name

    def connect(self, username, password):
        """Establish connection to Apache AGE database."""
        host = self.uri.host
        port = self.uri.port
        ag = None
        try:
            self.log.debug(  # pylint: disable=no-member
                f"Creating AGE Database connection to {self.uri} with graph: {self.name}"
            )
            ag = age.connect(
                host=host,
                port=port,
                dbname=self._db_name,
                user=username,
                password=password,
                graph=self.name,
            )
        except Exception as ex:  # pylint: disable=broad-exception-caught
            self.log.error(ex)

        # return
        if ag is not None:
            return AGEConnection(
                store=self,
                age_connection=ag.connection,
            )
        return None


@contextmanager
def acquire_store_lock(connection, timeout=60000):
    """Context manager for acquiring and releasing a lock for the RMTC store."""
    try:
        connection.lock(timeout=timeout)
        yield
    finally:
        connection.unlock()
