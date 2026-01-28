# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import pathlib

from .abstract_rmtc_unit_test import AbstractRMTCUnitTest
from rmtc.system import Datetime, URI, TypeName, Version, Type


class BaseType:
    pass


class DerivedType(BaseType):
    pass


class TestSystem(AbstractRMTCUnitTest):
    """Test RMTC objects"""

    def test_type(self):
        type_instance = Type(type_class=DerivedType, base_class=BaseType)
        self.assertEqual(type_instance.type_class, DerivedType)
        self.assertEqual(type_instance.base_class, BaseType)
        self.assertEqual(str(type_instance), "DerivedType")

    def test_typename(self):
        type_name = TypeName(string="rmtc.License.License-1.0.0")
        self.assertEqual(str(type_name), "rmtc.License.License-1.0.0")
        self.assertEqual(type_name.module, "rmtc")
        self.assertEqual(type_name.category, "License")
        self.assertEqual(type_name.name, "License")
        self.assertEqual(str(type_name.ver), "1.0.0")
        type_name = TypeName(string="rmtc.License.License")
        self.assertEqual(str(type_name), "rmtc.License.License")
        self.assertEqual(type_name.module, "rmtc")
        self.assertEqual(type_name.category, "License")
        self.assertEqual(type_name.name, "License")
        self.assertEqual(type_name.ver, None)
        type_name = TypeName(
            module="rmtc", category="License", name="License", ver=Version("1.0.0")
        )
        self.assertEqual(str(type_name), "rmtc.License.License-1.0.0")
        self.assertEqual(type_name.module, "rmtc")
        self.assertEqual(type_name.category, "License")
        self.assertEqual(type_name.name, "License")
        self.assertEqual(str(type_name.ver), "1.0.0")

    def test_uri(self):
        uri = URI(scheme="file", host="localhost")
        self.assertTrue(isinstance(uri.path, pathlib.Path))
        uri.path /= "test.exr"
        self.assertEqual(str(uri), "file://localhost/test.exr")
        uri = URI()
        self.assertTrue(isinstance(uri.path, str))
        uri.scheme = "file"
        self.assertTrue(isinstance(uri.path, pathlib.Path))
        uri.host = "localhost"
        uri.path /= "test"
        uri.path = uri.path.with_suffix(".exr")
        self.assertEqual(str(uri), "file://localhost/test.exr")

    def test_timestamp(self):
        iso_string = "2026-01-15T00:21:30.213805+00:00"  # UTC ISO time
        time_a = Datetime(string=iso_string)
        self.assertEqual(iso_string, str(time_a))

