from __future__ import annotations

import pickle
from queue import Empty as QueueEmptyError
from queue import Queue
from threading import Event as ThreadEvent
from threading import Thread
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast

from ..logger import Logger
from ..types import Disconnect, GetEnvrionment, InstallRequirements, ModifyInterpreter, PythonEnvironment, RunCode

if TYPE_CHECKING:
    from .client_manager import ClientManager


class WriteCallback(Protocol):
    """Callback protocol for writing messages to the client"""

    def __call__(self, client_id: bytes, msg_type: bytes, body: bytes) -> Any: ...


class RequestWorker(Thread, Logger):
    """Request worker thread to handle incoming requests from clients."""

    def __init__(
        self,
        queue: Queue,
        client_manager: ClientManager,
        callback: WriteCallback,
        stop_event: ThreadEvent,
    ) -> None:
        """
        Initialize the worker thread.

        Args:
            queue: The queue to receive requests from
            client_manager: The client manager instance to use for processing client requests
            callback: The callback to write responses to
            stop_event: The event to stop the worker thread
        """
        self._queue = queue
        self._client_manager = client_manager
        self._stop_event = stop_event
        self._callback = callback
        super().__init__(daemon=True)

    def _get_environment(self, client_id: bytes, environment_type: Literal["current", "all"]) -> None:
        """
        Get current or all python environment(s) of the client.

        Args:
            client_id: The client id
            environment_type: The type of environment to get
        """
        if (client_info := self._client_manager.get_info(client_id.decode())) is None:
            return

        if environment_type == "current":
            self._callback(client_id, b"request_done", pickle.dumps(client_info.current.environment))
        elif environment_type == "all":
            self._callback(client_id, b"request_done", pickle.dumps(list(client_info.interpreters)))

    def _modify_interpreter(
        self, client_id: bytes, environment: PythonEnvironment | str, mode: Literal["switch", "delete"]
    ) -> None:
        """
        Modify the client's interpreter based on the given environment and mode.

        Args:
            client_id: The client id
            environment: The environment to use
            mode: The mode to use
        """
        client_id_str = client_id.decode()
        _switch = lambda env: self._callback(
            client_id, b"request_done", pickle.dumps(self._client_manager.switch_interpreter(client_id_str, env))
        )
        try:
            if mode == "switch":
                _switch(environment)
            elif mode == "delete":
                self._client_manager.delete_interpreter(client_id_str, environment)
                _switch(self._client_manager.get_info(client_id_str).default_environment)  # type: ignore[union-attr]

        except Exception as e:
            self._callback(client_id, b"request_exception", str(e).encode())

    def _install_requirements(self, client_id: bytes, requirements: list[str]) -> None:
        """
        Install the given requirements in client's current interpreter.

        Args:
            client_id: The client id
            requirements: The requirements to install
        """
        if (client_info := self._client_manager.get_info(client_id.decode())) is None:
            return

        for response in client_info.current.interpreter._send_input(requirements=requirements):
            self._callback(client_id, b"interpreter", pickle.dumps(response))

        # Tell client to not wait for more responses
        self._callback(client_id, b"request_done", b"")

    def _run_code(self, client_id: bytes, code: str) -> None:
        """
        Run the code in client's current interpreter.

        Args:
            client_id: The client id
            code: The code to run
        """
        if (client_info := self._client_manager.get_info(client_id.decode())) is None:
            return

        for response in client_info.current.interpreter._send_input(code=code):
            self._callback(client_id, b"interpreter", pickle.dumps(response))

    def _remove_client(self, client_id: bytes) -> None:
        """Remove the client from the client manager"""
        self._client_manager.remove(client_id.decode())
        self._callback(client_id, b"request_done", b"")

    def run(self) -> None:  # noqa: C901
        """Run the worker thread."""
        while not self._stop_event.is_set():
            try:
                client_id, request_bytes = cast(tuple[bytes, bytes], self._queue.get(timeout=1))
                request = pickle.loads(request_bytes)
                try:
                    client_id_str = client_id.decode()
                    if isinstance(request, ModifyInterpreter):
                        # Register with default environment
                        self._client_manager.register(client_id_str, request.environment)
                    else:
                        self._client_manager.register(client_id_str)

                except Exception as e:
                    self._callback(client_id, b"request_exception", str(e).encode())
                    continue

                if isinstance(request, GetEnvrionment):
                    self._get_environment(client_id, request.environment_type)
                elif isinstance(request, ModifyInterpreter):
                    self._modify_interpreter(client_id, request.environment, request.mode)
                elif isinstance(request, InstallRequirements):
                    self._install_requirements(client_id, request.requirements)
                elif isinstance(request, RunCode):
                    self._run_code(client_id, request.code)
                elif isinstance(request, Disconnect):
                    self._remove_client(client_id)
            except QueueEmptyError:
                continue
            except Exception as e:
                self.logger.error(f"{e.__class__.__name__}: {e!s}")
