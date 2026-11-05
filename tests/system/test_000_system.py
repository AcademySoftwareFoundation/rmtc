# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import pathlib

from abstract_rmtc_test import AbstractRMTCTest
from rmtc.system import Datetime, URI, TypeName, Version, Type, FileURI


class BaseType:
    pass


class DerivedType(BaseType):
    pass


class TestSystem(AbstractRMTCTest):
    """Test RMTC objects"""

    def test_type(self):
        type_instance = Type(type_class=DerivedType, base_class=BaseType)
        self.assertEqual(type_instance.type_class, DerivedType)
        self.assertEqual(type_instance.base_class, BaseType)
        self.assertEqual(str(type_instance), "DerivedType")

    def test_typename(self):
        type_name = TypeName(string="rmtc_track.License.License-1.0.0")
        self.assertEqual(str(type_name), "rmtc_track.License.License-1.0.0")
        self.assertEqual(type_name.module, "rmtc_track")
        self.assertEqual(type_name.category, "License")
        self.assertEqual(type_name.name, "License")
        self.assertEqual(str(type_name.version), "1.0.0")
        type_name = TypeName(string="rmtc_track.License.License")
        self.assertEqual(str(type_name), "rmtc_track.License.License")
        self.assertEqual(type_name.module, "rmtc_track")
        self.assertEqual(type_name.category, "License")
        self.assertEqual(type_name.name, "License")
        self.assertEqual(type_name.version, None)
        type_name = TypeName(
            module="rmtc_track", 
            category="License", 
            name="License", 
            version=Version("1.0.0")
        )
        self.assertEqual(str(type_name), "rmtc_track.License.License-1.0.0")
        self.assertEqual(type_name.module, "rmtc_track")
        self.assertEqual(type_name.category, "License")
        self.assertEqual(type_name.name, "License")
        self.assertEqual(str(type_name.version), "1.0.0")

    def test_uri(self):
        uri = URI(scheme="file", host="localhost")
        self.assertTrue(isinstance(uri.path, pathlib.Path))
        uri.path /= "test.exr"
        self.assertEqual(str(uri), "file://localhost/test.exr")
        uri = URI()
        uri.scheme = "file"
        uri.host = "localhost"
        self.assertTrue(isinstance(uri.path, pathlib.Path))
        uri.path /= "test.exr"
        self.assertEqual(str(uri), "file://localhost/test.exr")
        file_uri = FileURI(path=uri.path)
        self.assertEqual(uri, file_uri)

    def test_timestamp(self):
        iso_string = "2026-01-15T00:21:30.213805+00:00"  # UTC ISO time
        time_a = Datetime(string=iso_string)
        self.assertEqual(iso_string, str(time_a))

    def test_version(self):
        version_0 = Version()
        self.assertEqual("0.0.0", str(version_0))        
        version_1 = Version("1.0.0")
        self.assertEqual("1.0.0", str(version_1))
        version_2 = version_1.bump_major()
        self.assertEqual("2.0.0", str(version_2))    
        version_2_1 = version_2.bump_minor()
        self.assertEqual("2.1.0", str(version_2_1))    
        version_2_1_1 = version_2_1.bump_patch()
        self.assertEqual("2.1.1", str(version_2_1_1))  
        self.assertEqual(version_2_1_1.major, 2)
        self.assertEqual(version_2_1_1.minor, 1)
        self.assertEqual(version_2_1_1.patch, 1)                
        self.assertEqual(Version("2.1.1"), version_2_1_1)          
        self.assertTrue(version_2_1.compatible(version_2))
        self.assertFalse(version_2_1.compatible(version_1))
