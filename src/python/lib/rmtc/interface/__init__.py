# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

"""
Interfaces to wrap the system object,
for example REST, RPC or other remote calling
architectures.
"""


from abc import ABC


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

    def __init__(self, rmtc_system=None, serializer=None):
        """Initialize the Interface with system and serializer components."""
        self._system = rmtc_system
        self._serializer = serializer

    # TODO : add the end points in here

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

    def __init__(self, rmtc_system=None, serializer=None):
        """Initialize the Client interface."""
        super(Client, self).__init__(rmtc_system=rmtc_system, serializer=serializer)


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

    def __init__(self, rmtc_system=None, serializer=None):
        """Initialize the Server interface."""
        super(Server, self).__init__(rmtc_system=rmtc_system, serializer=serializer)
