# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import datetime
import enum

import rmtc
from rmtc.system.objects import Object, Data, PropertyMessage, Immutable
from rmtc.system import Datetime, Version, Type, URI, TypeName, RMTCException
import datetime
import enum

from abstract_rmtc_test import AbstractRMTCTest


class BaseType:
    pass


class DerivedType(BaseType):
    pass


class MockEventObject(Object):

    def __init__(self):
        super(MockEventObject, self).__init__()
        self._updated = False
        self._accessed = False
        prop = self.add_property("number", int)
        prop.broadcaster.add(PropertyMessage.UPDATED, self.updated)
        prop.broadcaster.add(PropertyMessage.ACCESSED, self.accessed)

    def updated(self, prop):
        self._updated = True

    def accessed(self, prop):
        self._accessed = True


class MockObjectA(Object):

    def __init__(self):
        super(MockObjectA, self).__init__(name="Object A")
        self.add_property("b", Object)
        self.add_property("numbers", [int])


class MockEnum(enum.IntEnum):

    A = 0
    B = 1
    C = 2


class TestObjects(AbstractRMTCTest):
    """Test RMTC objects"""

    def test_object_notification(self):
        obj = MockEventObject()
        self.assertFalse(obj._accessed)
        obj.number #access number to trigger flag
        self.assertTrue(obj._accessed)
        self.assertFalse(obj._updated)
        obj.number = 10
        self.assertTrue(obj._updated)

    def test_array_notification(self):
        """Do all array mutation accessors broadcast UPDATED"""
        data = Data()
        prop = data.add_property("numbers", [int], [1, 2, 3])
        updates = []
        prop.broadcaster.add(PropertyMessage.UPDATED, updates.append)

        prop.append(4)
        self.assertEqual(len(updates), 1)
        prop[0] = 10
        self.assertEqual(len(updates), 2)
        prop.set(20, 1)
        self.assertEqual(len(updates), 3)
        prop.remove(20)
        self.assertEqual(len(updates), 4)
        self.assertEqual(data.numbers, [10, 3, 4])

    def test_object_adds(self):
        """Can we add numbers using the append helper"""
        obj_a = MockObjectA()
        test_list = [0, 1, 2, 3, 4]
        obj_a.add_numbers(test_list)
        self.assertEqual(test_list, obj_a.numbers)

    def test_property_add(self):
        data = Data()
        data.add_property("test_string", str, "test")
        data.add_property("test_int", int, 123)
        data.add_property("test_bool", bool, True)
        data.add_property("test_float", float, 123.123)
        data.add_property("test_uri", URI, URI("http://www.wetafx.co.nz"))
        data.add_property("test_datetime", Datetime, Datetime("2020-05-01T11:31:00"))
        data.add_property("test_version", Version, "1.2.3")
        data.add_property("test_type", Type, rmtc.system.URI)
        self.assertEqual(len(data.properties), 8)

    def test_propcopy(self):
        data = Data()

        # POD
        test_str = "test"
        test_int = 123
        test_bool = True
        test_float = 123.123
        data.add_property("test_string", str, test_str)
        data.add_property("test_int", int, test_int)
        data.add_property("test_bool", bool, test_bool)
        data.add_property("test_float", float, test_float)
        test_str = "not_test"
        test_int = 321
        test_bool = False
        test_float = 321.321
        self.assertEqual(data.test_string, "test")
        self.assertEqual(data.test_int, 123)
        self.assertEqual(data.test_bool, True)
        self.assertEqual(data.test_float, 123.123)

        # COMPLEX
        test_uri = URI("http://www.wetafx.co.nz")
        test_datetime = Datetime("2020-05-01T11:31:00")
        test_version = Version("1.2.3")
        test_type = rmtc.system.URI
        data.add_property("test_uri", URI, test_uri)
        data.add_property("test_datetime", Datetime, test_datetime)
        data.add_property("test_version", Version, test_version)
        data.add_property("test_type", Type, test_type)
        test_uri = URI("http://www.wetadigital.com")
        test_datetime = Datetime("2026-01-01T00:00:00")
        test_version = Version("3.2.1")
        test_type = rmtc.system.Version
        self.assertEqual(str(data.test_uri), "http://www.wetafx.co.nz")
        self.assertEqual(str(data.test_datetime), "2020-05-01T11:31:00")
        self.assertEqual(str(data.test_version), "1.2.3")
        self.assertEqual(data.test_type.type_class, rmtc.system.URI)

        # ARRAY
        test_array = [1, 2, 3]
        data.add_property("test_array", [int], test_array)
        test_array[0] = 3
        test_array[2] = 1
        self.assertEqual(data.test_array, [1, 2, 3])

    def test_duplicate(self):
        data = Data()
        test_uri = URI("http://www.wetafx.co.nz")
        test_datetime = Datetime("2020-05-01T11:31:00")
        test_version = Version("1.2.3")
        test_type = rmtc.system.URI
        data.add_property("test_uri", URI, test_uri)
        data.add_property("test_datetime", Datetime, test_datetime)
        data.add_property("test_version", Version, test_version)
        data.add_property("test_type", Type, test_type)
        duplicate = data.duplicate()
        self.assertEqual(str(duplicate.test_uri), "http://www.wetafx.co.nz")
        self.assertEqual(str(duplicate.test_datetime), "2020-05-01T11:31:00")
        self.assertEqual(str(duplicate.test_version), "1.2.3")
        self.assertEqual(duplicate.test_type.type_class, rmtc.system.URI)
        test_uri = URI("http://www.wetadigital.com")
        self.assertEqual(str(duplicate.test_uri), "http://www.wetafx.co.nz")

    def test_property_string_convert(self):
        data = Data()
        rmtc_sys = self.get_system()

        prop_string = data.add_property("test_string", str, "test")
        self.assertEqual(prop_string.value, "test")

        prop_string.value = 123
        self.assertEqual(prop_string.value, "123")

        prop_string.value = False
        self.assertEqual(prop_string.value, "False")

        prop_string.value = 123.4
        self.assertEqual(prop_string.value, "123.4")

        prop_string.value = URI("http://www.wetafx.co.nz")
        self.assertEqual(prop_string.value, "http://www.wetafx.co.nz")

        prop_string.value = Datetime("2020-05-01T11:31:00")
        self.assertEqual(prop_string.value, "2020-05-01T11:31:00")

        prop_string.value = Type(type_name=TypeName("rmtc_track.License.License-1.0.0"))
        self.assertEqual(prop_string.value, "rmtc_track.License.License-1.0.0")

    def test_property_uri_convert(self):
        data = Data()

        prop_uri = data.add_property("test_uri", URI, URI("http://www.wetafx.co.nz"))
        self.assertEqual(prop_uri.value, URI("http://www.wetafx.co.nz"))

        prop_uri.value = 123.4
        self.assertEqual(prop_uri.value, URI())

        prop_uri = data.add_property("test_uri", URI, URI("http://www.wetafx.co.nz"))
        self.assertEqual(prop_uri.value, URI("http://www.wetafx.co.nz"))

    def test_property_datetime_convert(self):
        data = Data()

        prop_datetime = data.add_property(
            "test_datetime", Datetime, Datetime("2020-05-01T11:31:00")
        )
        self.assertEqual(str(prop_datetime.value), "2020-05-01T11:31:00")

        now = datetime.datetime.now(datetime.timezone.utc)
        prop_datetime.value = now
        self.assertEqual(str(prop_datetime.value), now.isoformat())

        iso_datetime = datetime.datetime.fromisoformat("2020-05-01T11:31:00")
        prop_datetime.value = iso_datetime
        self.assertEqual(str(prop_datetime.value), "2020-05-01T11:31:00")

        iso_string = "2020-05-01T11:31:00"
        prop_datetime.value = iso_string
        self.assertEqual(str(prop_datetime.value), iso_string)

    def test_property_type_convert(self):
        data = Data()
        prop_type = data.add_property("test_type", Type, rmtc.system.URI)

        self.assertTrue(isinstance(prop_type.value, Type))
        obj = prop_type.value()
        self.assertTrue(isinstance(obj, rmtc.system.URI))

        prop_type.value = rmtc.system.URI
        obj = prop_type.value()
        self.assertTrue(isinstance(obj, rmtc.system.URI))

    def test_enum_property(self):
        data = Data()
        prop = data.add_property("test_type", MockEnum, MockEnum.A)
        self.assertEqual(prop.value, MockEnum.A)
        prop.value = MockEnum.B
        self.assertEqual(prop.value, MockEnum.B)
        prop.value = 2
        self.assertEqual(prop.value, MockEnum.C)
        self.assertEqual(prop.valid_values, [item.value for item in MockEnum])

    def test_derived_type_property(self):
        data = Data()
        prop_type = data.add_property(
            "test_type", Type, DerivedType, default=Type(type_class=BaseType)
        )
        self.assertEqual(prop_type.value.type_class, DerivedType)
        self.assertEqual(prop_type.default.type_class, BaseType)
        self.assertEqual(str(prop_type.value), "DerivedType")

    def test_property_type(self):
        data = Data()
        prop_type = data.add_property("type_test", Type)
        self.assertTrue("type_test" in data.properties.keys())
        data.type_test = "rmtc_ops.Asset.Image-1.0.0"
        self.assertEqual(data.type_test.__class__, Type)
        self.assertEqual(prop_type.value, data.type_test)
        self.assertEqual(data.type_test.type_name.module, "rmtc_ops")
        self.assertEqual(data.type_test.type_name.category, "Asset")
        self.assertEqual(data.type_test.type_name.name, "Image")
        self.assertEqual(str(data.type_test.type_name.version), "1.0.0")
        self.assertEqual(str(data.type_test.type_name), "rmtc_ops.Asset.Image-1.0.0")

    def test_property_dict(self):
        data = Data()
        data.add_property("dict_test", dict, {})
        data.dict_test["test1"] = 1
        data.dict_test["test2"] = "2"
        data.dict_test["test3"] = [1,2,3]
        self.assertEqual(len(data.dict_test.items()), 3)
        self.assertEqual(data.dict_test["test1"], 1)
        self.assertEqual(data.dict_test["test2"], "2")
        self.assertEqual(data.dict_test["test3"], [1,2,3])

    def test_immutablility(self):
        obj = Object()
        obj.add_property("test", int, 0)
        obj.set_immutable(True)
        failed = False
        try:
            obj.test = 1
        except RMTCException as e:
            failed = True
        self.assertTrue(failed)
        self.assertEqual(obj.test, 0)        
        obj.set_immutable(False)
        failed = False
        try:
            obj.test = 2
        except RMTCException as e:
            failed = True
        self.assertFalse(failed)        
        self.assertEqual(obj.test, 2)
        failed = False        
        with Immutable(obj):
            try:
                obj.test = 3
            except RMTCException as e:
                failed = True
        self.assertTrue(failed)
        self.assertEqual(obj.test, 2)

    def test_unnamed_object_gets_class_name(self):
        self.assertEqual(Object().name, "Object")
        self.assertEqual(MockEventObject().name, "MockEventObject")
        self.assertEqual(MockEventObject().name, "MockEventObject")

    def test_explicit_name_kept(self):
        self.assertEqual(Object(name="Named").name, "Named")
        self.assertEqual(MockObjectA().name, "Object A")

    def test_builtin_name_is_class_name(self):
        self.assertEqual(MockEventObject().builtin_name(), "MockEventObject")

    def test_default_name_without_namer(self):
        Object.set_namer(None)
        obj = MockEventObject()
        self.assertEqual(obj.default_name(), obj.builtin_name())

    def test_default_name_uses_installed_namer(self):
        self.addCleanup(Object.set_namer, None)
        seen = []

        def namer(obj):
            seen.append(obj)
            return f"custom_{obj.builtin_name()}"

        Object.set_namer(namer)
        obj = MockEventObject()
        self.assertEqual(obj.default_name(), "custom_MockEventObject")
        self.assertEqual(seen, [obj])

    def test_installed_namer_not_used_by_init(self):
        """__init__ runs before subclass links exist, so it never calls the namer"""
        self.addCleanup(Object.set_namer, None)
        Object.set_namer(lambda obj: "from_namer")
        self.assertEqual(MockEventObject().name, "MockEventObject")

    def test_set_namer_none_restores_builtin(self):
        Object.set_namer(lambda obj: "from_namer")
        Object.set_namer(None)
        self.assertEqual(MockEventObject().default_name(), "MockEventObject")