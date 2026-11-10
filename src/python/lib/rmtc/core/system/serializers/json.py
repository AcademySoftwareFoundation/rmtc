# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import json
import math

from rmtc.track.store import Proxy
from rmtc.system.objects import PropertyType, Unlocked
from rmtc.system import (
    URI,
    Type,
    Datetime,
    Version,
    Package,
    TypeName,
    Inhibitor,
    Serializer,
)


class JSONSerializer(Serializer):
    """
    JSON serialization handler for RMTC entities and properties.

    The JSONSerializer class provides bidirectional JSON serialization for RMTC
    entities, handling complex property types, object references, and nested
    structures. It converts RMTC objects to JSON and reconstructs objects from
    JSON data with proper type conversion. It knows nothing about HTTP - the
    REST response envelope is added by the Server.

    `objects` is the lookup table used when deserializing: entities already
    in it are reused rather than rebuilt, so deserializing the same entity
    twice, or a reference to one already loaded, gives back the same object.
    Serialization does not use it.
    """

    def serialize(self, objects):
        """
        Serialize objects into a JSON string.

        Args:
            objects (list): Objects to send, in order. A plain list - not the
                `self.objects` lookup table, which is only for deserializing.

        Returns:
            str: A JSON array, one element per object, each shaped as
                described in `serialize_object`. Non-finite floats are sent
                as null, so the string is always strict JSON.
        """
        serialized_objects = []

        for obj in objects:
            serialized_objects.append(self.serialize_object(obj))
        return json.dumps(serialized_objects, allow_nan=False)

    def serialize_object(self, obj=None):
        """
        Serialize a single entity to a plain dict (not a JSON string).

        Args:
            obj (Object): The entity/object to serialize.

        Returns:
            dict: `{"_id": <uuid str>, "_type_name": <typename str>, ...}`
                with one key per property on `obj`. Scalar property values
                are flattened directly; array property values are lists.
                Object-typed properties are encoded as:
                - `{"_id", "_type_name", "name"}` if the property is a
                  reference (`prop.member` is False), or
                - a nested dict (the recursive result of `serialize_object`),
                  if the property is a member (owned, `prop.member` is True).
                ENUM values are sent by name, TYPE values by type name and
                URI/Datetime/Version/Package values as strings, matching how
                the Cypher store writes them. NaN/Infinity floats and unset
                references are sent as null. Callers that need a JSON string
                must `json.dumps()` this themselves (with `allow_nan=False`),
                or call `serialize()`.
        """

        # internals
        members = {}
        members["_id"] = obj.obj_id
        members["_type_name"] = self._type_name(obj)

        # properties
        for prop in obj.properties.values():
            if prop.is_array():
                members[prop.name] = [self._to_json(prop, v) for v in prop.value]
            else:
                members[prop.name] = self._to_json(prop, prop.value)

        return members

    def _to_json(self, prop, value):
        """Convert one property value to its JSON form"""
        if value is None:
            return None

        prop_type = prop.prop_type

        if prop_type == PropertyType.OBJECT:
            if prop.member:
                return self.serialize_object(value)
            return {
                "_id": value.obj_id,
                "_type_name": self._type_name(value),
                "name": value.name,
            }
        if prop_type == PropertyType.NUMBER:
            return value if math.isfinite(value) else None
        if prop_type == PropertyType.ENUM:
            return value.name
        if prop_type == PropertyType.TYPE:
            if value.type_class is not None:
                return str(self.factory.resolve_inverse(value.type_class))
            return str(value.type_name)
        if prop_type in [
            PropertyType.URI,
            PropertyType.DATETIME,
            PropertyType.VERSION,
            PropertyType.PACKAGE,
        ]:
            return str(value)
        return value

    def _from_json(self, prop, json_value):
        """Convert one JSON value back to its property value"""
        prop_type = prop.prop_type
        if json_value is None:
            # non-finite floats are sent as null
            if prop_type == PropertyType.NUMBER:
                return float("nan")
            return None
        if prop_type == PropertyType.OBJECT:
            if prop.member:
                return self.deserialize_object(json_value)
            return self._resolve_reference(json_value)
        if prop_type == PropertyType.ENUM:
            return prop.type_class[json_value]
        if prop_type == PropertyType.TYPE:
            type_name = TypeName(json_value)
            return Type(type_class=self.factory.resolve(type_name), type_name=type_name)
        if prop_type == PropertyType.DATETIME:
            return Datetime(json_value)
        if prop_type == PropertyType.URI:
            return URI(json_value)
        if prop_type == PropertyType.VERSION:
            return Version(json_value)
        if prop_type == PropertyType.PACKAGE:
            return Package(json_value)
        return json_value

    def _get_or_create(self, obj_id, type_name):
        """Get the entity from `self.objects`, or create and register it"""
        if obj_id in self.objects:
            return self.objects[obj_id]
        obj = self._create(type_name)
        # obj_id must be set before the object is added to the Objects DOM,
        # since objects.add() indexes by obj_id
        obj.obj_id = obj_id
        self.objects.add([obj])
        return obj

    def _create(self, type_name):
        """Create via the factory, falling back to a proxy if not registered"""
        type_name = TypeName(type_name)
        entity = None
        if self.factory.get_type_info(type_name) is not None:
            entity = self.factory.create(type_name)
        if entity is None:
            entity = Proxy(type_name.category, type_name=type_name)
        return entity

    def _resolve_reference(self, json_ref):
        """
        Get the referenced entity from `self.objects`, or make a stub for it.

        A stub has the right type, id and name, and is in the same state as an
        entity fetched (but not yet synced) from a store: not new, not dirty,
        and marked as needing a sync.
        """
        obj_id = json_ref["_id"]
        if obj_id in self.objects:
            return self.objects[obj_id]

        stub = self._create(json_ref["_type_name"])
        stub.obj_id = obj_id
        name = stub.properties["name"]
        with Inhibitor(name.broadcaster), Unlocked(name):
            name.value = json_ref["name"]
        stub.reset_create()
        stub.reset_update()
        stub.mark_for_sync()
        self.objects.add([stub])
        return stub

    def _type_name(self, obj):
        """Get the registered type name string for an entity's class"""
        if isinstance(obj, Proxy) and obj.type_name is not None:
            return str(obj.type_name)
        return str(self.factory.resolve_inverse(obj.__class__))

    def deserialize(self, string):
        """
        Deserialize a JSON string produced by `serialize()` to entities.

        Args:
            string (str): A JSON array of entity dicts, each shaped as
                described in `deserialize_object`.

        Returns:
            list: The reconstructed entities, in order. They are also
                registered in `self.objects`, so a later reference to one by
                `obj_id` resolves to the same object.
        """
        json_data = json.loads(string)
        return [self.deserialize_object(item) for item in json_data]

    def deserialize_object(self, json_dict):
        """
        Deserialize a single entity dict to an RMTC entity.

        If an entity with the same `_id` is already in `self.objects` (a
        full entity, or a stub made for an earlier reference) it is filled in
        and returned, otherwise a new one is made via the factory and
        registered before any property is populated.

        Properties are assigned without broadcasting, and the entity ends
        with its create, update and sync flags all cleared - it reflects the
        store and has nothing to push. With no store attached, a push skips
        it rather than writing a duplicate.

        Args:
            json_dict (dict): A single entity's data, shaped as produced by
                `serialize_object`. Member object properties are nested
                dicts, deserialized recursively. Reference properties are
                `{"_id", "_type_name", "name"}` dicts; ones not yet in
                `self.objects` become stubs (see `_resolve_reference`). Only
                keys matching a property defined on the reconstructed class
                are consumed - unrecognised/custom properties are skipped.

        Returns:
            Object: The reconstructed entity.
        """

        obj = self._get_or_create(json_dict["_id"], json_dict["_type_name"])

        # use entity properties - custom props will be missed
        for prop in obj.properties.values():

            if prop.name not in json_dict:
                continue

            # the JSON value - a list if the property is an array
            values = json_dict[prop.name]

            # assign without marking the entity dirty or bumping updated_at
            with Inhibitor(prop.broadcaster), Unlocked(prop):
                if prop.is_array():
                    values = [self._from_json(prop, v) for v in values or []]
                    prop.value = [v for v in values if v is not None]
                else:
                    # values was serialized as a non-array
                    prop.value = self._from_json(prop, values)

        obj.reset_create()
        obj.reset_update()
        obj.reset_sync()
        return obj
