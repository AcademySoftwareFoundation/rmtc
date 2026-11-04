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

import json
import re

from abc import abstractmethod

from rmtc.track.store import Queries, Connection, Proxy
from rmtc.system.objects import PropertyType, PropertyContainer, Property, Unlocked
from rmtc.system import (
    Datetime,
    Version,
    URI,
    Type,
    RMTCException,
    Package,
    TypeName,
    Inhibitor,
)


class CypherConnection(Connection):
    """
    Cypher-based database connection for graph database operations.

    The CypherConnection class provides a concrete implementation of the RMTC
    Connection interface for graph databases that support the Cypher query
    language (such as Neo4j or Apache AGE). It handles entity persistence,
    property synchronization, and relationship management using Cypher queries.
    """

    def __init__(
        self,
        store,
        queries=None,
    ):
        """Initialize CypherConnection with store and CypherQueries."""
        if queries is None:
            queries = CypherQueries(self)
        super(CypherConnection, self).__init__(
            store=store,
            queries=queries,
        )
        self._use_dt = store.supports_datetime()

    def delete_all(self, store_name=None):
        """Delete all nodes and relationships from the graph database.

        This method performs a complete database wipe by executing a Cypher
        query that matches all nodes and detaches/deletes them along with
        their relationships. This operation is only allowed in testing mode
        to prevent accidental data loss.
        """
        if store_name is None:
            store_name = self.store.name
        if self.store.immutable:
            raise RMTCException(f"Failed to delete immutable storage {self.store.uri}")
        query = """
            MATCH (e) WHERE e._store=$store
            DETACH DELETE e RETURN count(e) AS deleted
        """
        result = self.write_query(query, store=store_name)
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
        if self.store.immutable:
            raise RMTCException("Deleting entities inside immutable store")
        ids = []
        for entity in entities:
            ids.append(entity.obj_id)
        query = """
            MATCH (e) WHERE e._obj_id IN $obj_ids AND e._store=$store
            DETACH DELETE e
            RETURN count(e) AS deleted
        """
        result = self.write_query(query, obj_ids=ids, store=self.store.name)
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
            if not entity.is_tracked():
                raise RMTCException(f"Untracked entity asked to be created {entity}")
            if entity.class_category is None:
                raise RMTCException(
                    f"Some issues with {entity} / {entity.class_category}"
                )
            if not entity.class_category.isalnum():
                raise RMTCException(
                    f"Invalid category for {entity} - {entity.class_category}"
                )
            label = entity.class_category
            type_name = self.store.factory.resolve_inverse(entity.__class__)
            datetime_pushed = "datetime($pushed)" if self._use_dt else "$pushed"
            datetime_updated = "datetime($updated)" if self._use_dt else "$updated"
            query = f"""
                CREATE (
                    e:{label}
                    {{
                        _type_name:$type_name,
                        _store:$store_name,
                        _pushed_at:{datetime_pushed},
                        _updated_at:{datetime_updated},
                        _obj_id:$obj_id
                    }}
                )
                RETURN e._obj_id AS id
            """
            result = self.write_query(
                query,
                type_name=str(type_name),
                store_name=self.store.name,
                obj_id=entity.obj_id,
                pushed=str(Datetime()),
                updated=str(entity.updated_at),
            )
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

        This returns the entities in the same order as the IDs

        Reads only the required properties.
        """
        if len(ids) == 0:
            return []
        # NOTE: we do this sequentially as this ensures
        # entity order matches ID order
        entities = []
        for obj_id in ids:
            query = """
                MATCH (e) WHERE e._obj_id=$obj_id AND e._store=$store
                RETURN
                e._obj_id AS id,
                e._type_name AS type_name,
                e._updated_at AS updated_at
            """
            results = self.read_query(
                query,
                obj_id=obj_id,
                store=self.store.name,
            )
            for result in results:
                obj_id = result["id"]
                type_name = TypeName(result["type_name"])
                entity = None
                try:
                    entity = self.store.factory.create(type_name)
                except RMTCException:
                    self.store.log.warning(
                        f"Cannot create instance of {type_name} for {obj_id}, using proxy entity"
                    )
                if entity is None:
                    entity = Proxy(type_name.category)
                    self.store.add_entity(obj_id, entity)
                    self._sync_properties(entity, required_only=True)
                else:
                    entity.reset_create()
                    entity.reset_update()
                    entity.mark_for_sync()
                    self.store.add_entity(obj_id, entity)
                    self._sync_properties(entity, required_only=True)
                    entity.mark_for_sync()
                timestamp = result["updated_at"]
                if self._use_dt:
                    timestamp = timestamp.isoformat()
                entity.updated_at = Datetime(timestamp)
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

        # check category
        if not entity.class_category.isalnum():
            raise RMTCException(f"Invalid category {entity.class_category}")

        # query the timestamp
        timestamps = self.queries.get_timestamps([entity])
        if len(timestamps) > 0 and timestamps[0] is not None:
            if timestamps[0] > entity.updated_at:
                raise RMTCException(
                    f"Stale {entity} is not updated, remote store is newer"
                )

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

            # build first query entry
            query = f"""
                MATCH (e:{entity.class_category}) WHERE 
                e._obj_id=$obj_id AND e._store=$store
            """

            # add in timestamp
            updated = "$updated"
            if self._use_dt:
                updated = "datetime($updated)"
            query += f"SET e._updated_at = {updated}\n"

            # build params
            params = {}
            for prop in node_props:

                # cache names
                prop_name = prop.name
                prop_type = prop.prop_type

                # check name
                if not Property.valid_name(prop_name):
                    self.log.warning(f"Insecure prop name '{prop_name}'")
                    continue

                # dicts currently don't save to the store
                if prop_type == PropertyType.DICT:
                    self.log.warning(f"Dictionaries not supported: '{prop_name}'")
                    continue

                # datetime arrays cannot be well managed
                if (
                    prop_type == PropertyType.DATETIME
                    and prop.container_type == PropertyContainer.ARRAY
                ):
                    self.log.warning(f"Datetime arrays not supported: '{prop_name}'")
                    continue

                # build params
                if prop.container_type == PropertyContainer.VALUE:
                    if prop_type in [
                        PropertyType.VERSION,
                        PropertyType.PACKAGE,
                        PropertyType.URI,
                        PropertyType.DATETIME,
                    ]:
                        params[prop_name] = str(prop.value)
                    elif prop_type == PropertyType.TYPE:
                        type_name = self.store.factory.resolve_inverse(
                            prop.value.type_class
                        )
                        params[prop_name] = str(type_name) or str()
                    elif prop_type == PropertyType.DICT:
                        params[prop_name] = json.dumps(prop.value)
                    elif prop_type == PropertyType.ENUM:
                        params[prop_name] = prop.value.name or str()
                    else:
                        params[prop_name] = prop.value
                else:
                    if prop_type == PropertyType.TYPE:
                        values = []
                        for value in prop.value:
                            type_name = self.store.factory.resolve_inverse(
                                value.type_class
                            )
                            values.append(str(type_name))
                        params[prop_name] = values
                    elif prop_type == PropertyType.DICT:
                        params[prop_name] = [json.dumps(value) for value in prop.value]
                    elif prop_type in [
                        PropertyType.VERSION,
                        PropertyType.PACKAGE,
                        PropertyType.URI,
                        PropertyType.DATETIME,
                    ]:
                        params[prop_name] = [str(value) for value in prop.value]
                    elif prop_type == PropertyType.ENUM:
                        params[prop_name] = [value.name for value in prop.value]
                    else:
                        params[prop_name] = prop.value

                # add in query
                # TODO : arrays of datetimes are not easily parameterised
                if prop_type == PropertyType.DATETIME and self._use_dt:
                    if prop.container_type == PropertyContainer.VALUE:
                        query += f"SET e.{prop_name} = datetime(${prop_name})\n"
                    else:
                        raise NotImplementedError()
                else:
                    query += f"SET e.{prop_name} = ${prop_name}\n"

            # run query
            self.write_query(
                query,
                obj_id=entity.obj_id,
                updated=str(entity.updated_at),
                store=self.store.name,
                **params,
            )

        # assign relation props
        for prop in relation_props:
            i = 0

            # visited objects
            visited = set()

            # any item connected needs to also be created in the DB and push
            if prop.is_member_object():
                self.create(prop.array_value)
                self.update(prop.array_value)

            # get and check prop name
            prop_name = prop.name
            if not Property.valid_name(prop_name):
                raise RMTCException(f"Insecure prop name '{prop_name}'")

            # update
            for other in prop.array_value:

                # empty
                if other is None:
                    self.store.log.warning(
                        f"None element inside array property {entity.name}.{prop_name}"
                    )
                    continue

                # not tracked in the DB
                if not other.is_tracked():
                    continue

                # record which we have visited
                visited.add(other.obj_id)

                # connect
                query = f"""
                    MATCH (a:{entity.class_category}) 
                    WHERE a._obj_id=$a_obj_id AND a._store=$store
                    MATCH (b:{other.class_category}) WHERE b._obj_id=$b_obj_id AND b._store=$store
                """
                if prop.is_inputoutput():
                    self.store.log.warning(
                        f"Can't have an INOUT relation property: {entity.name}.{prop_name}"
                    )
                    continue

                if prop.is_output():
                    query += f"""
                        MERGE (a)-[r:{prop_name}]->(b)
                    """
                elif prop.is_input():
                    query += f"""
                        MERGE (a)<-[r:{prop_name}]-(b)
                    """
                query += " SET r._property = true"
                if prop.is_member():
                    query += " SET r._member = true"
                if prop.container_type == PropertyContainer.ARRAY:
                    query += f" SET r._index = {i}"
                self.write_query(
                    query,
                    a_obj_id=entity.obj_id,
                    b_obj_id=other.obj_id,
                    store=self.store.name,
                )
                i += 1

            # detach any none visited relations to this property
            query = ""
            if prop.is_output():
                query += f"""
                    MATCH (a:{entity.class_category})-[r:{prop_name}]->(b)
                """
            elif prop.is_input():
                query += f"""
                    MATCH (a:{entity.class_category})<-[r:{prop_name}]-(b)
                """
            query += """
                WHERE a._obj_id=$a_obj_id AND
                NOT b._obj_id IN $b_obj_ids AND 
                a._store=$store AND 
                b._store=$store
            """
            if prop.is_member():
                query += """
                    DETACH DELETE b
                """
            else:
                query += """
                    DELETE r
                """
            self.write_query(
                query,
                a_obj_id=entity.obj_id,
                b_obj_ids=list(visited),
                store=self.store.name,
            )

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

        # check category
        if not entity.class_category.isalnum():
            raise RMTCException(f"Invalid category {entity.class_category}")

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
        required_only = False
        if not required_only:

            # custom node properties
            query = f"""
                MATCH (e:{entity.class_category}) WHERE e._obj_id=$obj_id AND e._store=$store
                RETURN properties(e) AS node_props
            """
            results = self.read_query(
                query,
                obj_id=entity.obj_id,
                store=self.store.name,
            )
            for result in results:
                for prop_name in result["node_props"]:

                    # skip dunders or repeats
                    if prop_name.startswith("_"):
                        continue
                    if entity.get_property(prop_name) is not None:
                        continue

                    # get value to infer type from
                    prop_value = result["node_props"][prop_name]
                    prop_type = str
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
                    prop = entity.add_property(prop_name, prop_type)
                    node_props.append(prop)

        # get and read the basic nodal props
        if node_props:
            prop_queries = []
            for prop in node_props:
                prop_name = prop.name
                if not Property.valid_name(prop_name):
                    raise RMTCException(f"Insecure prop name '{prop_name}'")
                prop_queries.append(f"e.{prop_name} AS {prop_name}")
            query = f"""
                MATCH (e:{entity.class_category}) 
                WHERE e._obj_id=$obj_id AND e._store=$store RETURN
                """ + ",\n".join(
                prop_queries
            )
            results = self.read_query(
                query,
                obj_id=entity.obj_id,
                store=self.store.name,
            )
            if len(results) == 1:
                result = results[0]
                for prop in node_props:

                    # get and check prop name
                    prop_name = prop.name
                    if not Property.valid_name(prop_name):
                        raise RMTCException(f"Insecure prop name '{prop_name}'")

                    # prop not in query
                    if result[prop_name] is None:
                        if prop.readonly:
                            # a missing readonly (identity) property means the
                            # node predates it - the entity keeps its
                            # construction-time stamp, which is a fabrication;
                            # run the backfill migration
                            self.store.log.warning(
                                f"Node for '{entity.name}' has no '{prop_name}' "
                                "in the store; keeping the construction-time "
                                "value - run the backfill migration"
                            )
                        else:
                            self.store.log.debug(
                                f"Skipping sync for: {prop_name} as not in "
                                f"results for {entity.name}"
                            )
                        with Inhibitor(prop.broadcaster), Unlocked(prop):
                            prop.set_to_default()
                        continue

                    # assign
                    if prop.container_type == PropertyContainer.VALUE:
                        value = None
                        if prop.prop_type == PropertyType.DATETIME:
                            if self._use_dt:
                                value = Datetime(result[prop_name].isoformat())
                            else:
                                value = Datetime(result[prop_name])
                        elif prop.prop_type == PropertyType.DICT:
                            value = json.loads(result[prop_name])
                        elif prop.prop_type == PropertyType.VERSION:
                            value = Version(result[prop_name])
                        elif prop.prop_type == PropertyType.URI:
                            value = URI(result[prop_name])
                        elif prop.prop_type == PropertyType.PACKAGE:
                            value = Package(result[prop_name])
                        elif prop.prop_type == PropertyType.TYPE:
                            type_name = TypeName(result[prop_name])
                            type_class = self.store.factory.resolve(type_name)
                            value = Type(type_class=type_class, type_name=type_name)
                        else:
                            value = result[prop_name]

                        # assign
                        with Inhibitor(prop.broadcaster), Unlocked(prop):
                            prop.value = value

                    elif prop.container_type == PropertyContainer.ARRAY:
                        values = []
                        if prop.prop_type == PropertyType.DATETIME:
                            for entry in result[prop_name]:
                                if self._use_dt:
                                    values.append(Datetime(entry.isoformat()))
                                else:
                                    values.append(Datetime(entry))
                        elif prop.prop_type == PropertyType.DICT:
                            for entry in result[prop_name]:
                                values.append(json.loads(entry))
                        elif prop.prop_type == PropertyType.VERSION:
                            for entry in result[prop_name]:
                                values.append(Version(entry))
                        elif prop.prop_type == PropertyType.URI:
                            for entry in result[prop_name]:
                                values.append(URI(entry))
                        elif prop.prop_type == PropertyType.PACKAGE:
                            for entry in result[prop_name]:
                                values.append(Package(entry))
                        elif prop.prop_type == PropertyType.TYPE:
                            for entry in result[prop_name]:
                                type_name = TypeName(entry)
                                type_class = self.store.factory.resolve(type_name)
                                type_value = Type(
                                    type_class=type_class, type_name=type_name
                                )
                                values.append(type_value)
                        else:
                            values = result[prop_name]

                        # assign
                        with Inhibitor(prop.broadcaster), Unlocked(prop):
                            prop.value = values

        # deal with references & objects
        entities_to_sync = set()
        for prop in relation_props:

            # get and check prop name
            prop_name = prop.name
            if not Property.valid_name(prop_name):
                raise RMTCException(f"Insecure prop name '{prop_name}'")

            # query based on direction
            if prop.is_inputoutput():
                self.store.log.warning(
                    f"Can't have an INOUT relation property: {entity.name}.{prop_name}"
                )
                continue
            if prop.is_output():
                query = f"""
                    MATCH (a:{entity.class_category})-[r:{prop_name}]->(b) 
                """
            elif prop.is_input():
                query = f"""
                    MATCH (a:{entity.class_category})<-[r:{prop_name}]-(b) 
                """
            query += """
                WHERE a._obj_id=$obj_id AND a._store=$store AND b._store=$store
                RETURN b._obj_id AS id
            """

            # get index if an array
            if prop.container_type == PropertyContainer.ARRAY:
                query += ", r._index AS index"

            # execute
            results = self.read_query(
                query,
                obj_id=entity.obj_id,
                store=self.store.name,
            )

            # order the returning data as the JSON values are unordered
            if prop.container_type == PropertyContainer.ARRAY:
                results = sorted(results, key=lambda result: result["index"])

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
                with Inhibitor(prop.broadcaster):
                    for obj in prop.array_value:
                        if obj not in objs:
                            self.store.remove_entity(obj)

            # assign value
            with Inhibitor(prop.broadcaster), Unlocked(prop):
                prop.array_value = objs

        self.sync(list(entities_to_sync))

    @property
    def use_datetime(self):
        """Does the store hold native datetimes rather than ISO strings."""
        return self._use_dt

    @abstractmethod
    def read_query(self, query, **kwargs):
        """Execute a read-only Cypher query against the graph database."""
        pass

    @abstractmethod
    def write_query(self, query, **kwargs):
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
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """
        Query training runs by name, creation window and relationships.

        Runs are filtered by their relationships to input models, datasets and
        trainers, and to output artifacts. Setting latest returns the most
        recently created match.
        """

        # properties
        clause, params = self._build_filters(
            "r",
            name=name,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
        )
        query = f"MATCH (r:Run) WHERE r._store=$store {clause}\n"

        # connections - IN properties are stored (owner)<-[:prop]-(value),
        # OUT properties (owner)-[:prop]->(value); arrows must match
        if model is not None:
            query += "MATCH (r)<-[:model]-(m) WHERE m._obj_id=$model\n"
            params["model"] = model.obj_id
        if trainer is not None:
            query += "MATCH (r)<-[:trainer]-(t) WHERE t._obj_id=$trainer\n"
            params["trainer"] = trainer.obj_id
        if dataset is not None:
            query += "MATCH (r)<-[:dataset]-(d) WHERE d._obj_id=$dataset\n"
            params["dataset"] = dataset.obj_id
        if solution is not None:
            query += "MATCH (r)<-[:solution]-(s) WHERE s._obj_id=$solution\n"
            params["solution"] = solution.obj_id
        if checkpoint is not None:
            query += "MATCH (r)<-[:checkpoint]-(c) WHERE c._obj_id=$checkpoint\n"
            params["checkpoint"] = checkpoint.obj_id
        if result_weights is not None:
            query += (
                "MATCH (r)-[:result_weights]->(rw) WHERE rw._obj_id=$result_weights\n"
            )
            params["result_weights"] = result_weights.obj_id
        if result_checkpoint is not None:
            query += "MATCH (r)-[:result_checkpoints]->(rc) WHERE rc._obj_id=$result_checkpoint\n"
            params["result_checkpoint"] = result_checkpoint.obj_id

        # return
        tail, tail_params = self._build_tail("r", latest=latest, limit=limit)
        query += tail
        params.update(tail_params)

        # execute
        results = self.connection.read_query(
            query,
            store=self.connection.store.name,
            **params,
        )
        return self._resolve(results, latest=latest, limit=limit)

    def get_models(
        self,
        name=None,
        model_license=None,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Query models by name, creation window and license."""
        return self._get_entities(
            categories=["Model"],
            name=name,
            entity_license=model_license,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )

    def get_datasets(
        self,
        name=None,
        dataset_license=None,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Query datasets by name, creation window and license."""
        return self._get_entities(
            categories=["Dataset"],
            name=name,
            entity_license=dataset_license,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )

    def get_solutions(
        self,
        name=None,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Query solutions by name and creation window."""
        return self._get_entities(
            categories=["Solution"],
            name=name,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )

    def get_entities(
        self,
        name=None,
        categories=None,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Query entities by name, type and creation window."""
        return self._get_entities(
            name=name,
            categories=categories,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )

    def get_sources(self, entities, limit=None):
        obj_ids = [entity.obj_id for entity in entities]
        query = """
                MATCH (b)-[]->(a) WHERE a._obj_id IN $obj_ids AND a._store=$store AND b._store=$store
                RETURN b._obj_id AS id
            """
        limit = limit or self.connection.limit
        if limit is not None:
            query += """
                LIMIT $limit
            """
        results = self.connection.read_query(
            query, obj_ids=obj_ids, store=self.connection.store.name, limit=limit
        )
        return [result["id"] for result in results]

    def get_related(self, entities, limit=None):
        obj_ids = [entity.obj_id for entity in entities]
        query = """
                MATCH (a)-[]-(b) WHERE a._obj_id IN $obj_ids AND a._store=$store AND b._store=$store
                RETURN b._obj_id AS id
            """
        limit = limit or self.connection.limit
        if limit is not None:
            query += """
                LIMIT $limit
            """
        results = self.connection.read_query(
            query, obj_ids=obj_ids, store=self.connection.store.name, limit=limit
        )
        return [result["id"] for result in results]

    def get_descendents(self, entities, limit=None):
        obj_ids = [entity.obj_id for entity in entities]
        query = """
                MATCH (a)-[:ancestors]->(b) WHERE a._obj_id IN $obj_ids AND a._store=$store AND b._store=$store
                RETURN b._obj_id AS id
            """
        limit = limit or self.connection.limit
        if limit is not None:
            query += """
                LIMIT $limit
            """
        results = self.connection.read_query(
            query, obj_ids=obj_ids, store=self.connection.store.name, limit=limit
        )
        return [result["id"] for result in results]

    def get_derivatives(self, entities, limit=None):
        obj_ids = [entity.obj_id for entity in entities]
        query = """
                MATCH (a)-[]->(b) WHERE a._obj_id IN $obj_ids AND a._store=$store AND b._store=$store
                RETURN b._obj_id AS id
            """
        limit = limit or self.connection.limit
        if limit is not None:
            query += """
                LIMIT $limit
            """
        results = self.connection.read_query(
            query, obj_ids=obj_ids, store=self.connection.store.name, limit=limit
        )
        return [result["id"] for result in results]

    def get_licenses(
        self,
        name=None,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Query licenses by name and creation window."""
        return self._get_entities(
            categories=["License"],
            name=name,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
            latest=latest,
            limit=limit,
        )

    def get_inferences(
        self,
        name=None,
        weights=None,
        model=None,
        inputs=None,
        outputs=None,
        solution=None,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """Query inferences by name, creation window and related entities."""

        # properties
        clause, params = self._build_filters(
            "i",
            name=name,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
        )
        query = f"MATCH (i:Inference) WHERE i._store=$store {clause}\n"

        # connections - IN properties are stored (owner)<-[:prop]-(value),
        # OUT properties (owner)-[:prop]->(value); arrows must match
        if model is not None:
            query += "MATCH (i)<-[:model]-(m) WHERE m._obj_id=$model\n"
            params["model"] = model.obj_id
        if weights is not None:
            query += "MATCH (i)<-[:weights]-(w) WHERE w._obj_id=$weights\n"
            params["weights"] = weights.obj_id
        if inputs is not None:
            query += "MATCH (i)<-[:inputs]-(d) WHERE d._obj_id=$inputs\n"
            params["inputs"] = inputs.obj_id
        if outputs is not None:
            query += "MATCH (i)-[:outputs]->(o) WHERE o._obj_id=$outputs\n"
            params["outputs"] = outputs.obj_id
        if solution is not None:
            query += "MATCH (i)<-[:solution]-(s) WHERE s._obj_id=$solution\n"
            params["solution"] = solution.obj_id

        # return
        tail, tail_params = self._build_tail("i", latest=latest, limit=limit)
        query += tail
        params.update(tail_params)

        # execute
        results = self.connection.read_query(
            query,
            store=self.connection.store.name,
            **params,
        )
        return self._resolve(results, latest=latest, limit=limit)

    def get_assets(
        self,
        uri=None,
        name=None,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """
        Query assets by URI, name and creation window.

        The URI is matched exactly where given, alongside the shared name and
        instantiated_at filters.
        """

        # properties
        clause, params = self._build_filters(
            "n",
            name=name,
            exact=exact,
            version=version,
            instantiated_after=instantiated_after,
            instantiated_before=instantiated_before,
        )
        query = f"MATCH (n:Asset) WHERE n._store=$store {clause}\n"
        if uri is not None:
            query += "AND n.uri = $uri\n"
            params["uri"] = str(uri)

        # return
        tail, tail_params = self._build_tail("n", latest=latest, limit=limit)
        query += tail
        params.update(tail_params)

        # execute
        results = self.connection.read_query(
            query,
            store=self.connection.store.name,
            **params,
        )
        return self._resolve(results, latest=latest, limit=limit)

    def get_timestamps(self, entities):
        obj_ids = [entity.obj_id for entity in entities]
        query = """
            MATCH (a) WHERE a._obj_id IN $obj_ids AND a._store=$store
            RETURN a._updated_at AS updated_at
        """
        results = self.connection.read_query(
            query,
            obj_ids=obj_ids,
            store=self.connection.store.name,
        )
        timestamps = []
        for result in results:
            if result["updated_at"] is not None:
                timestamps.append(Datetime(string=result["updated_at"]))
            else:
                timestamps.append(None)
        return timestamps

    def _get_entities(
        self,
        categories=None,
        name=None,
        entity_license=None,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
        latest=False,
        limit=None,
    ):
        """
        Generic entity query with name, creation window and recency filtering.

        Entities are matched by category, name (exact or fuzzy) and an optional
        instantiated_at window, with licenses filtered by relationship traversal.
        Setting latest returns only the most recently created match.
        """

        # check category
        if categories is not None:
            for category in categories:
                if not category.isalnum():
                    raise RMTCException(f"Invalid category {category}")

        # fail if no clauses
        if (
            categories is None
            and name is None
            and entity_license is None
            and instantiated_after is None
            and instantiated_before is None
        ):
            raise RMTCException("No search items specified for get entity")

        # HACK: need at least an empty category
        if categories is None:
            categories = [None]

        rows = []
        for category in categories:
            node_type = ""
            if category is not None:
                node_type = f":{category}"

            # properties - rebuilt per category so the name pattern is never
            # rewritten across iterations
            clause, params = self._build_filters(
                "n",
                name=name,
                exact=exact,
                version=version,
                instantiated_after=instantiated_after,
                instantiated_before=instantiated_before,
            )
            query = f"MATCH (n{node_type}) WHERE n._store=$store {clause}\n"

            # connections
            if entity_license is not None:
                query += "MATCH (n)-[:licenses]->(l) WHERE l._obj_id=$entity_license\n"
                params["entity_license"] = entity_license.obj_id

            # return
            tail, tail_params = self._build_tail("n", latest=latest, limit=limit)
            query += tail
            params.update(tail_params)

            # execute
            results = self.connection.read_query(
                query,
                store=self.connection.store.name,
                **params,
            )
            rows.extend(results)

        return self._resolve(rows, latest=latest, limit=limit)

    def _build_filters(
        self,
        alias,
        name=None,
        exact=True,
        version=None,
        instantiated_after=None,
        instantiated_before=None,
    ):
        """
        Build the shared name and instantiated_at clauses for a node alias.

        Returns the clause string and its params. The clause is prefixed with
        AND so it appends to an existing WHERE.
        """
        clauses = []
        params = {}

        if name is not None:
            if exact:
                clauses.append(f"{alias}.name = $name")
                params["name"] = name
            else:
                # contains match, case insensitive - the name is escaped so
                # regex metacharacters in it are matched literally
                clauses.append(f"{alias}.name =~ $name")
                params["name"] = f"(?i).*{re.escape(name)}.*"

        if version is not None:
            clauses.append(f"{alias}.version = $version")
            params["version"] = str(version)

        if instantiated_after is not None:
            value = (
                "datetime($instantiated_after)"
                if self.connection.use_datetime
                else "$instantiated_after"
            )
            clauses.append(f"{alias}.instantiated_at >= {value}")
            params["instantiated_after"] = str(instantiated_after)

        if instantiated_before is not None:
            value = (
                "datetime($instantiated_before)"
                if self.connection.use_datetime
                else "$instantiated_before"
            )
            clauses.append(f"{alias}.instantiated_at <= {value}")
            params["instantiated_before"] = str(instantiated_before)

        clause = ""
        if len(clauses) > 0:
            clause = f"AND ({' AND '.join(clauses)})"
        return clause, params

    def _build_tail(self, alias, latest=False, limit=None):
        """
        Build the RETURN tail.

        AGE doesn't support DISTINCT and doesn't guarantee JSON row order, so
        no ORDER BY/LIMIT is applied here — every match is fetched and
        _resolve() sorts by instantiated_at and truncates client-side.
        """
        query = (
            f"RETURN {alias}._obj_id AS id, "
            f"{alias}.instantiated_at AS instantiated_at\n"
        )
        return query, {}

    @staticmethod
    def _resolve(rows, latest=False, limit=None):
        """
        Reduce result rows to ids, newest first.

        The category loop issues one query per category, so latest and limit
        must be reapplied across the combined rows.
        """
        rows = [row for row in rows if row.get("id") is not None]
        rows.sort(key=lambda row: str(row["instantiated_at"] or ""), reverse=True)
        if latest:
            rows = rows[:1]
        elif limit:
            rows = rows[:limit]
        return [row["id"] for row in rows]

    def get_recent_inference(self, solution):
        """Return the last chronological inference for the solution"""
        ids = self.get_inferences(solution=solution, latest=True)
        return ids[0] if ids else None

    def get_recent_run(self, solution):
        """Return the last chronological run for the solution"""
        ids = self.get_runs(solution=solution, latest=True)
        return ids[0] if ids else None

    def get_best_run(self, solution):
        """Return the run with the lowset metric"""
        query = """
            MATCH (r:Run)-[]-(n) WHERE n._obj_id=$solution AND n._store=$store
            RETURN r._obj_id AS id ORDER BY r.metric ASC
        """
        results = self.connection.read_query(
            query,
            solution=solution.obj_id,
            store=self.connection.store.name,
        )
        if len(results) > 0:
            return results[0]["id"]
        return None
