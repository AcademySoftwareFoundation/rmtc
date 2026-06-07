# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Essential basic system classes
"""

import os
import enum
import datetime
import logging
import importlib
import copy

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from pathlib import Path
from abc import ABC, abstractmethod
from packaging import version

import yaml

# Alias version
Version = version.Version


class TypeName:

    def __init__(self, string=None, module=None, category=None, ver=None, name=None):
        self._version = ver
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

    def __repr__(self):
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
    def ver(self):
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


class IConfig(ABC):

    @abstractmethod
    def __getitem__(self, key):
        """Get configuration value by key."""
        return None


class IFactory(ABC):

    @abstractmethod
    def register(
        self,
        name,
        display_name,
        ver,
        module,
        category,
        class_path,
        dependencies,
    ):
        pass

    @abstractmethod
    def deregister(
        self,
        type_name,
    ):
        pass

    @abstractmethod
    def create(self, type_name):
        return None

    @abstractmethod
    def get_type_names(self, category, module=None, abridged=True):
        """
        Get a list of all type names in a given category and module,
        if versioned is True - it will be qualified with version
        """
        return []

    @abstractmethod
    def get_versions(self, unversioned_type_name):
        """
        Given an unversioned type name module.category.name
        Return back all the versions
        """
        return []

    @abstractmethod
    def is_registered_type_class(self, type_class):
        return None

    @abstractmethod
    def is_registered_type_name(self, type_name):
        return None

    @abstractmethod
    def get_type_info(self, type_name):
        return None

    @abstractmethod
    def resolve_inverse(self, cls):
        return None

    @abstractmethod
    def resolve(self, type_name, env=None):
        return None


class ModuleFactory(IFactory):
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
    e.g. rmtc_core.model.TorchModel-1.0.0
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
        self._log = log

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
            self._load_module(path)
            log.debug(f"Registered module: {path}")

    def __repr__(self):
        return f"Factory: {[str(item) for item in self._paths]}"

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

    def _load_module(self, path):
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
                    deprecated = False
                    if "deprecated" in type_info:
                        deprecated = bool(type_info["deprecated"])
                    message = ""
                    if "message" in type_info:
                        message = str(type_info["message"])
                    if "version" in type_info:
                        ver = Version(type_info["version"])
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
                        category=category,
                        class_path=type_info["class_path"],
                        ver=ver,
                        dependencies=[],
                        deprecated=deprecated,
                        abstract=abstract,
                        message=message,
                    )
        self._log.debug(f"Registered Module: {path}")
        self._paths.append(path)

    def register(
        self,
        name,
        display_name,
        ver,
        module,
        category,
        class_path,
        dependencies,
        deprecated=False,
        message="",
        abstract=False,
    ):
        # create tree if absent
        if module not in self._modules:
            self._modules[module] = {}
        if category not in self._modules[module]:
            self._modules[module][category] = {}
        if name not in self._modules[module][category]:
            self._modules[module][category][name] = {}
        if str(ver) not in self._modules[module][category][name]:
            self._modules[module][category][name][ver] = {}

        # create the entry
        type_info = {
            "class_path": class_path,
            "display_name": display_name,
            "dependencies": dependencies,
            "deprecated": deprecated,
            "message": message,
            "abstract": abstract,
        }
        self._modules[module][category][name][ver] = type_info

        # create reverse lookup
        type_name = TypeName(module=module, category=category, name=name, ver=ver)
        self._inverse_modules[class_path] = type_name

        # return the new type name
        self._log.debug(f"Registered: {type_name}")
        return type_name

    def deregister(self, type_name):
        module = type_name.module
        ver = type_name.ver
        category = type_name.category
        name = type_name.name
        del self._modules[module][category][name][ver]
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
        ver = type_name.ver
        if ver is None:
            ver = self.get_versions(type_name)[-1]
            if ver is not None:
                self._log.warning(
                    f"Resolving partial type name: {type_name} with version {ver}"
                )
        if ver is None:
            raise RMTCException(f"Invalid factory state for '{type_name}'")

        return self._modules[module][category][name][ver]

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

    def resolve(self, type_name, env=None):
        """
        Take the type name and find the Python class from it
        Dynamically imports the module and instantiates the class - uses the module
        registration white lists to establish the python class name
        """

        type_info = self.get_type_info(type_name)
        if type_info is None:
            self._log.warning(f"Cannot get type info for {type_name}")
            return None
        return self._create_class(type_info["class_path"], env)

    def _create_class(self, class_path, env):

        # setup env
        if self._env_manager:
            self._env_manager.setup(env)

        # import
        parts = class_path.split(".")
        module_name = ".".join(parts[:-1])
        class_name = parts[-1]
        class_obj = None
        try:
            module = importlib.import_module(module_name)
            class_obj = getattr(module, class_name)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._log.error(f"Cannot import: '{class_path}'\n{e}")

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
                        for ver in self._modules[mod][category][name].keys():
                            entries.add(
                                TypeName(
                                    module=mod, category=category, name=name, ver=ver
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
        ver = type_name.ver
        category = type_name.category
        name = type_name.name

        # if type name has a version - it's that version
        if ver is not None and ver in self._modules[module][category][name].keys():
            return [ver]

        # get all version keys and sort
        versions = list(self._modules[module][category][name].keys())
        versions.sort()
        return versions

    def create(
        self,
        type_name,
        env=None,
    ):
        """
        Create an instance of the specified class by fully qualified name.
        """

        if type_name is None:
            return None

        if isinstance(type_name, str):
            type_name = TypeName(string=type_name)
        type_info = self.get_type_info(type_name)
        if type_info["deprecated"]:
            msg = type_info["message"]
            self._log.warning(f"Instantiating deprecated class {type_name} {msg}")
        type_class = self._create_class(type_info["class_path"], env)
        if type_class is not None:
            return type_class()
        return None


class Mode(enum.IntEnum):

    PRODUCTION = 0  # standard mode - no deletes allowed
    DEVELOPMENT = 1  # developer features with debugging & deleted, some persistence
    TESTING = 2  # automated testing features - unit test, everything is volatile

    def __str__(self):
        return self.name.upper()


class Datetime(datetime.datetime):
    """Create datetime wrapper that enforces ISO UTC format"""

    def __new__(cls, *args, **kwargs):  # pylint: disable=unused-argument
        dt = None
        if len(args) == 1 and isinstance(args[0], str):
            dt = datetime.datetime.fromisoformat(args[0])
        elif "string" in kwargs.keys():
            dt = datetime.datetime.fromisoformat(kwargs["string"])
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
        return self.isoformat()

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        new = self.__class__(self.isoformat())
        memo[id(self)] = new  # log to prevernt circular refs
        return new


class IIDGenerator(ABC):

    @abstractmethod
    def generate(self):
        return "invalid"


class Context(enum.IntEnum):
    """Enumeration for execution contexts in RMTC operations."""

    INVALID = 0
    CPU = 1
    GPU = 2

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


class Type:
    """
    Dynamic type representation with lazy loading capabilities.

    Uses the passed in factory and type name to construct a new object.
    """

    def __init__(
        self,
        type_class=None,
        type_name=None,
        env=None,
        base_class=None,
    ):
        """Initialize Type with class reference, string & environment."""
        if isinstance(type_class, Type):
            raise RMTCException(
                f"Invalid type class - {type_class}, cannot be a Type itself"
            )
        self._type_class = type_class
        self._type_name = type_name
        self._env = env
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

    def is_resolved(self):
        return self._type_class is not None

    def resolve(self, factory):
        if self._type_class is None:
            if self._type_name is None:
                raise RMTCException("Can't construct a Type Class without a Type Name")
            type_class = factory.resolve(self._type_name, env=self._env)
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

    def __repr__(self):
        """Return fully qualified name of the type."""
        return f"Type: {str(self)}"

    def __call__(self):
        """Create an instance of the wrapped type."""
        if self._type_class is None:
            raise RMTCException("Can't construct an unresolved Type")
        return self._type_class()


class Package:
    """
    Representation of a versioned item with a name
    """

    def __init__(
        self,
        string=None,
        name=None,
        ver=None,
    ):
        if string:
            parts = string.split("-")
            if len(parts) == 1:
                name = parts[0]
            if len(parts) == 2:
                ver = Version(parts[1])
        if isinstance(ver, str):
            ver = Version(ver)
        self._name = name
        self._ver = ver

    @property
    def name(self):
        return self._name

    @property
    def ver(self):
        return self._ver

    def __repr__(self):
        return f"{self._name}-{self._ver}"


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

    def __repr__(self):
        """Constructs a string from the parts and returns."""
        if self._string is None:
            self._unparse()
        return self._string

    def valid(self):
        """Check if URI has required components for validity."""
        if self._host is None:
            return False
        if self._scheme is None:
            return False
        return len(self._host) > 0 and len(self._scheme) > 0

    def exists(self):
        """Check if the URI resource exists (file URIs only)."""
        if self.scheme == "file":
            return self.path.exists()
        return False

    def create(self):
        """
        Create the URI resource (file URIs only).

        Creates directories for file:// URIs, including parent directories.
        """
        if self.scheme == "file":
            self.path.mkdir(parents=True, exist_ok=True)

    @property
    def scheme(self):
        """Get the URI scheme."""
        return self._scheme

    @property
    def path(self):
        """Get the path component."""
        if self.scheme == "file":
            return Path(self._path)
        return self._path

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

    def __eq__(self, other):
        """Check if this timestamp equals another."""
        if isinstance(other, URI):
            return self._string == other._string
        return False


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


class ILog(ABC):
    """Basic log abstraction to allow for specific log delegation"""

    @abstractmethod
    def get_name(self):
        pass

    @abstractmethod
    def set_level(self, level=0):
        pass

    @abstractmethod
    def debug(self, msg):
        pass

    @abstractmethod
    def warning(self, msg):
        pass

    @abstractmethod
    def error(self, msg):
        pass

    @abstractmethod
    def broadcaster(self):
        pass

    @abstractmethod
    def info(self, msg):
        pass

    def __repr__(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__}"


class Logger(ILog):
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

    def set_enabled(self, enable):
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


class Config(IConfig):
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

    CONFIG_PATH_ENV_VAR = "RMTC_CONFIG"
    CONFIG_FILE_EXTENSIONS = [".yml", ".yaml"]
    RMTC_INSTALL_ENV_VAR = "RMTC_HOME"
    RMTC_CONFIG_TYPE = "config"
    MIN_VERSION = "1.0.0"

    def __init__(self, overrides=None):
        """Initialize the Config singleton with configuration loading."""
        super(Config, self).__init__()
        self._overrides = overrides
        self._config_path = None
        self._config_data = {}
        self._entries = {}
        path = self._find_config()
        if path is not None:
            self._load_config(path=path)

    def __repr__(self):
        return f"{self._config_path}, overrides: {self._overrides}"

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

    def _find_config(self):

        # Look for config in the current directory
        config_file = self._find_config_file(os.getcwd())

        # If config path is not provided, load from the environment
        if config_file is None:
            env_var_path = os.environ.get(self.CONFIG_PATH_ENV_VAR, None)
            if env_var_path is not None:
                for env_path in env_var_path.split(":"):
                    config_file = self._find_config_file(env_path)
                    if config_file is not None:
                        break
        if config_file is None:
            raise RMTCException(
                "Cannot find a valid RMTC config file in the current directory or from"
                f" the {self.CONFIG_PATH_ENV_VAR} environment variable"
            )

        return config_file

    def _find_config_file(self, path):
        """
        Find a valid RMTC configuration file in the given path.
        """
        config_path = Path(path)

        # Return a valid config file
        if config_path.is_file() and config_path.suffix in self.CONFIG_FILE_EXTENSIONS:
            return path

        # Look for config files in the directory
        config_files = []
        for file_ext in self.CONFIG_FILE_EXTENSIONS:
            config_files.extend(config_path.glob(f"*{file_ext}"))
        for config_file in config_files:
            if self._is_valid_config_file(config_file):
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
