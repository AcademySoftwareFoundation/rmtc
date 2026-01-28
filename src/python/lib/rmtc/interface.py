# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Interfaces to wrap the system object,
for example REST, RPC or other remote calling
architectures.
"""


from abc import ABC, abstractmethod


class Serializer(ABC):
    """
    Abstract base class for object serialization and deserialization.

    The Serializer class provides a framework for converting objects to and from
    a text format with type information preservation. It manages a factory for
    object creation and maintains a collection of objects to be serialized.

    This class is designed to handle complex object hierarchies while preserving
    type information during the serialization process, enabling accurate
    reconstruction of objects during deserialization.
    """

    def __init__(self, factory, objects):
        """Initialize the Serializer with factory and objects."""
        self._factory = factory
        self._objects = objects

    @property
    def factory(self):
        """Get the object factory used for deserialization."""
        return self._factory

    def objects(self):
        """Get the collection of objects managed by this serializer."""
        return self._objects

    @abstractmethod
    def serialize(self):
        """
        Convert the object list into a JSON string.

        Abstract method that must be implemented by subclasses to define
        how objects are converted to string format with type preservation.

        The implementation should:
        - Convert all managed objects to JSON format
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
        - Use the factory to create appropriate object instances
        - Restore object relationships and references
        - Update the managed objects collection
        """


class Interface(ABC):
    """
    Abstract base class for system interfaces.

    The Interface class provides a common foundation for client-server
    communication interfaces in the RMTC system. It manages system
    connections and serialization components for data exchange.

    This class serves as the base for both client and server implementations,
    providing shared functionality for entity management and system interaction.
    The interface supports pluggable serialization strategies for flexible
    data format handling.
    """

    # TODO: This is incomplete testing code only

    def __init__(self, system=None, serializer=None):
        """Initialize the Interface with system and serializer components."""
        self._system = system
        self._serializer = serializer

    @abstractmethod
    def get_entities(self, name=None):
        """Retrieve entities from the system by name."""
        pass

    @property
    def system(self):
        """Get the RMTC system instance."""
        return self._system


class Client(Interface):
    """
    Client-side interface for RMTC system communication.

    The Client class implements the client-side functionality for communicating
    with RMTC systems. It extends the base Interface class to provide
    client-specific operations and behaviors.

    This class is designed to handle client-side concerns such as remote
    system connections, request formatting, and response processing. It
    provides a local interface to remote RMTC system capabilities.
    """

    # TODO: This is incomplete testing code only

    def __init__(self, system=None, serializer=None):
        """Initialize the Client interface."""
        super(Client, self).__init__(system=system, serializer=serializer)


class Server(Interface):
    """
    Server-side interface for RMTC system communication.

    The Server class implements the server-side functionality for handling
    RMTC system requests. It extends the base Interface class to provide
    server-specific operations and request processing capabilities.

    This class is designed to handle server-side concerns such as request
    routing, authentication, authorization, and response generation. It
    provides the server endpoint for RMTC system operations.
    """

    # TODO: This is incomplete testing code only

    def __init__(self, system=None, serializer=None):
        """Initialize the Server interface."""
        super(Server, self).__init__(system=system, serializer=serializer)
