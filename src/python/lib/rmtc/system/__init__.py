# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Essential basic system classes
"""

import re
import os
import enum
import datetime
import logging
import importlib
import copy

from contextlib import contextmanager
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from pathlib import Path
from abc import ABC, abstractmethod
from packaging import version as ver
from packaging.version import parse as ver_parse

import yaml


class Version(ver.Version):
    """
    Version identifier with bump_major/minor/patch and comparison operators.
    """

    def __init__(
        self,
        string=None,
        major=0,
        minor=0,
        patch=0,
    ):
        if string is None:
            string = f"{major}.{minor}.{patch}"
        super(Version, self).__init__(string)
        self._parts = ver_parse(string)
        self._valid = False
        if self.major != 0:
            self._valid = True

    def is_valid(self):
        return self._valid

    def bump_major(self):
        return Version(f"{self.major+1}.0.0")

    def bump_minor(self):
        return Version(f"{self.major}.{self.minor+1}.0")

    def bump_patch(self):
        return Version(f"{self.major}.{self.minor}.{self.patch+1}")

    def compatible(self, other):
        # is this version compatible with the other version
        if other.major != self.major:
            return False
        if other.minor > self.minor:
            return False
        return True

    @property
    def major(self):
        return self._parts.major

    @property
    def minor(self):
        return self._parts.minor

    @property
    def patch(self):
        return self._parts.micro


# Basic logic operators
class Operator(enum.IntEnum):

    INVALID = 0
    AND = 1  # Everything true
    NAND = 2  # Everything false
    OR = 3  # At least 1 thing true
    NOR = 4  # At least 1 thing false
    XOR = 5  # Only 1 thing true
    XNOR = 6  # All true or all false

    def __repr__(self):
        return self.name.upper()


class Location:
    """Formal location representation using ISO 3166"""

    pass


# Basic datatypes
class DataType(enum.IntEnum):

    INVALID = 0
    FLOAT16 = 1
    FLOAT32 = 2
    FLOAT64 = 3
    INT8 = 4
    INT16 = 5
    INT32 = 6
    INT64 = 7
    UINT8 = 8
    UINT16 = 9
    UINT32 = 10
    UINT64 = 11
    BOOL = 12
    LABEL = 13

    def __str__(self):
        return self.name.upper()


class Datetime(datetime.datetime):
    """Create datetime wrapper that enforces ISO UTC format"""

    def __new__(cls, *args, **kwargs):
        """Hijack the constructor so that we always construct from a string"""
        dt = None
        if len(args) == 1 and isinstance(args[0], str):
            string = args[0]
            if "T" not in string:
                raise RMTCException(f"Malformed iso datetime {string}")
            dt = datetime.datetime.fromisoformat(string)
        elif "string" in kwargs.keys():
            string = kwargs["string"]
            if "T" not in string:
                raise RMTCException(f"Malformed iso datetime {string}")
            dt = datetime.datetime.fromisoformat(string)
        else:
            dt = datetime.datetime.now(datetime.timezone.utc)
        return super().__new__(
            cls,
            dt.year,
            dt.month,
            dt.day,
            dt.hour,
            dt.minute,
            dt.second,
            dt.microsecond,
            dt.tzinfo,
        )

    def __str__(self):
        return self.isoformat(sep="T")

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        new = self.__class__(self.isoformat())
        memo[id(self)] = new  # log to prevernt circular refs
        return new


class URI:
    """
    URI wrapper with parsing and manipulation capabilities.

    The URI class provides a comprehensive wrapper for Uniform Resource Identifiers
    with support for parsing, validation, and manipulation of URI components.
    It handles both string-based initialization and component-based construction,
    with automatic parsing and unparsing as needed.

    The class supports per scheme path operations, currently only supporting
    a file path implementation for 'file' schemes.
    All URI components can be accessed with a simple parameter map for options.
    """

    def __init__(
        self,
        string=None,
        scheme=None,
        user=None,
        host="",
        port=None,
        path="",
        query=None,
        fragment=None,
        uri=None,
    ):
        """Initialize URI from string or individual components."""
        self._string = ""
        if uri is not None:
            self._string = uri._string
        else:
            self._string = string
        self._scheme = scheme
        self._user = user
        self._host = host
        self._port = port
        self._path = str(path)
        if query is None:
            query = {}
        self._query = query
        self._fragment = fragment
        if self._string is not None:
            self._parse()
        else:
            self._unparse()

    def _unparse(self):
        """
        Construct URI string from individual components.

        Builds the complete URI string from the current component values,
        handling proper formatting of user credentials, port numbers,
        query parameters, and fragments.
        """
        loc = self._host
        if self._user is not None:
            loc = f"{self._user}@{loc}"
        if self._port is not None:
            loc = f"{loc}:{self._port}"
        query = urlencode(self._query, doseq=True)
        scheme = ""
        if self._scheme is not None:
            scheme = str(self._scheme)
        path = ""
        if self._path is not None:
            path = str(self._path)
        fragment = ""
        if self._fragment is not None:
            fragment = str(self._fragment)
        components = (scheme, loc, path, "", query, fragment)
        self._string = urlunparse(components)

    def _parse(self):
        """
        Parse URI string into individual components.

        Extracts all URI components from the string representation using
        urllib.parse, populating the internal component attributes.
        """
        components = urlparse(self._string)
        self._scheme = components.scheme
        self._user = components.username
        self._port = components.port
        self._host = components.hostname
        self._path = components.path
        self._query = parse_qs(components.query)
        self._fragment = components.fragment

    def __hash__(self):
        return hash(self._string)

    def __str__(self):
        """Constructs a string from the parts and returns."""
        if self._string is None:
            self._unparse()
        return self._string

    def is_valid(self):
        """Check if URI has required components for validity."""
        if self._host is None:
            return False
        if self._scheme is None:
            return False
        return len(self._host) > 0 and len(self._scheme) > 0

    @property
    def scheme(self):
        """Get the URI scheme."""
        return self._scheme

    @property
    def path(self):
        """
        Get the path component.
        Always returns an os path
        """
        return Path(self._path)

    @property
    def host(self):
        """Get the hostname component."""
        return self._host

    @property
    def user(self):
        """Get the username component."""
        return self._user

    @property
    def port(self):
        """Get the port number."""
        return self._port

    @property
    def fragment(self):
        """Get the fragment identifier."""
        return self._fragment

    @property
    def query(self):
        """Get the query parameters dictionary."""
        return self._query

    @scheme.setter
    def scheme(self, value):
        """Set the URI scheme and invalidate cached string."""
        self._scheme = value
        self._string = None

    @path.setter
    def path(self, value):
        """Set the path component and invalidate cached string."""
        self._path = str(value)
        self._string = None

    @host.setter
    def host(self, value):
        """Set the hostname and invalidate cached string."""
        self._host = value
        self._string = None

    @user.setter
    def user(self, value):
        """Set the username and invalidate cached string."""
        self._user = value
        self._string = None

    @port.setter
    def port(self, value):
        """Set the port number and invalidate cached string."""
        self._port = value
        self._string = None

    @fragment.setter
    def fragment(self, value):
        """Set the fragment identifier and invalidate cached string."""
        self._fragment = value
        self._string = None

    @query.setter
    def query(self, value):
        """Set the query parameters and invalidate cached string."""
        self._query = value
        self._string = None

    @property
    def parent(self):
        return self.__class__(path=self.path.parent)

    @parent.setter
    def parent(self, value):
        self.path = value.path / self.path.name

    def __eq__(self, other):
        """Check if this timestamp equals another."""
        if isinstance(other, URI):
            return self._string == other._string
        return False

    def __copy__(self):
        return self

    def duplicate(self):
        return copy.deepcopy(self)

    def __deepcopy__(self, memo):
        new = self.__class__(string=self._string)
        memo[id(self)] = new  # log to prevernt circular refs
        return new


class FileURI(URI):
    """Special case file"""

    def __init__(
        self,
        path=None,
        string=None,
    ):
        super(FileURI, self).__init__(
            scheme="file",
            host="localhost",
            path=path,
            string=string,
        )


class Criteria(enum.IntEnum):
    INVALID = 0  # invalid
    EXACT = 1  # ==
    LATER = 2  # >
    EARLIER = 3  # <
    MINIMUM = 4  # >=
    MAXIMUM = 5  # <=
    APPROX = 6  # ~=


class Package:
    """
    Representation of a versioned item with a name
    """

    def __init__(
        self,
        string=None,
        name=None,
        version=None,
        suffix=None,
        criteria=Criteria.EXACT,
    ):
        if string is not None:
            parts = string.split("-")
            if len(parts) == 1:
                # no version
                name = parts[0]
            elif len(parts) == 2:
                # name and version
                name = parts[0]
                version = Version(parts[1])
            elif len(parts) == 3:
                # name, version and suffix
                name = parts[0]
                version = Version(parts[1])
                suffix = parts[2]
            else:
                raise RMTCException(f"Bad version string {string}")
        if isinstance(version, str):
            version = Version(version)
        package_validity = re.compile(r"[a-z0-9A-Z_]+")
        if package_validity.fullmatch(name) is None:
            raise RMTCException(f"Bad package name {name}")
        self._name = name
        self._version = version
        self._suffix = suffix
        self._criteria = criteria

    def compatible(self, package, suffix_check=False):
        """
        Check the incoming package is compatible - which considers the
        package criteria for compatibility
        """
        if package.name != self.name:
            return False
        if self.criteria == Criteria.EXACT and not package.version == self.version:
            return False
        if self.criteria == Criteria.EARLIER and not package.version > self.version:
            return False
        if self.criteria == Criteria.LATER and not package.version < self.version:
            return False
        if self.criteria == Criteria.MINIMUM and not package.version >= self.version:
            return False
        if self.criteria == Criteria.MAXIMUM and not package.version <= self.version:
            return False
        if suffix_check:
            if self.suffix != package.suffix:
                return False
        return True

    @property
    def criteria(self):
        return self._criteria

    @property
    def name(self):
        return self._name

    @property
    def version(self):
        return self._version

    @property
    def suffix(self):
        return self._suffix

    def __repr__(self):
        if self._suffix is not None:
            return f"{self._name}-{str(self._version)}-{self._suffix}"
        return f"{self._name}-{str(self._version)}"


class Mode(enum.IntEnum):

    PRODUCTION = 0  # standard mode - no deletes allowed
    TESTING = 1  # can delete, can be cleared - DANGER-DANGER

    def __str__(self):
        return self.name.upper()


class Device(enum.IntEnum):
    """
    Enumeration for individual processing contexts in RMTC operations.
    Somewhat ambiguous - does not make a difference between vendor devices
    RMTC will attempt to take the context and map to what it can at the time
    Distributed compute is not modelled explicitly.
    """

    INVALID = 0
    CPU = 1  # Fallback
    GPU = 2  # CUDA generally
    TPU = 3  # Dedicated AI ASIC
    QPU = 4  # Quantum
    DNA = 5  # Encoded biocomputing
    REM = 6  # Remote - something else
    ALL = 100  # Any compute context

    def __str__(self):
        return self.name.upper()


class RMTCException(Exception):
    """
    Base exception class for RMTC system errors.

    The RMTCException class provides a common base for all exceptions
    raised within the RMTC system. It extends the standard Exception
    class with optional cause information for better error tracking.
    """

    def __init__(self, cause=""):
        """Initialize the exception with optional cause description."""
        super(RMTCException, self).__init__(cause)


class LogLevel(enum.IntEnum):
    """Basic log level abstraction"""

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR

    def __str__(self):
        return self.name.upper()


class LogMessage(enum.IntEnum):

    POSTED = 0
    ERROR = 1
    WARNING = 2
    INFO = 3
    DEBUG = 4


class Logger:
    """Implementation of log interface using python logging module"""

    def __init__(self, logger=None):
        if logger is None:
            logger = logging.getLogger("RMTC")
        if len(logger.handlers) == 0:
            formatter = logging.Formatter(
                "%(name)s %(levelname)s %(asctime)s: %(message)s"
            )
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        self._logger = logger
        self._broadcaster = Broadcaster()

    @property
    def logger(self):
        return self._logger

    def get_name(self):
        return self._logger.name

    def set_level(self, level=0):
        self._logger.level = level

    def debug(self, msg):
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug(msg)
            self._broadcaster(LogMessage.DEBUG, str(msg))
            self._broadcaster(LogMessage.POSTED, str(msg))

    def warning(self, msg):
        if self._logger.isEnabledFor(logging.WARNING):
            self._logger.warning(msg)
            self._broadcaster(LogMessage.WARNING, str(msg))
            self._broadcaster(LogMessage.POSTED, str(msg))

    def error(self, msg):
        if self._logger.isEnabledFor(logging.ERROR):
            self._logger.error(msg)
            self._broadcaster(LogMessage.ERROR, str(msg))
            self._broadcaster(LogMessage.POSTED, str(msg))

    def info(self, msg):
        if self._logger.isEnabledFor(logging.INFO):
            self._logger.info(msg)
            self._broadcaster(LogMessage.INFO, str(msg))
            self._broadcaster(LogMessage.POSTED, str(msg))

    def broadcaster(self):
        return self._broadcaster


class Inhibitor:

    def __init__(self, broadcaster):
        self._broadcaster = broadcaster
        self._enabled = broadcaster._enabled

    def __enter__(self):
        self._broadcaster._set_enabled(False)
        return self._broadcaster

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._broadcaster._set_enabled(self._enabled)
        return False


class Broadcaster:

    def __init__(self):
        self._listeners = {}
        self._enabled = True

    def add(self, message, listener):
        if message not in self._listeners:
            self._listeners[message] = set()
        self._listeners[message].add(listener)

    def remove(self, message, listener):
        if message in self._listeners:
            if listener in self._listeners[message]:
                self._listeners[message].remove(listener)

    def clear(self, message):
        if message in self._listeners:
            self._listeners[message] = set()

    def _set_enabled(self, enable):
        self._enabled = enable

    def __call__(self, message, data=None):
        # TODO : use queue here
        if not self._enabled:
            return
        if message not in self._listeners:
            return

        # iterate over a copy for safety
        for listener in list(self._listeners[message]):
            listener(data)


class Config:
    """
    Singleton class for managing the RMTC system configuration.

    The Config provides centralized access to RMTC system configuration
    loaded from YAML files. It implements the singleton pattern to ensure
    consistent configuration access across the application and supports
    multiple configuration file discovery strategies.

    The manager searches for configuration files in the following order:
    1. Current working directory
    2. Path from RMTC_CONFIG environment variable

    Configuration files must be valid YAML with '_type: rmtc_config' and
    a compatible version number.
    """

    CONFIG_PATH_ENV_VAR = "RMTC_CONFIGS"
    CONFIG_NAME_ENV_VAR = "RMTC_CONFIG_NAME"
    CONFIG_FILE_EXTENSIONS = [".yml", ".yaml"]
    RMTC_CONFIG_TYPE = "config"
    MIN_VERSION = "1.0.0"

    def __init__(self, overrides=None, path=None, name=None):
        """Initialize the Config singleton with configuration loading."""
        super(Config, self).__init__()
        self._overrides = overrides
        self._config_path = None
        self._config_data = {}
        self._config_name = None
        self._entries = {}
        if name is None:
            name = os.environ.get(self.CONFIG_NAME_ENV_VAR, None)
        if path is None:
            path = self._find_config(name=name)
        if path is not None:
            self._load_config(path=path)

    def __str__(self):
        return f"{self._config_path}, overrides: {self._overrides}"

    @property
    def name(self):
        return self._config_name

    @property
    def path(self):
        return self._config_path

    @property
    def overrides(self):
        return self._overrides

    def _is_valid_config_file(self, filepath):
        """Check that the given YAML file is a valid RMTC config."""
        with open(filepath, encoding="utf8") as stream:
            # Parse the yaml file
            parsed_yaml = yaml.safe_load(stream)
            if parsed_yaml.get("_type") != self.RMTC_CONFIG_TYPE:
                return False

            # Check the config version
            config_version = parsed_yaml.get("_version")
            if config_version is None or config_version == "":
                return False

            if Version(config_version) > Version(self.MIN_VERSION):
                return False

        return True

    def _find_config(self, name=None):

        # Look for config in the current directory
        config_file = self._find_config_file(os.getcwd(), name=name)

        # If config path is not provided, load from the environment
        if config_file is None:
            env_var_path = os.environ.get(self.CONFIG_PATH_ENV_VAR, None)
            if env_var_path is None:
                return None
            env_paths = env_var_path.split(":")
            for env_path in env_paths:
                config_file = self._find_config_file(env_path, name=name)
                if config_file is not None:
                    break

        return config_file

    def _find_config_file(self, path, name=None):
        """
        Find a valid RMTC configuration file in the given path.
        If name is specified - check for that name in the file
        """
        config_path = Path(path)

        # Return a valid config file
        if config_path.is_file() and config_path.suffix in self.CONFIG_FILE_EXTENSIONS:
            return path

        # Look for config files in the directory
        config_files = []
        for file_ext in self.CONFIG_FILE_EXTENSIONS:
            config_files.extend(config_path.glob(f"*{file_ext}"))

        # sort them - so we reliably get the same first config
        config_files.sort()

        # check each file
        for config_file in config_files:

            # if not valid - skip
            if not self._is_valid_config_file(config_file):
                continue

            # return first one if no name specified
            if name is None:
                return config_file

            # if name is specified - check the name is the same
            with open(config_file, encoding="utf8") as stream:
                parsed_yaml = yaml.safe_load(stream)
                if "_name" not in parsed_yaml:
                    continue
                if parsed_yaml["_name"] == name:
                    return config_file

        return None

    def _load_config(self, path):
        """
        Load and parse the RMTC configuration file.

        Implements the configuration discovery strategy by searching in
        multiple locations. Validates the configuration format, type,
        and version compatibility before loading entries.
        """

        # Parse the yaml file
        self._config_data = {}
        with open(path, encoding="utf8") as stream:
            parsed_yaml = yaml.safe_load(stream)
            self._entries = {}
            for key, value in parsed_yaml.items():
                self._entries[key] = value

        # assign overrides
        if self._overrides is not None:
            for key, sub_dict in self._overrides.items():
                if key in self._entries and isinstance(self._entries[key], dict):
                    self._entries[key].update(sub_dict)
                else:
                    self._entries[key] = sub_dict

        # store path
        self._config_path = path
        self._config_name = self._entries["_name"]

    def __getitem__(self, key):
        """Get configuration value by key."""
        if key in self._entries:
            return self._entries[key]
        return {}

    def __contains__(self, key):
        """Check if configuration key exists."""
        return key in self._entries

    def get_all_entries(self):
        """Get all config data entries"""
        # Return a copy of the entries dict because it is mutable
        return copy.deepcopy(self._entries)


class Type:
    """
    Dynamic type representation with lazy loading capabilities.

    Uses the passed in factory and type name to construct a new object.
    """

    def __init__(
        self,
        type_class=None,
        type_name=None,
        dependencies=None,
        base_class=None,
    ):
        """Initialize Type with class reference, string & environment."""
        if isinstance(type_class, Type):
            raise RMTCException(
                f"Invalid type class - {type_class}, cannot be a Type itself"
            )
        self._type_class = type_class
        self._type_name = type_name
        self._dependencies = dependencies
        self._base_class = base_class

    @property
    def base_class(self):
        return self._base_class

    @property
    def type_name(self):
        return self._type_name

    @property
    def type_class(self):
        return self._type_class

    @base_class.setter
    def base_class(self, value):
        self._base_class = value

    def is_class(self, type_class):
        if type_class is None:
            return False
        if not issubclass(type_class, self._type_class):
            return False
        return True

    def is_instance(self, instance):
        if instance is None:
            return False
        if not isinstance(instance, self._type_class):
            return False
        return True

    def is_derived(self, instance):
        if instance is None:
            return False
        if not issubclass(instance.__class__, self._type_class):
            return False
        return True

    def is_resolved(self):
        return self._type_class is not None

    def resolve(self, factory):
        if self._type_class is None:
            if self._type_name is None:
                raise RMTCException("Can't construct a Type Class without a Type Name")
            type_class = factory.resolve(
                self._type_name, dependencies=self._dependencies
            )
            if self._base_class is not None and not issubclass(
                type_class, self._base_class
            ):
                raise RMTCException(
                    f"Type {type_class} is not a subclass of base {self._base_class}"
                )
            self._type_class = type_class

    def __str__(self):
        """Return fully qualified name of the type."""
        if self._type_name is not None:
            return str(self._type_name)
        if self._type_class is not None:
            return f"{self._type_class.__name__}"
        return ""

    def __call__(self):
        """Create an instance of the wrapped type."""
        if self._type_class is None:
            raise RMTCException("Can't construct an unresolved Type")
        return self._type_class()


class TypeName:

    def __init__(
        self, string=None, module=None, category=None, version=None, name=None
    ):
        self._version = version
        self._name = name
        self._module = module
        self._category = category
        if string is not None and string != "":
            self._parse_type_name(string)
        self._string = f"{self._module}.{self._category}.{self._name}"
        if self._version is not None:
            self._string += f"-{self._version}"

    def __str__(self):
        return self._string

    def is_valid(self):
        return self._module and self._category and self._name

    def __eq__(self, other):
        return self._string == other._string

    def __lt__(self, other):
        return self._string < other._string

    def __hash__(self):
        return hash(self._string)

    @property
    def version(self):
        return self._version

    @property
    def name(self):
        return self._name

    @property
    def category(self):
        return self._category

    @property
    def module(self):
        return self._module

    def abridged(self):
        return TypeName(module=self._module, category=self._category, name=self._name)

    def _parse_type_name(self, string):
        if string is None:
            raise RMTCException(f"Invalid type name '{string}'")
        parts = string.split("-")
        self._version = None
        if len(parts) >= 2:
            self._version = Version(parts[1])
        path_parts = parts[0].split(".")
        if len(path_parts) != 3:
            raise RMTCException(f"Invalid type name '{string}'")
        self._module = path_parts[0]
        self._category = path_parts[1]
        self._name = path_parts[2]


class Factory:
    """
    Python instantiator for fully qualified module and classes.

    The Factory class provides dynamic instantiation of Python classes
    from a RMTC specific type names. It supports optional scope resolution,
    environment management, and base class validation for type safety.

    The factory uses Python's importlib to dynamically load modules and
    instantiate classes - with an effect whitelist to allow for a Python
    agnostic way to reference versioned class types.

    Factory loads all the registered extension types from modules which are
    then identified as follows: module.category.name-version
    e.g. rmtc.core.model.TorchModel-1.0.0
    """

    MODULE_PATH_ENVVAR = "RMTC_MODULES"
    MODULE_FILE_EXTENSIONS = [".yml", ".yaml"]
    MODULE_TYPE = "module"
    MIN_VERSION = "1.0.0"

    def __init__(self, log=None, env_manager=None):
        """Initialize the Factory."""

        self._paths = []
        self._env_manager = env_manager
        self._modules = {}
        self._inverse_modules = {}
        self._log = log or Logger()

        # find paths
        paths = []
        env_var_path = os.environ.get(self.MODULE_PATH_ENVVAR)
        if env_var_path is not None:
            env_var_paths = env_var_path.split(":")
            for env_path in env_var_paths:
                modules = self._find_modules(env_path)
                if modules is not None:
                    paths.extend(modules)

        # load paths
        for path in paths:
            self.load_module(path)

    def __str__(self):
        return f"Factory: {[str(item) for item in self._paths]}"

    def save(self, module_name, path):
        """Save the named module to the path"""
        raise NotImplementedError()

    def register_class(
        self,
        name,
        version,
        module,
        category,
        class_type,
        display_name=None,
        description=None,
        dependencies=None,
        deprecated=False,
        message=None,
        abstract=False,
    ):
        """
        Simple wrapper to register an internal class for testing
        or programatic module creation
        """
        class_path = f"{class_type.__module__}.{class_type.__qualname__}"
        self.register(
            name=name,
            display_name=display_name,
            description=description,
            version=version,
            module=module,
            category=category,
            class_path=class_path,
            dependencies=dependencies,
            deprecated=deprecated,
            message=message,
            abstract=abstract,
        )

    def register(
        self,
        name,
        version,
        module,
        category,
        class_path,
        display_name=None,
        description=None,
        dependencies=None,
        deprecated=False,
        message=None,
        abstract=False,
    ):
        # check types
        if not isinstance(version, Version):
            raise RMTCException(f"Invalid version {version}")

        # create tree if absent
        if module not in self._modules:
            self._modules[module] = {}
        if category not in self._modules[module]:
            self._modules[module][category] = {}
        if name not in self._modules[module][category]:
            self._modules[module][category][name] = {}
        if str(version) not in self._modules[module][category][name]:
            self._modules[module][category][name][version] = {}

        # create the entry
        type_info = {
            "class_path": class_path,
            "deprecated": deprecated,
            "abstract": abstract,
            "display_name": display_name or name,
            "description": description or "",
            "dependencies": dependencies or [],
            "message": message or "",
        }
        self._modules[module][category][name][version] = type_info

        # create reverse lookup
        type_name = TypeName(
            module=module, category=category, name=name, version=version
        )
        if class_path in self._inverse_modules:
            raise RMTCException(f"Already registered {class_path}")
        self._inverse_modules[class_path] = type_name

        # return the new type name
        self._log.debug(f"Registered: {type_name}")
        return type_name

    def deregister(self, type_name):
        module = type_name.module
        version = type_name.version
        category = type_name.category
        name = type_name.name
        del self._modules[module][category][name][version]
        del self._inverse_modules[type_name]

    def is_registered_type_class(self, type_class):
        type_name = self.resolve_inverse(type_class)
        return type_name is not None

    def is_registered_type_name(self, type_name):
        type_class = self.resolve(type_name)
        return type_class is not None

    def get_type_info(self, type_name):

        # type name valid
        if type_name is None or not type_name.is_valid():
            return None

        # get parts
        module = type_name.module
        category = type_name.category
        name = type_name.name

        # check we have something
        if module not in self._modules:
            self._log.warning(f"{type_name} module not registered with factory")
            return None
        if category not in self._modules[module]:
            self._log.warning(f"{type_name} category not registered with factory")
            return None
        if name not in self._modules[module][category]:
            self._log.warning(f"{type_name} name not registered with factory")
            return None

        # get version
        version = type_name.version
        if version is None:
            version = self.get_versions(type_name)[-1]
            if version is not None:
                self._log.debug(
                    f"Resolving partial type name: {type_name} with version {version}"
                )
        if version not in self._modules[module][category][name]:
            msg1 = f"Invalid factory state getting info for '{type_name}'"
            msg2 = f"Version {version} not found"
            msg3 = f"Modules: {self._modules}"
            raise RMTCException(f"{msg1}\n{msg2}\n{msg3}")

        return self._modules[module][category][name][version]

    def resolve_inverse(self, cls):
        """
        For a given python class, get the type_name - uses the map in the register
        """
        if cls is None:
            return None
        class_path = f"{cls.__module__}.{cls.__name__}"
        if class_path not in self._inverse_modules:
            raise RMTCException(f"Class {class_path} not registered with factory")
        return self._inverse_modules[class_path]

    def resolve(self, type_name, dependencies=None):
        """
        Take the type name and find the Python class from it
        Dynamically imports the module and instantiates the class - uses the module
        registration white lists to establish the python class name
        """

        type_info = self.get_type_info(type_name)
        if type_info is None:
            self._log.warning(f"Cannot get type info for {type_name}")
            return None
        return self._create_class(type_info["class_path"], dependencies)

    def _create_class(self, class_path, dependencies):

        # setup env
        if self._env_manager:
            self._env_manager.add_packages(dependencies)

        # import
        parts = class_path.split(".")
        module_name = ".".join(parts[:-1])
        class_name = parts[-1]
        class_obj = None
        try:
            module = importlib.import_module(module_name)
            importlib.invalidate_caches()
            class_obj = getattr(module, class_name)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._log.error(f"Cannot import: '{class_path}' - {e}")

        return class_obj

    def get_type_names(self, category, module=None, abridged=True):
        """
        Get all the type names of items in a given category & module,
        if abridged is true, return all the available versions
        """
        entries = set()
        modules = []
        if module is not None:
            if module in self._modules:
                modules = self._modules[module]
        else:
            modules = self._modules.keys()
        for mod in modules:
            if category in self._modules[mod]:
                for name in self._modules[mod][category].keys():
                    if not abridged:
                        for version in self._modules[mod][category][name].keys():
                            entries.add(
                                TypeName(
                                    module=mod,
                                    category=category,
                                    name=name,
                                    version=version,
                                )
                            )
                    else:
                        entries.add(TypeName(module=mod, category=category, name=name))
        return list(entries)

    def get_versions(self, type_name):

        if not type_name.is_valid():
            return []

        # split parts
        module = type_name.module
        version = type_name.version
        category = type_name.category
        name = type_name.name

        # if type name has a version - it's that version
        if (
            version is not None
            and version in self._modules[module][category][name].keys()
        ):
            return [version]

        # get all version keys and sort
        versions = list(self._modules[module][category][name].keys())
        versions.sort()
        return versions

    def create(
        self,
        type_name,
        **kwargs,
    ):
        """
        Create an instance of the specified class by fully qualified name.
        """

        if type_name is None:
            return None

        if isinstance(type_name, str):
            type_name = TypeName(string=type_name)
        type_info = self.get_type_info(type_name)
        if type_info is None:
            raise RMTCException(f"No type registered for {type_name}")
        if type_info["deprecated"]:
            msg = type_info["message"]
            self._log.warning(f"Instantiating deprecated class {type_name} {msg}")
        type_class = self._create_class(
            type_info["class_path"],
            type_info["dependencies"],
        )
        if type_class is not None:
            return type_class(**kwargs)
        return None

    def _is_valid_module_file(self, path):
        with open(path, encoding="utf8") as stream:
            parsed_yaml = yaml.safe_load(stream)
            if parsed_yaml.get("_type") != self.MODULE_TYPE:
                return False
            config_version = parsed_yaml.get("_version")
            if Version(config_version) > Version(self.MIN_VERSION):
                return False
        return True

    def _find_modules(self, path):
        config_path = Path(path)
        if config_path.is_file() and config_path.suffix in self.MODULE_FILE_EXTENSIONS:
            return path
        module_paths = []
        module_files = []
        for file_ext in self.MODULE_FILE_EXTENSIONS:
            module_paths.extend(config_path.glob(f"*{file_ext}"))
        for module_path in module_paths:
            if self._is_valid_module_file(module_path):
                module_files.append(module_path)
        return module_files

    def load_module(self, path):
        with open(path, encoding="utf8") as stream:
            parsed_yaml = yaml.safe_load(stream)
            module_name = parsed_yaml.get("_name")
            for category, value in parsed_yaml.items():
                if category.startswith("_"):
                    continue
                for name, type_info in value.items():
                    display_name = name
                    if "display_name" in type_info:
                        display_name = str(type_info["display_name"])
                    description = ""
                    if "description" in type_info:
                        display_name = str(type_info["description"])
                    deprecated = False
                    if "deprecated" in type_info:
                        deprecated = bool(type_info["deprecated"])
                    message = ""
                    if "message" in type_info:
                        message = str(type_info["message"])
                    version = None
                    if "version" in type_info:
                        version = Version(type_info["version"])
                    else:
                        raise RMTCException(
                            f"Version missing when registering {module_name}.{category}.{name}"
                        )
                    abstract = False
                    if "abstract" in type_info:
                        abstract = bool(type_info["abstract"])
                    self.register(
                        name=name,
                        module=module_name,
                        display_name=display_name,
                        description=description,
                        category=category,
                        class_path=type_info["class_path"],
                        version=version,
                        dependencies=[],
                        deprecated=deprecated,
                        abstract=abstract,
                        message=message,
                    )
        self._log.debug(f"Registered Module: {path}")
        self._paths.append(path)


class Serializer(ABC):
    """
    Abstract base class for object serialization and deserialization.
    """

    def __init__(self, factory, objects):
        """Initialize the Serializer with factory and objects."""
        self._factory = factory
        self._objects = objects

    @property
    def factory(self):
        """Get the object factory used for deserialization."""
        return self._factory

    @property
    def objects(self):
        """Get the Objects lookup table that deserialized entities are added to."""
        return self._objects

    @abstractmethod
    def serialize(self, entities):
        """
        Convert the given entities into a string.

        Abstract method that must be implemented by subclasses to define
        how objects are converted to string format with type preservation.

        The implementation should:
        - Convert the passed entities, in order
        - Preserve type information for accurate deserialization
        - Handle complex object relationships and references
        """

    @abstractmethod
    def deserialize(self, string):
        """
        Create or update the object list from a string.

        Abstract method that must be implemented by subclasses to define
        how objects are reconstructed from the string format using type information.

        The implementation should:
        - Parse the string to extract object data and types
        - Reuse entities already in the objects lookup, or create them via the factory
        - Restore object relationships and references
        - Add the reconstructed entities to the objects lookup
        """
