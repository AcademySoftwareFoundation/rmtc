# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Cypher implementation shared between AGE & Neo4j.

AGE supports a subset with some differing behaviour over DISTINCT to Neo4j.
Primarily - since AGE supports different graphs but Neo4j does not,
we force a _store name into the objects on CREATE.

This allows you to emulate separate graphs - however weakly, but has most
value in the delete all call.

Once you create and use an ID, there is an assumption that the ID
will be under the right store - this will only be true if any
query string that doesn't match on ID specifically, uses the store name.
"""

from abc import abstractmethod

from rmtc.track import Queries, Connection
from rmtc.objects import PropertyType, PropertyContainer
from rmtc.system import (
    Datetime,
    Version,
    URI,
    Type,
    RMTCException,
    Mode,
    Package,
    TypeName,
)


class CypherConnection(Connection):
    """
    Cypher-based database connection for graph database operations.

    The CypherConnection class provides a concrete implementation of the RMTC
    Connection interface for graph databases that support the Cypher query
    language (such as Neo4j or Apache AGE). It handles entity persistence,
    property synchronization, and relationship management using Cypher queries.
    """

    def __init__(self, store=None, queries=None):
        """Initialize CypherConnection with store and CypherQueries."""
        if queries is None:
            queries = CypherQueries(self)
        super(CypherConnection, self).__init__(store=store, queries=queries)

    def delete_all(self):
        """Delete all nodes and relationships from the graph database.

        This method performs a complete database wipe by executing a Cypher
        query that matches all nodes and detaches/deletes them along with
        their relationships. This operation is only allowed in testing mode
        to prevent accidental data loss.
        """
        if self.store.mode == Mode.PRODUCTION:
            raise RMTCException(f"Failed to delete production storage {self.store.uri}")
        query = f"""
            MATCH (e) WHERE e._store='{self.store.name}'
            DETACH DELETE e RETURN count(e) AS deleted
        """
        result = self.write_query(query)
        self.store.clear()
        if result is not None:
            return int(result[0]["deleted"])
        return 0

    def delete_entities(self, entities):
        """
        Delete entities in the graph database and detach/delete connected relationships.

        This operation is only allowed in testing mode to prevent accidental data loss.
        """
        if len(entities) == 0:
            return 0
        if self.store.mode == Mode.PRODUCTION:
            self.store.log.warning("Deleting entities inside production")
        ids = []
        for entity in entities:
            ids.append(entity.obj_id)
        result = self.write_query(
            f"""
            MATCH (e) WHERE e._obj_id IN {ids}
            DETACH DELETE e
            RETURN count(e) AS deleted
        """
        )
        for entity in entities:
            self.store.remove_entity(entity)
        if result is not None:
            return int(result[0]["deleted"])
        return 0

    def create_entities(self, entities):
        """
        Create new entities in the graph database.

        Creates graph nodes for each entity with appropriate labels and metadata.
        Each entity is assigned a unique graph node ID and has its required
        properties synchronized to the database immediately after creation.

        We write out the name of the store so that the nodes are scoped
        to a given context - e.g. testing, dev, weta etc.
        """
        if len(entities) == 0:
            return 0
        ids = []
        for entity in entities:
            label = entity.class_category
            type_name = self.store.factory.resolve_inverse(entity.__class__)
            query = f"""
                CREATE (e:{label}
                    {{_type_name:'{type_name}',
                    _store:'{self.store.name}',
                    _created:'{Datetime()}',
                    _timestamp:'{entity.timestamp}',
                    _obj_id:'{entity.obj_id}'}})
                RETURN DISTINCT e._obj_id AS id
            """
            result = self.write_query(query)
            if result is not None:
                self.store.add_entity(result[0]["id"], entity)
                self._update_properties(entity, required_only=True)
                ids.append(result[0]["id"])
        return entities

    def fetch_entities(self, ids):
        """
        Fetch entities from the graph database by their node IDs.

        Retrieves entities from the database, reconstructs them using the
        factory pattern based on stored type information.

        Reads only the required properties.
        """
        if len(ids) == 0:
            return []
        entities = []
        for obj_id in ids:
            results = self.read_query(
                f"""
                MATCH (e) WHERE e._obj_id='{obj_id}'
                RETURN
                e._type_name AS type_name,
                e._timestamp AS timestamp
            """
            )
            if len(results) == 1:
                result = results[0]
                type_name = TypeName(result["type_name"])
                entity = self.store.factory.create(type_name)
                if entity is None:
                    self.store.log.warning(
                        f"Cannot create instance of {type_name} for {obj_id}"
                    )
                else:
                    entity.reset_create()
                    entity.reset_update()
                    entity.mark_for_sync()
                    self.store.add_entity(obj_id, entity)
                    self._sync_properties(entity, required_only=True)
                    entity.mark_for_sync()
                    entities.append(entity)
        return entities

    def sync_entities(self, entities):
        """Synchronize entity properties from the database."""
        if len(entities) == 0:
            return True
        for entity in entities:
            self._sync_properties(entity)
        return True

    def update_entities(self, entities):
        """Update entity properties in the database."""
        if len(entities) == 0:
            return True
        for entity in entities:
            self._update_properties(entity)
        return True

    def _update_properties(
        self,
        entity,
        required_only=False,
    ):
        """
        Update entity properties in the graph database.

        Synchronizes entity properties to the database by separating node
        properties (stored as node attributes) from relationship properties
        (stored as graph relationships). Handles both simple properties and
        complex object references with proper type conversion.
        """

        # query the timestamp
        timestamps = self.queries.get_timestamps([entity])
        if len(timestamps) > 0 and timestamps[0] is not None:
            if timestamps[0] > entity.timestamp:
                self.store.log.warning(
                    f"Skipping {entity} update as remote store is newer"
                )
                return

        # seperate into links and node props
        node_props = []
        relation_props = []
        for prop_name in entity.properties:
            prop = entity.properties[prop_name]

            # skip required
            if required_only and not prop.required:
                continue

            # add
            if prop.prop_type == PropertyType.OBJECT:
                relation_props.append(prop)
            else:
                node_props.append(prop)

        # assign POD props
        if len(node_props) > 0:
            query = (
                f"MATCH (e:{entity.class_category}) WHERE e._obj_id='{entity.obj_id}'\n"
            )
            for prop in node_props:
                if prop.container_type == PropertyContainer.VALUE:
                    if prop.prop_type == PropertyType.STRING:
                        query += f"SET e.{prop.name} = '{prop.value}'\n"
                    elif prop.prop_type == PropertyType.DATETIME:
                        query += f"SET e.{prop.name} = '{prop.value}'\n"
                    elif prop.prop_type == PropertyType.VERSION:
                        query += f"SET e.{prop.name} = '{prop.value}'\n"
                    elif prop.prop_type == PropertyType.PACKAGE:
                        query += f"SET e.{prop.name} = '{prop.value}'\n"
                    elif prop.prop_type == PropertyType.TYPE:
                        type_name = self.store.factory.resolve_inverse(
                            prop.value.type_class
                        )
                        query += f"SET e.{prop.name} = '{type_name or str()}'\n"
                    elif prop.prop_type == PropertyType.URI:
                        query += f"SET e.{prop.name} = '{prop.value}'\n"
                    elif prop.prop_type == PropertyType.ENUM:
                        query += f"SET e.{prop.name} = '{prop.value.name}'\n"
                    else:
                        query += f"SET e.{prop.name} = {prop.value}\n"
                else:
                    query += f"SET e.{prop.name} = {prop.value}\n"
            query += f"SET e._timestamp = '{entity.timestamp}'\n"
            self.write_query(query)

        # assign relation props
        for prop in relation_props:
            i = 0

            # visited objects
            visited = set()

            # any item connected needs to also be created in the DB and push
            if prop.is_member_object():
                self.create(prop.array_value)
                self.update(prop.array_value)

            # update
            for other in prop.array_value:

                # record which we have visited
                visited.add(other.obj_id)

                # connect
                query = f"""
                    MATCH (a:{entity.class_category}) WHERE a._obj_id='{entity.obj_id}'
                    MATCH (b) WHERE b._obj_id='{other.obj_id}'
                """
                if prop.is_inputoutput():
                    self.store.log.warning(
                        f"Can't have an INOUT relation property: {entity.name}.{prop.name}"
                    )
                    continue
                if prop.is_output():
                    query += f"""
                        MERGE (a)-[r:{prop.name}]->(b)
                    """
                elif prop.is_input():
                    query += f"""
                        MERGE (a)<-[r:{prop.name}]-(b)
                    """
                query += " SET r._property = true"
                if prop.container_type == PropertyContainer.ARRAY:
                    query += f" SET r._index = {i}"
                self.write_query(query)
                i += 1

            # detach any none visited relations to this property
            query = ""
            if prop.is_output():
                query += f"""
                    MATCH (a:{entity.class_category})-[r:{prop.name}]->(b)
                """
            elif prop.is_input():
                query += f"""
                    MATCH (a:{entity.class_category})<-[r:{prop.name}]-(b)
                """
            query += f"""
                WHERE a._obj_id='{entity.obj_id}' AND NOT b._obj_id IN {list(visited)}
            """
            if prop.is_member():
                query += """
                    DETACH DELETE b
                """
            else:
                query += """
                    DELETE r
                """
            self.write_query(query)

    def _sync_properties(self, entity, required_only=False):
        """
        Synchronize entity properties from the graph database.

        Loads current property values from the database into the entity object,
        handling both node properties and relationship properties with proper
        type conversion. Recursively synchronizes child objects and maintains
        array ordering through sequence attributes.

        Referenced objects are fetched by default, this means after sync
        there should be no unresolved reference members. These member objects
        however are not synced - they have to be synced separately.
        """

        # seperate into links and node props
        node_props = []
        relation_props = []
        for prop_name in entity.properties:
            prop = entity.properties[prop_name]

            # skip
            if required_only and not prop.required:
                continue

            # add
            if prop.prop_type == PropertyType.OBJECT:
                relation_props.append(prop)
            else:
                node_props.append(prop)

        # custom properties - never required
        if not required_only:

            # custom node properties
            query = f"""
                MATCH (e:{entity.class_category}) WHERE e._obj_id='{entity.obj_id}'
                RETURN DISTINCT properties(e) AS node_props
            """
            results = self.read_query(query)
            for result in results:
                for prop_name in result["node_props"]:

                    # skip dunders or repeats
                    if prop_name.startswith("_"):
                        continue
                    if entity.get_property(prop_name) is not None:
                        continue

                    # get value to infer type from
                    prop_value = result["node_props"][prop_name]
                    prop_type = None
                    if isinstance(prop_value, int):
                        prop_type = int
                    elif isinstance(prop_value, bool):
                        prop_type = bool
                    elif isinstance(prop_value, float):
                        prop_type = float
                    elif isinstance(prop_value, str):
                        prop_type = str
                    elif isinstance(prop_value, list):
                        if len(prop_value) > 0:
                            element_value = prop_value[0]
                            if isinstance(element_value, int):
                                prop_type = [int]
                            elif isinstance(element_value, bool):
                                prop_type = [bool]
                            elif isinstance(element_value, float):
                                prop_type = [float]
                            elif isinstance(element_value, str):
                                prop_type = [str]
                            else:
                                self.store.log.warning(
                                    f"Defaulting {entity.name}.{prop_name} to string array"
                                )
                                prop_type = [str]
                    else:
                        self.store.log.warning(
                            f"Defaulting {entity.name}.{prop_name} to string"
                        )
                        prop_type = str

                    node_props.append(entity.add_property(prop_name, prop_type))

        # get and read the basic nodal props
        if node_props:
            prop_queries = []
            for prop in node_props:
                prop_queries.append(f"e.{prop.name} AS {prop.name}")
            query = (
                f"MATCH (e:{entity.class_category}) WHERE e._obj_id='{entity.obj_id}' RETURN\n"
                + ",\n".join(prop_queries)
            )
            results = self.read_query(query)
            if len(results) == 1:
                result = results[0]
                for prop in node_props:

                    # prop not in query
                    if result[prop.name] is None:
                        self.store.log.warning(
                            f"Skipping sync for: {prop.name} as not in results"
                        )
                        prop.set_to_default()
                        continue

                    # assign
                    if prop.container_type == PropertyContainer.VALUE:
                        if prop.prop_type == PropertyType.DATETIME:
                            prop.value = Datetime(result[prop.name])
                        elif prop.prop_type == PropertyType.VERSION:
                            prop.value = Version(result[prop.name])
                        elif prop.prop_type == PropertyType.URI:
                            prop.value = URI(result[prop.name])
                        elif prop.prop_type == PropertyType.PACKAGE:
                            prop.value = Package(result[prop.name])
                        elif prop.prop_type == PropertyType.TYPE:
                            type_name = TypeName(result[prop.name])
                            type_class = self.store.factory.resolve(type_name)
                            prop.value = Type(
                                type_class=type_class, type_name=type_name
                            )
                        else:
                            prop.value = result[prop.name]
                    elif prop.container_type == PropertyContainer.ARRAY:
                        if prop.prop_type == PropertyType.DATETIME:
                            for entry in result[prop.name]:
                                prop.value.append(Datetime(entry))
                        elif prop.prop_type == PropertyType.VERSION:
                            for entry in result[prop.name]:
                                prop.value.append(Version(entry))
                        elif prop.prop_type == PropertyType.URI:
                            for entry in result[prop.name]:
                                prop.value.append(URI(entry))
                        elif prop.prop_type == PropertyType.PACKAGE:
                            for entry in result[prop.name]:
                                prop.value = Package(entry)
                        elif prop.prop_type == PropertyType.TYPE:
                            for entry in result[prop.name]:
                                type_name = TypeName(entry)
                                type_class = self.store.factory.resolve(type_name)
                                prop.value = Type(
                                    type_class=type_class, type_name=type_name
                                )
                        else:
                            prop.value = result[prop.name]

        # deal with references & objects
        entities_to_sync = set()
        for prop in relation_props:

            # query based on direction
            if prop.is_inputoutput():
                self.store.log.warning(
                    f"Can't have an INOUT relation property: {entity.name}.{prop.name}"
                )
                continue
            if prop.is_output():
                query = f"""
                    MATCH (a:{entity.class_category})-[r:{prop.name}]->(b) 
                """
            elif prop.is_input():
                query = f"""
                    MATCH (a:{entity.class_category})<-[r:{prop.name}]-(b) 
                """
            query += f"""
                WHERE a._obj_id='{entity.obj_id}'
                RETURN DISTINCT b._obj_id AS id
            """

            # Order the returning data
            # TODO : actually order by index, regardless of neo4j being asked,
            # the JSON data returned is not guaranteed to be ordered
            if prop.container_type == PropertyContainer.ARRAY:
                query += ", r._index AS index ORDER BY index ASC"

            # execute
            results = self.read_query(query)

            # process the results
            objs = []
            for result in results:
                obj = self.fetch([result["id"]])
                obj = obj[0] if obj else None

                # sync any members
                if obj is not None:
                    if prop.is_member_object():
                        entities_to_sync.add(obj)
                    objs.append(obj)

            # can't link back
            if entity in objs:
                raise RMTCException(
                    f"Cycle in sync found {objs} is connected to {entity.name}"
                )

            # any members that have vanished mark for removal
            # disable update broadcasting as going to access value
            if prop.is_member():
                prop.broadcaster.set_enabled(False)
                for obj in prop.array_value:
                    if obj not in objs:
                        self.store.remove_entity(obj)
                prop.broadcaster.set_enabled(True)

            # assign value
            prop.array_value = objs

        self.sync(list(entities_to_sync))

    @abstractmethod
    def read_query(self, query):
        """Execute a read-only Cypher query against the graph database."""
        pass

    @abstractmethod
    def write_query(self, query):
        """Execute a write Cypher query against the graph database."""
        pass


class CypherQueries(Queries):
    """
    Cypher-based query implementation for graph database operations.

    The CypherQueries class provides concrete implementations of RMTC query
    operations using the Cypher query language for graph databases. It handles
    complex relationship traversals and entity lookups optimized for the RMTC
    entity relationship model.

    This implementation is designed to work with graph databases that support
    Cypher queries, such as Neo4j or Apache AGE, and provides efficient
    querying capabilities for ML experiment tracking and artifact management.

    Queries return entity IDs - fetching, syncing etc. ops are performed directly
    with the connection.
    """

    def get_runs(
        self,
        name=None,
        model=None,
        dataset=None,
        checkpoint=None,
        trainer=None,
        result_checkpoint=None,
        result_weights=None,
        solution=None,
    ):
        """
        Query training runs by their input and output relationships.

        Searches for training runs based on their relationships to various entities
        including input models, datasets, trainers, and output artifacts. The method
        handles both unambiguous relationships (where relationship type doesn't matter)
        and ambiguous relationships (where specific relationship types are required).
        """

        # early out with every run if no clauses
        if (
            name is None
            and model is None
            and dataset is None
            and checkpoint is None
            and trainer is None
            and result_checkpoint is None
            and result_weights is None
        ):
            return self._get_entity(category="Run")

        entity_obj_ids = []

        # if name is specified get that first
        if name is not None:
            entity_obj_ids = self._get_entity(category="Run", name=name)

        # unambiguous
        clauses = []
        if model is not None:
            clauses.append(f"WHERE n._obj_id='{model.obj_id}'")
        if trainer is not None:
            clauses.append(f"WHERE n._obj_id='{trainer.obj_id}'")
        if dataset is not None:
            clauses.append(f"WHERE n._obj_id='{dataset.obj_id}'")
        if solution is not None:
            clauses.append(f"WHERE n._obj_id='{solution.obj_id}'")
        if len(clauses) > 0:
            query = f"""
                MATCH (r:Run)-[]-(n) {" OR ".join(clauses)} RETURN DISTINCT r._obj_id AS id
            """
            results = self.connection.read_query(query)
            for result in results:
                entity_obj_ids.append(result["id"])

        # ambiguous - fully qualified relation
        if checkpoint is not None:
            query = f"""
                MATCH (r:Run)-[:checkpoints]->(n) WHERE n._obj_id='{checkpoint.obj_id}' 
                RETURN r._obj_id AS id
            """
            results = self.connection.read_query(query)
            for result in results:
                entity_obj_ids.append(result["id"])
        if result_weights is not None:
            query = f"""
                MATCH (r:Run)-[:result_weights]->(n) WHERE n._obj_id='{result_weights.obj_id}'
                RETURN r._obj_id AS id
            """
            results = self.connection.read_query(query)
            for result in results:
                entity_obj_ids.append(result["id"])
        if result_checkpoint is not None:
            query = f"""
                MATCH (r:Run)-[:result_checkpoint]->(n) WHERE n._obj_id='{result_checkpoint.obj_id}'
                RETURN r._obj_id AS id
            """
            results = self.connection.read_query(query)
            for result in results:
                entity_obj_ids.append(result["id"])

        return entity_obj_ids

    def get_models(self, name=None, version=None, model_license=None):
        """Query models by name, version, and license criteria."""
        return self._get_entity(
            category="Model",
            name=name,
            version=version,
            entity_license=model_license,
        )

    def get_datasets(self, name=None, version=None, dataset_license=None):
        """Query datasets by name, version, and license criteria."""
        return self._get_entity(
            category="Dataset",
            name=name,
            version=version,
            entity_license=dataset_license,
        )

    def get_solutions(self, name=None):
        """Query solutions by name."""
        return self._get_entity(category="Solution", name=name)

    def get_entities(self, name=None, category=None):
        """Query entities by name and type."""
        return self._get_entity(name=name, category=category)

    def get_sources(self, entities):
        obj_ids = [entity.obj_id for entity in entities]
        query = f"""
                MATCH (b)-[]->(a) WHERE a._obj_id IN {obj_ids}
                RETURN b._obj_id AS id
            """
        results = self.connection.read_query(query)
        return [result["id"] for result in results]

    def get_related(self, entities):
        obj_ids = [entity.obj_id for entity in entities]
        query = f"""
                MATCH (a)-[]-(b) WHERE a._obj_id IN {obj_ids}
                RETURN b._obj_id AS id
            """
        results = self.connection.read_query(query)
        return [result["id"] for result in results]

    def get_descendents(self, entities):
        obj_ids = [entity.obj_id for entity in entities]
        query = f"""
                MATCH (a)-[:ancestors]->(b) WHERE a._obj_id IN {obj_ids}
                RETURN b._obj_id AS id
            """
        results = self.connection.read_query(query)
        return [result["id"] for result in results]

    def get_derivatives(self, entities):
        obj_ids = [entity.obj_id for entity in entities]
        query = f"""
                MATCH (a)-[]->(b) WHERE a._obj_id IN {obj_ids}
                RETURN b._obj_id AS id
            """
        results = self.connection.read_query(query)
        return [result["id"] for result in results]

    def get_licenses(self, name=None, version=None):
        """Query licenses by name and version."""
        return self._get_entity(category="License", name=name, version=version)

    def get_inferences(self, name=None, weights=None, model=None, asset=None):
        """Query inferences by their related entities."""

        # no conditions
        if name is None and weights is None and model is None and asset is None:
            return self._get_entity(category="Inference")

        entity_obj_ids = []

        # get generic entities first
        if name is not None:
            entity_obj_ids = self._get_entity(category="Inference", name=name)

        # tack on the other objects
        clauses = []
        if weights is not None:
            clauses.append(f" b._obj_id='{weights.obj_id}'")
        if model is not None:
            clauses.append(f" b._obj_id='{model.obj_id}'")
        if asset is not None:
            clauses.append(f" b._obj_id='{asset.obj_id}'")
        clause = ""
        if len(clauses) > 0:
            clause = f"WHERE {' OR '.join(clauses)}"
        query = f"""
            MATCH (i:Inference)-[]-(b) {clause}
            RETURN DISTINCT i._obj_id AS id
        """
        results = self.connection.read_query(query)
        for result in results:
            entity_obj_ids.append(result["id"])
        return entity_obj_ids

    def get_assets(self, uri=None, name=None, asset_license=None, version=None):
        """
        Query assets by URI pattern.

        Searches for asset entities using URI pattern matching. Currently only
        implements URI-based filtering with regex pattern matching.
        """
        entity_obj_ids = []

        if uri is None:
            entity_obj_ids = self._get_entity(
                category="Asset",
                name=name,
                entity_license=asset_license,
                version=version,
            )

        query = f"""
            MATCH (n:Asset) WHERE n.uri = '{uri}' AND n._store='{self.connection.store.name}'
            RETURN DISTINCT n._obj_id AS id
        """
        results = self.connection.read_query(query)
        for result in results:
            entity_obj_ids.append(result["id"])
        return entity_obj_ids

    def get_timestamps(self, entities):
        obj_ids = [entity.obj_id for entity in entities]
        query = f"""
            MATCH (a) WHERE a._obj_id IN {obj_ids}
            RETURN a._timestamp AS timestamp
        """
        results = self.connection.read_query(query)
        timestamps = []
        for result in results:
            if result["timestamp"] is not None:
                timestamps.append(Datetime(string=result["timestamp"]))
            else:
                timestamps.append(None)
        return timestamps

    def _get_entity(
        self,
        category=None,
        name=None,
        entity_license=None,
        version=None,
        greedy=True,
    ):
        """
        Generic entity query method with flexible filtering criteria.

        Provides a unified query interface for finding entities by type, name,
        version, and license. Supports regex pattern matching for name and
        version fields, and relationship-based filtering for licenses.

        The method performs a two-stage query:
        1. Filter by entity type, name, and version using node properties
        2. Further filter by license using relationship traversal if specified
        """

        # fail if no clauses
        if (
            category is None
            and name is None
            and entity_license is None
            and version is None
        ):
            raise RMTCException("No entity type specified for query")

        entity_obj_ids = []

        # early out and warn if key clauses not satisified
        if name is None and entity_license is None and version is None:
            self.connection.store.log.warning(f"Requesting all {category}s")
            query = f"""
                MATCH (n:{category}) WHERE n._store='{self.connection.store.name}' 
                RETURN DISTINCT n._obj_id AS id
            """
            results = self.connection.read_query(query)
            for result in results:
                entity_obj_ids.append(result["id"])
            return entity_obj_ids

        clauses = []
        if name is not None:
            anything = ""
            if greedy:
                anything = ".*"
            clauses.append(f"n.name =~ '{name}{anything}'")
        if version is not None:
            clauses.append(f"n.version = '{version}'")
        node_type = ""
        if category is not None:
            node_type = f":{category}"
        clause = ""
        if len(clauses) > 0:
            clause = f"AND ({' OR '.join(clauses)})"
        query = f"""
            MATCH (n{node_type}) WHERE n._store='{self.connection.store.name}' {clause}
            RETURN DISTINCT n._obj_id AS id
        """
        results = self.connection.read_query(query)
        for result in results:
            entity_obj_ids.append(result["id"])
        if entity_license is not None:
            clause = ""
            if len(entity_obj_ids) > 0:
                clause = f" AND n._obj_id IN {entity_obj_ids} "
            query = f"""
                MATCH (n)-[:licenses]->(l:License) WHERE l._obj_id='{entity_license.obj_id}' {clause}
                RETURN DISTINCT n._obj_id AS id
            """
            results = self.connection.read_query(query)
            entity_obj_ids = []
            for result in results:
                entity_obj_ids.append(result["id"])
        return entity_obj_ids
