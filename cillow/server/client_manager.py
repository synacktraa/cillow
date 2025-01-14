from __future__ import annotations

import multiprocessing
import threading
from dataclasses import dataclass

from ..importhook import validate_environment
from ..logger import Logger
from ..types import PythonEnvironment
from ._process import _InterpreterProcess

__all__ = (
    "ClientInfo",
    "ClientManager",
)


@dataclass(frozen=True)
class CurrentContext:
    """Current context information"""

    environment: PythonEnvironment
    interpreter: _InterpreterProcess


@dataclass
class ClientInfo:
    """Client information"""

    current: CurrentContext
    default_environment: PythonEnvironment
    interpreters: dict[PythonEnvironment, _InterpreterProcess]


class ClientManager(Logger):
    """
    Manages clients and their interpreter processes.

    This class is utilized by the server component to share the instance with all the request worker threads.
    """

    def __init__(self, max_interpreters: int | None = None, interpreters_per_client: int | None = None):
        """
        Initialize the client manager.

        Args:
            max_interpreters: Maximum total interpreter processes allowed. Defaults to `os.cpu_count()`
            interpreters_per_client: Maximum processes per client. Defaults to `min(2, max_interpreters)`
        """
        self.cpu_count = multiprocessing.cpu_count()
        self.max_interpreters = min(max_interpreters or self.cpu_count, self.cpu_count)
        self.interpreters_per_client = interpreters_per_client or min(2, self.max_interpreters)
        self.max_clients = self.max_interpreters // self.interpreters_per_client

        self._lock = threading.Lock()
        self._clients: dict[str, ClientInfo] = {}

    @property
    def optimal_number_of_request_workers(self) -> int:
        """Optimal number of request worker threads based on current limits."""
        return min(2 * self.max_clients, self.cpu_count)

    @property
    def optimal_max_queue_size(self) -> int:
        """Get optimal maximum queue size based on current limits."""
        return self.max_clients * self.interpreters_per_client * 2

    @property
    def total_active_processes(self) -> int:
        """Get total number of active interpreter processes."""
        return sum(len(client.interpreters) for client in self._clients.values())

    def register(self, client_id: str, environment: PythonEnvironment | str = "$system") -> None:
        """
        Register a client if possible.

        Args:
            client_id: The client identifier
            environment: The environment to use. This environment will be used as default when an interpreter process is deleted.

        Raises:
            Exception: If the client limit is exceeded.
            LookupError: If the given environment is invalid or not found.
        """
        with self._lock:
            if client_id in self._clients:
                return

            # Check if a new client can be accepted based on current limits.
            if not len(self._clients) < self.max_clients:
                raise Exception("Client limit exceeded. Try again later.")

            environment = validate_environment(environment or "$system")
            interpreter = _InterpreterProcess(environment)
            self._clients[client_id] = ClientInfo(
                default_environment=environment,
                current=CurrentContext(environment=environment, interpreter=interpreter),
                interpreters={environment: interpreter},
            )
            self.logger.info(f"Client {client_id!r} joined the server with {str(environment)!r} environment")

    def get_info(self, client_id: str) -> ClientInfo | None:
        """Get client info"""
        with self._lock:
            return self._clients.get(client_id)

    def switch_interpreter(self, client_id: str, environment: PythonEnvironment | str) -> PythonEnvironment:
        """
        Switch client to interpreter process based on the given environment.

        Args:
            client_id: The client identifier
            environment: The environment to switch to

        Raises:
            Exception: If unable to create new interpreter due to process limit
            LookupError: If the given environment is invalid or not found
            ValueError: If client is not found

        Returns:
            The valid Python environment value
        """
        with self._lock:
            if (client_info := self._clients.get(client_id)) is None:
                raise ValueError(f"Client {client_id!r} not found.")

            environment = validate_environment(environment)
            if client_info.current.environment == environment:
                return environment

            if not (interpreter := client_info.interpreters.get(environment)):
                # Check if client and total process limits are met to create new interpreter
                if (
                    len(client_info.interpreters) < self.interpreters_per_client
                    and self.total_active_processes < self.max_interpreters
                ):
                    interpreter = _InterpreterProcess(environment)
                    client_info.interpreters[environment] = interpreter
                else:
                    raise Exception("Unable to create new interpreter due to process limit.")

            self._clients[client_id].current = CurrentContext(environment=environment, interpreter=interpreter)
            return environment

    def delete_interpreter(self, client_id: str, environment: PythonEnvironment | str) -> None:
        """
        Delete client's interpreter processes at the given environment.

        Args:
            client_id: The client identifier
            environment: The environment associated with the interpreter
        """
        with self._lock:
            if (client_info := self._clients.get(client_id)) is None:
                return

            try:
                environment = validate_environment(environment)
                client_info.interpreters.pop(environment).stop()
            except KeyError:
                return

    def remove(self, client_id: str) -> None:
        """
        Remove a client and stop all its interpreter processes.

        Args:
            client_id: The client identifier
        """
        with self._lock:
            if (client_info := self._clients.get(client_id)) is None:
                return

            for interpreter in client_info.interpreters.values():
                interpreter.stop()
            del self._clients[client_id]
            self.logger.info(f"Client {client_id!r} left the server")

    def cleanup(self) -> None:
        """Stop all the interpreter processes."""
        for info in self._clients.values():
            for interpreter in info.interpreters.values():
                interpreter.stop()
        self._clients.clear()
