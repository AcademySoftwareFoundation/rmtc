# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.system.objects import Objects
from rmtc.system import RMTCException
from rmtc.track.store import Entity

from abstract_rmtc_test import AbstractRMTCTest


class MockDomObject(Entity):

    def __init__(self, name=None):
        super(MockDomObject, self).__init__(name=name)

    @classmethod
    def category(cls):
        return "MockDomObject"


class TestDomObjects(AbstractRMTCTest):
    """
    Objects is the local-process DOM used to cache and resolve entities by
    UUID. The REST serializer relies on `key in self.objects` to decide
    whether a referenced UUID has already been fetched, so __contains__
    must be correct and must terminate for keys that were never added.
    """

    def test_contains_is_false_for_unknown_key(self):
        objects = Objects()
        self.assertFalse("not-a-real-id" in objects)

    def test_contains_is_true_after_add(self):
        objects = Objects()
        obj = MockDomObject(name="A")
        objects.add([obj])
        self.assertTrue(obj.obj_id in objects)

    def test_contains_is_false_after_remove(self):
        objects = Objects()
        obj = MockDomObject(name="A")
        objects.add([obj])
        objects.remove([obj])
        self.assertFalse(obj.obj_id in objects)

    def test_getitem_resolves_added_object(self):
        objects = Objects()
        obj = MockDomObject(name="A")
        objects.add([obj])
        self.assertEqual(objects[obj.obj_id], obj)

    def test_getitem_returns_none_for_unknown_key(self):
        objects = Objects()
        self.assertIsNone(objects["not-a-real-id"])

    def test_add_raises_on_none_object(self):
        objects = Objects()
        with self.assertRaises(RMTCException):
            objects.add([None])

    def test_add_is_idempotent_for_same_id(self):
        objects = Objects()
        obj = MockDomObject(name="A")
        added_first = objects.add([obj])
        added_second = objects.add([obj])
        self.assertEqual(added_first, [obj])
        self.assertEqual(added_second, [])
        self.assertEqual(len(objects.get()), 1)
