# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Objects, data & property system
"""

import enum
import datetime
import uuid
import copy

from abc import ABC

from rmtc.system import RMTCException, IIDGenerator, Broadcaster
from rmtc.system import Datetime, URI, Type, Version, Package, TypeName


class PropertyDirection(enum.IntEnum):

    INVALID = 0
    IN = 1
    OUT = 2
    INOUT = 3

    def __str__(self):
        return self.name.upper()


class PropertyMessage(enum.IntEnum):

    INVALID = 0
    UPDATED = 1
    ACCESSED = 2
    APPENDED = 3
    REMOVED = 5

    def __str__(self):
        return self.name.upper()


class ObjectMessage(enum.IntEnum):

    INVALID = 0
    PROPERTY_ADDED = 1
    PROPERTY_UPDATED = 2
    PROPERTY_ACCESSED = 3
    APPENDED = 5
    REMOVED = 6

    def __str__(self):
        return self.name.upper()


class PropertyContainer(enum.IntEnum):
    """
    Enumeration for property container types.

    Defines how properties store their values, either as single values
    or as arrays/lists of values. This determines the storage structure
    and access patterns for property data.
    """

    INVALID = 0
    VALUE = 1  # Property holds a single value
    ARRAY = 2  # Property holds a HOMOGENOUS list

    def __str__(self):
        return self.name.upper()


# Convienience alias
IN = PropertyDirection.IN
OUT = PropertyDirection.OUT
INOUT = PropertyDirection.INOUT


class PropertyType(enum.IntEnum):
    """
    Enumeration for property data types.

    Defines the supported data types for object properties in the RMTC system.
    Each type corresponds to specific Python types and JSON formats,
    enabling type-safe property management and validation.
    """

    INVALID = 0
    BOOLEAN = 1
    INTEGER = 2
    NUMBER = 3
    STRING = 4
    DATETIME = 5  # ISO UTC timestamp
    OBJECT = 6  # object reference
    URI = 7  # file path or resource
    VERSION = 8  # version
    TYPE = 9  # class type - used for signatures
    PACKAGE = 10  # versioned package name
    ENUM = 11

    def __str__(self):
        return self.name.upper()


class Property:
    """
    Object property with type safety and ownership semantics.

    The Property class represents a typed property of an RMTC object with
    support for single values or arrays & ownership relationships.
    It provides type validation, serialization
    hints, and lifecycle management for object properties.

    Properties can hold primitive types (strings, numbers, booleans) or
    object references with configurable ownership semantics. Array properties
    can contain multiple values of the same type.

    Note on mutablility:
    * POD Property values are immutable
    * Object propertes return back a mutable reference
    * Array accessors will return an unmanaged mutable list
    * Array elements are mutable & unmanaged

    Changing mutable properties are not managed or tracked by RMTC
    If you alter a mutable property value (e.g. appending to a list) then
    you need to mark the entity to update in the db

    TODO: make getting array values return a tuple to prevent unmanaged append/remove
    """

    def __init__(
        self,
        name,
        prop_type,
        obj,
        type_class=None,
        required=False,
        container=PropertyContainer.VALUE,
        member=True,
        valid_values=None,
        value=None,
        hidden=False,
        default=None,
        direction=PropertyDirection.INOUT,
    ):
        """Initialize Property with type and ownership configuration."""
        self._name = name
        self._type = prop_type
        self._type_class = type_class
        self._obj = obj
        self._value = None
        self._array = None
        self._required = required
        self._container = container
        self._member = member
        self._valid_values = valid_values
        self._hidden = hidden
        self._default = default
        self._direction = direction
        self._broadcaster = Broadcaster()

        self.value = value

    def __repr__(self):
        """Return string representation showing value or object references."""
        if self._container == PropertyContainer.VALUE:
            if self._type == PropertyType.OBJECT:
                return f"Obj:{id(self._value)}"
            return f"{self._value}"
        if self._type == PropertyType.OBJECT:
            return f"Objs:{[id(x.value) for x in self._array]}"
        return f"{self._array}"

    @property
    def direction(self):
        return self._direction

    @property
    def broadcaster(self):
        return self._broadcaster

    @property
    def valid_values(self):
        return self._valid_values

    @property
    def required(self):
        """Get required flag."""
        return self._required

    @property
    def hidden(self):
        """Get required flag."""
        return self._hidden

    @property
    def member(self):
        """Get ownership semantics."""
        return self._member

    @property
    def name(self):
        """Get property name."""
        return self._name

    @property
    def prop_type(self):
        """Get property data type."""
        return self._type

    @property
    def default(self):
        return self._default

    @property
    def type_class(self):
        """Get property obj type."""
        return self._type_class

    @property
    def container_type(self):
        """Get container type (VALUE or ARRAY)."""
        return self._container

    @property
    def obj(self):
        """Get owner object reference."""
        return self._obj

    def is_input(self):
        return self._direction in [PropertyDirection.IN, PropertyDirection.INOUT]

    def is_output(self):
        return self._direction in [PropertyDirection.OUT, PropertyDirection.INOUT]

    def is_inputoutput(self):
        return self._direction == PropertyDirection.INOUT

    def is_value(self):
        """Check if property is a value."""
        return self._container == PropertyContainer.VALUE

    def is_array(self):
        """Check if property holds an array of values."""
        return self._container == PropertyContainer.ARRAY

    def is_member(self):
        return self.member

    def is_reference(self):
        return not self.member

    def is_hidden(self):
        return self.hidden

    def is_required(self):
        return self.required

    def is_object(self):
        return self._type == PropertyType.OBJECT

    def is_referenced_object(self):
        """Check if property references an object it doesn't own."""
        return self._type == PropertyType.OBJECT and self.is_reference()

    def is_member_object(self):
        """Check if this is an owned child object property."""
        return self._type == PropertyType.OBJECT and self.is_member()

    def duplicate(self):
        """
        Create a copy of this property.

        This is 'near-deep' copy of RMTC objects as we duplicate all the
        persistent property information only - anything that is not an exposed
        property is ignored, this allows objects to hold large volatile data
        such as torch models or datasets which are discarded on duplicate
        """
        new_prop = Property(
            name=self.name,
            prop_type=self.prop_type,
            obj=self.obj,
            type_class=self.type_class,
            container=self.container_type,
            required=self.required,
            member=self.member,
            valid_values=self.valid_values,
            hidden=self.hidden,
            default=self.default,
            direction=self.direction,
        )

        # deep copy member data over
        if self.is_member():
            if self.is_object():
                new_value = None
                if self.is_array():
                    new_value = [item.duplicate() for item in self.array_value]
                elif self.value is not None:
                    new_value = self.value.duplicate()
                new_prop.value = new_value
            else:
                new_prop.value = copy.deepcopy(self.value)
        else:
            new_prop.value = self.value

        return new_prop

    def _convert(self, value, prop_type=None):
        """
        Convert input value to the property's data type.

        Performs type-safe conversion of input values to match the property's
        declared data type, preventing type drift through assignment errors.
        Handles None values with appropriate defaults for each type.
        """
        if prop_type is None:
            prop_type = self.prop_type

        # immutable types

        if prop_type == PropertyType.BOOLEAN:
            if value is not None:
                return bool(value)
            if self.default is not None:
                return self.default
            return bool()

        if prop_type == PropertyType.INTEGER:
            if value is not None:
                return int(value)
            if self.default is not None:
                return self.default
            return int()

        if prop_type == PropertyType.NUMBER:
            if value is not None:
                return float(value)
            if self.default is not None:
                return self.default
            return float()

        if prop_type == PropertyType.STRING:
            if isinstance(value, datetime.datetime):
                return value.isoformat()
            if value is not None:
                return str(value)
            if self.default is not None:
                return str(self.default)
            return str()

        if prop_type == PropertyType.ENUM:
            if isinstance(value, enum.IntEnum):
                return value
            if isinstance(value, int):
                return self._type_class(value)
            if isinstance(value, str):
                index = list(self._type_class).index(self._type_class[value])
                value = index
            if self.default is not None:
                return self.default
            if value is None:
                value = self._type_class(0)
            return self._type_class(int(value))

        if prop_type == PropertyType.DATETIME:
            if isinstance(value, Datetime):
                return value
            if isinstance(value, datetime.datetime):
                # HACK : upcast via the ISO string
                return Datetime(value.isoformat())
            if isinstance(value, str):
                return Datetime(value)
            if self.default is not None:
                return self.default
            return Datetime()

        # mutable types - copy required

        if prop_type == PropertyType.VERSION:
            if isinstance(value, Version):
                return value
            if isinstance(value, str):
                return Version(value)
            if self.default is not None:
                return copy.copy(self.default)
            return Version("0.0.0")

        if prop_type == PropertyType.URI:
            if isinstance(value, URI):
                return value
            if isinstance(value, str):
                return URI(value)
            if self.default is not None:
                return self.default
            return URI()

        if prop_type == PropertyType.PACKAGE:
            if isinstance(value, Package):
                return value
            if isinstance(value, str):
                return Package(value)
            if self.default is not None:
                return copy.copy(self.default)
            return Package()

        if prop_type == PropertyType.TYPE:
            if isinstance(value, Type):
                return value
            if isinstance(value, TypeName):
                return Type(type_name=value)
            if isinstance(value, str):
                type_name = TypeName(string=value)
                return Type(type_name=type_name)
            if isinstance(value, type):
                return Type(type_class=value)
            if self.default is not None:
                return copy.copy(self.default)
            return Type()

        if prop_type == PropertyType.OBJECT:
            if value is not None and not isinstance(value, Object):
                raise RMTCException(
                    cause=f"Reference must be assigned Object, got: {value.__class__.__name__}"
                )
            return value

        raise RMTCException(cause="Invalid conversion")

    def set_to_default(self):
        if self.default is not None:
            self.value = self.default

    def append(self, value):
        """Add a value to array property and notify listeners."""
        self._broadcaster(PropertyMessage.ACCESSED, self)

        if self._container == PropertyContainer.ARRAY:
            self._array.append(self._convert(value))
            self._broadcaster(PropertyMessage.APPENDED, value)
            self._broadcaster(PropertyMessage.UPDATED, self)

    def remove(self, value):
        """Remove a value from array property and notify listeners."""
        self._broadcaster(PropertyMessage.ACCESSED, self)

        if self._container == PropertyContainer.ARRAY:
            if value in self._array:
                self._array.remove(value)
            self._broadcaster(PropertyMessage.REMOVED, value)
            self._broadcaster(PropertyMessage.UPDATED, self)

    def __len__(self):
        """Return length of property values."""
        self._broadcaster(PropertyMessage.ACCESSED, self)

        if self._container == PropertyContainer.ARRAY:
            return len(self._array)
        return 1

    def __setitem__(self, index, value):
        """Set array item at index and notify listeners if changed."""
        self._broadcaster(PropertyMessage.ACCESSED, self)

        if self._container == PropertyContainer.ARRAY:
            if self._array[index] != value:
                self._array[index] = value
                self._broadcaster(PropertyMessage.UPDATED, self)
        else:
            if self._value != value:
                self._value = value
                self._broadcaster(PropertyMessage.UPDATED, self)

    def __getitem__(self, index):
        """Get array item at index."""
        self._broadcaster(PropertyMessage.ACCESSED, self)

        if self._container == PropertyContainer.ARRAY:
            return self._array[index]
        return self._value

    @property
    def value(self):
        """Get the property value based on container type."""
        self._broadcaster(PropertyMessage.ACCESSED, self)

        result = None
        if self._container == PropertyContainer.ARRAY:
            result = self._array
        if self._container == PropertyContainer.VALUE:
            result = self._value
        return result

    @property
    def array_value(self):
        """Get the property value always as an array"""
        self._broadcaster(PropertyMessage.ACCESSED, self)

        if self._container == PropertyContainer.ARRAY:
            return self._array
        if self._value is not None:
            return [self._value]
        return []

    @array_value.setter
    def array_value(self, value):
        """Set the property value always as an array"""
        if self._container == PropertyContainer.ARRAY:
            self.value = value
        else:
            if len(value) > 0:
                self.value = value[0]
            else:
                self.value = None

    @value.setter
    def value(self, value):
        """
        Set property value with type conversion and change notification.

        Converts the input value to the property's data type and notifies
        the owner object of the change. For array properties, replaces
        the entire array with converted values.
        """
        # TODO: check this equality actually works as expected
        if self._container == PropertyContainer.ARRAY:
            if self._array == value:
                return
            self._array = []
            if value is not None:
                for v in value:
                    v = self._convert(v)
                    if v is not None and not issubclass(v.__class__, self.type_class):
                        raise RMTCException(
                            f"Mismatched type: {v} not a subclass of {self.type_class}"
                        )
                    self._array.append(self._convert(v))
        elif self._container == PropertyContainer.VALUE:
            if self._value == value:
                return
            v = self._convert(value)
            if v is not None and not issubclass(v.__class__, self.type_class):
                raise RMTCException(
                    f"Mismatched type: {v} not a subclass of {self.type_class}"
                )
            self._value = v

        # notify
        self._broadcaster(PropertyMessage.UPDATED, self)

    def set(self, value, idx=0):
        """Lambda acceptable assignment method"""
        if self.is_array():
            self.value[idx] = value
        else:
            self.value = value

    def get(self, idx=0):
        """Symmetry to set"""
        if self.is_array():
            return self.value[idx]
        return self.value


class Appender:
    """
    Helper class for synthetic add_xxxx() methods with change notification.

    The Appender class provides a callable interface that mimics
    synthetic add methods for array properties. When called, it appends
    items to the specified property and triggers change notifications
    to maintain object consistency and observer patterns.

    This class enables dynamic method generation for property manipulation
    while ensuring proper change tracking and notification propagation.
    """

    def __init__(self, data, prop_name):
        """Initialize the Appender with owner object and property name."""
        self._data = data
        self._prop_name = prop_name

    def __call__(self, *args, **kwargs):
        """
        Append items to the property and notify listeners."""
        prop = self._data[self._prop_name]
        if not isinstance(args[0], list):
            raise RMTCException(
                f"None list value {args[0]} being added to list property {self._prop_name}"
            )
        for item in args[0]:
            prop.append(item)


class Remover:
    """
    Helper class for synthetic remove_xxxx() methods with change notification.

    The Remover class provides a callable interface that mimics
    synthetic remove methods for array properties. When called, it removes
    items from the specified property and triggers change notifications
    to maintain object consistency and observer patterns.

    This class enables dynamic method generation for property manipulation
    while ensuring proper change tracking and notification propagation.
    """

    def __init__(self, data, prop_name):
        """Initialize the Remover with owner object and property name."""
        self._data = data
        self._prop_name = prop_name

    def __call__(self, *args, **kwargs):
        """Remove items from the property and notify listeners."""
        prop = self._data[self._prop_name]
        for item in args[0]:
            prop.remove(item)


class Data:
    """
    Abstract base class for property-based data containers with change notification.

    The Data class provides a foundation for objects that manage typed properties
    with automatic change notification, parent-child relationships, and dynamic
    method generation. It supports both primitive and object properties with
    configurable ownership semantics.

    Data and Object form the member variables and method functions respectively.
    They are distinct to allow for dependency injection like approaches.

    Properties can be accessed using Pythonic syntax (obj.property_name) and
    support automatic generation of add_xxx() and remove_xxx() methods for
    array properties. The class maintains listener patterns for property
    change notifications and enforces type safety through property conversion.
    """

    def __init__(self):
        """Initialize Data container with optional property initialization."""
        self._properties = {}

    def __repr__(self):
        """Return string representation showing object ID and properties."""
        return f"{id(self)}: {str(self._properties)}"

    def __setattr__(self, name, value):
        """
        Set property value using Pythonic syntax with type conversion.

        Intercepts attribute assignment for non-internal properties and
        delegates to the property's type-safe value setter.
        """
        if not name.startswith("_"):  # ignore internals
            if (
                name in self._properties.keys()
            ):  # pylint: disable=consider-iterating-dictionary
                prop = self._properties[name]
                prop.value = value
                return
        super(Data, self).__setattr__(name, value)

    def __getattr__(self, name):
        """
        Get property value or create dynamic methods using Pythonic syntax.

        Provides access to property values and generates synthetic add_xxx()
        and remove_xxx() methods for array properties. Returns None for
        non-existent properties.
        """
        if not name.startswith("_"):  # ignore internals
            if name.startswith("add_"):
                return Appender(data=self, prop_name=name.removeprefix("add_"))
            if name.startswith("remove_"):
                return Remover(data=self, prop_name=name.removeprefix("remove_"))
            if (
                name in self._properties.keys()
            ):  # pylint: disable=consider-iterating-dictionary
                return self._properties[name].value
        return None

    @property
    def properties(self):
        """Get the internal property mapping dictionary."""
        return self._properties

    def merge(self, other):
        """Add all the properties of the other data structure."""
        self._properties |= other.properties

    def clear(self):
        """Clear all properties and reset internal caches."""
        self._properties = {}

    def add_property(
        self,
        name,
        type_class,
        value=None,
        member=True,
        direction=PropertyDirection.INOUT,
        required=False,
        valid_values=None,
        hidden=False,
        default=None,
    ):
        """
        Add a typed property to the object with automatic type introspection.

        Creates a new property with type safety, change notification, and
        relationship management. Supports both primitive types and object
        references with configurable ownership semantics.

        The method introspects class types to determine the appropriate
        PropertyType and container type. List types create array properties,
        while single types create value properties.
        """
        container = PropertyContainer.VALUE
        prop_type = None

        # check default
        if default is not None and not issubclass(default.__class__, type_class):
            raise RMTCException(
                f"Default for property {name} is not a derived class of it's type"
            )

        # check for lists
        if isinstance(type_class, list):
            container = PropertyContainer.ARRAY
            type_class = type_class[0]
        else:
            container = PropertyContainer.VALUE

        # is POD or an object
        if type_class is str:
            prop_type = PropertyType.STRING
        elif type_class is int:
            prop_type = PropertyType.INTEGER
        elif type_class is bool:
            prop_type = PropertyType.BOOLEAN
        elif type_class is float:
            prop_type = PropertyType.NUMBER
        elif type_class is Datetime:
            prop_type = PropertyType.DATETIME
        elif type_class is URI:
            prop_type = PropertyType.URI
        elif type_class is Type:
            prop_type = PropertyType.TYPE
        elif type_class is Package:
            prop_type = PropertyType.PACKAGE
        elif type_class is Version:
            prop_type = PropertyType.VERSION
        elif issubclass(type_class, enum.IntEnum):
            prop_type = PropertyType.ENUM
            valid_values = [item.value for item in type_class]
        else:
            prop_type = PropertyType.OBJECT

        # required properties can't be objects
        # this may cause an issue on store create
        if required and prop_type == PropertyType.OBJECT:
            raise RMTCException(
                f"Can't create a required object property {self.name}.{name}"
            )

        # create value
        if value is None:
            if container == PropertyContainer.ARRAY:
                value = []
            else:
                if prop_type == PropertyType.OBJECT:
                    value = None
                elif prop_type == PropertyType.DATETIME:
                    value = Datetime()
                elif prop_type == PropertyType.VERSION:
                    value = Version("1.0.0")
                elif prop_type == PropertyType.ENUM:
                    value = 0
                else:
                    value = type_class()

        # create and add
        prop = Property(
            name=name,
            prop_type=prop_type,
            type_class=type_class,
            obj=self,
            container=container,
            required=required,
            member=member,
            valid_values=valid_values,
            hidden=hidden,
            default=default,
            direction=direction,
        )
        self._properties[name] = prop  # overrides

        # HACK : set value at last minute - after property is created, fixes notification issues
        prop.value = value
        return prop

    def duplicate(self):
        """Create a duplicate with copied properties but no state information."""
        data = Data()
        for key, value in self._properties.items():
            data.properties[key] = value.duplicate()
        return data

    def __getitem__(self, key):
        """Get property by name using dictionary syntax."""
        if key not in self._properties:
            raise RMTCException(
                f"Bad key '{key}' not found in: {self._properties.keys()}"
            )
        return self._properties[key]

    def __setitem__(self, key, value):
        """Set property by name using dictionary syntax."""
        if key not in self._properties:
            raise RMTCException(
                f"Bad key '{key}' not found in: {self._properties.keys()}"
            )
        self._properties[key] = value


class UUID4(IIDGenerator):
    def generate(self):
        return str(uuid.uuid4())


class Object(ABC):

    _id_generator = UUID4()
    _counter = {}

    """
    Abstract base class for property-based objects with dynamic composition.

    Objects defer attributes to their Data instance - allowing for python like
    syntax to access serialisable properties.

    The Object class serves as a proxy that defers property operations to a
    dynamically composed Data object while preserving the derived type identity.
    It provides a unified interface for typed properties, change notification,
    parent-child relationships, and object lifecycle management.

    Objects automatically generate unique IDs, support execution context
    management, and provide introspection capabilities for serialization
    and factory instantiation. The class maintains bidirectional parent-child
    relationships and supports both deep and shallow copying semantics.
    """

    def __init__(self, name=None, obj_id=None, data=None):
        """Initialize Object with name, data container, and properties."""

        # create data
        if data is None:
            data = Data()
        self._data = data
        self._broadcaster = Broadcaster()

        # count instances for name
        counter = 1
        if self.__class__ in Object._counter:
            counter = Object._counter[self.__class__]
        Object._counter[self.__class__] = counter + 1
        if name is None:
            name = f"{self.__class__.__name__}-{counter}"
        self.add_property("name", str, name, required=True)

        # ID
        if obj_id is None:
            if Object._id_generator is None:
                raise RMTCException("ID generator is None - internal error")
            obj_id = Object._id_generator.generate()
        self._obj_id = obj_id

    @classmethod
    def set_id_generator(cls, id_generator):
        if id_generator is None or not issubclass(id_generator.__class__, IIDGenerator):
            raise RMTCException("ID generator is invalid - internal error")
        cls._id_generator = id_generator

    @property
    def type_class(self):
        return self.__class__

    @property
    def obj_id(self):
        """Get the unique object identifier."""
        return self._obj_id

    @obj_id.setter
    def obj_id(self, value):
        """Override the ID."""
        self._obj_id = value

    def __repr__(self):
        """Return string representation using object name."""
        return f"{self.name}"

    def merge_properties(self, other):
        """
        Merge in the object data contents
        This enables sophisticated object construction
        you can make a composite class that uses a same singular data property store.

        TorchModel(track.Model):
            def __init__():
                trainable = TorchTrainable()
                inferrable = TorchInferrable()
                super().__init__()
                self.merge(trainable)
                self.merge(inferrable)

        Post init, TorchModel instance now uses a single data structure made up of all the elements
        of the trainable and inferrable.

        Maybe useful - seemed cool at the time
        """
        self._data.merge(other.data)

    @property
    def data(self):
        """Get the internal data container."""
        return self._data

    @data.setter
    def data(self, value):
        """Get the internal data container."""
        self._data = value

    @property
    def properties(self):
        """Get the properties dictionary from data container."""
        return self._data.properties

    def clear_properties(self):
        """Clear all properties from the data container."""
        self._data.clear()

    def get_property(self, name):
        """Get property by name."""
        if name in self._data.properties:
            return self._data[name]
        return None

    def get_objects(self):
        return self.get_referenced_objects() + self.get_member_objects()

    def get_referenced_objects(self):
        objs = []
        for prop in self.properties.values():
            if prop.is_referenced_object():
                for obj in prop.array_value:
                    if obj is not None:
                        objs.append(obj)
        return objs

    def get_member_objects(self):
        objs = []
        for prop in self.properties.values():
            if prop.is_member_object():
                for obj in prop.array_value:
                    if obj is not None:
                        objs.append(obj)
        return objs

    def add_property(
        self,
        name,
        type_class,
        value=None,
        member=True,
        direction=PropertyDirection.INOUT,
        required=False,
        valid_values=None,
        hidden=False,
        default=None,
    ):
        """
        Add a typed property to the object.

        Delegates to the internal data container for property creation
        with type introspection and relationship management.
        """
        prop = self._data.add_property(
            name=name,
            type_class=type_class,
            required=required,
            member=member,
            direction=direction,
            valid_values=valid_values,
            hidden=hidden,
            default=default,
        )
        prop.broadcaster.add(
            PropertyMessage.ACCESSED, lambda prop: self.property_accessed(prop)
        )
        prop.broadcaster.add(
            PropertyMessage.UPDATED, lambda prop: self.property_updated(prop)
        )
        prop.value = value
        self._broadcaster(ObjectMessage.PROPERTY_ADDED, prop)
        return prop

    def __setattr__(self, name, value):
        """Set attribute with property delegation for non-internal names."""
        if not name.startswith("_"):
            if name in self._data.properties:
                self._data.__setattr__(name, value)
                return
        super(Object, self).__setattr__(name, value)
        return

    def __getattr__(self, name):
        """Get attribute with property delegation for non-internal names."""
        if not name.startswith("_"):
            return self._data.__getattr__(name)
        return None

    def __getitem__(self, key):
        """Get property by key using dictionary syntax."""
        return self._data[key]

    def __setitem__(self, key, value):
        """Set property by key using dictionary syntax."""
        self._data[key] = value

    def property_accessed(self, prop):  # pylint: disable=unused-argument

        # broadcast
        self._broadcaster(ObjectMessage.PROPERTY_ACCESSED, self)

    def property_updated(self, prop):  # pylint: disable=unused-argument

        # broadcast
        self._broadcaster(ObjectMessage.PROPERTY_UPDATED, self)

    @property
    def broadcaster(self):
        return self._broadcaster

    def duplicate(self):
        """
        Create a duplicate object with appropriate copying semantics.

        Performs duplication based on property types: objects are deep
        copied while references are shallow copied. Creates a new instance
        of the same class with duplicated data container.
        """
        # this performs an appropriate duplication depending on the property
        # objects are deep copied, refs are shallow copied
        new_obj = self.__class__()
        new_data = self.data.duplicate()
        new_obj.data = new_data
        return new_obj


class Objects:
    """
    This objects manager is the DOM for the local process and stores
    cached versions of the root items in RMTC.

    This is currently a naive implemenetation with performance issues.
    """

    def __init__(self):
        """Initialize the DOM manager with empty collections."""
        self._id_map = {}
        self._objects = set()

    def __repr__(self):
        name = f"{self.__class__.__module__}.{self.__class__.__name__}"
        return f"{name} - ({len.self._objects})"

    def clear(self):
        """Clear all stored objects from all collections."""
        self._id_map = {}
        self._objects = set()

    def __getitem__(self, key):
        if key in self._id_map:
            return self._id_map[key]
        return None

    def add(self, objects, add_refs=True):
        """Add objects to appropriate collections based on their entity type."""

        added = []

        for obj in objects:

            # quick checks
            if obj is None:
                raise RMTCException("Invalid object being added to DOM")
            if obj.obj_id is None:
                raise RMTCException(f"Invalid id on {obj}")
            if obj.obj_id in self._id_map:
                continue

            # add to return list
            added.append(obj)

            # update maps - this ends up storing every entity
            self._id_map[obj.obj_id] = obj

            # recurse to the references
            if add_refs:
                if not obj.requires_sync():
                    self.add(obj.get_referenced_objects())

        # update list cache
        self._objects = set(self._id_map.values())

        return added

    def remove(self, objects, remove_refs=False):
        """Remove objects to appropriate collections based on their entity type."""
        # TODO: replace with type enum
        removed = []
        for obj in objects:

            # quick checks
            if obj is None:
                raise RMTCException("Invalid object being added")
            if obj.obj_id is None:
                raise RMTCException(f"Invalid id on {obj}")
            if obj.obj_id not in self._id_map:
                continue

            # add to return list
            removed.append(obj)

            # update internal storage
            del self._id_map[obj.obj_id]
            self._objects = list(self._id_map.values())

            # recurse to the references
            if remove_refs:
                if not obj.requires_sync():
                    self.remove(obj.get_referenced_objects())

        return removed

    def get(self):
        return tuple(self._objects)

    def is_empty(self):
        return len(self._list) == 0
