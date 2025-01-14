from __future__ import annotations

import pickle
from queue import Empty as QueueEmptyError
from queue import Queue
from threading import Event as ThreadEvent
from threading import Thread
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast

from ..logger import Logger
from ..types import (
    Disconnect,
    GetPythonEnvironment,
    InstallRequirements,
    ModifyInterpreter,
    PythonEnvironment,
    RunCode,
    RunCommand,
    SetEnvironmentVariables,
)

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

    def _get_python_environment(self, client_id: bytes, type: Literal["current", "all", "default"]) -> None:  # noqa: A002
        """
        Get client's python environment of certain type.

        Args:
            client_id: The client id
            type: The type of python environment to get
        """
        if (client_info := self._client_manager.get_info(client_id.decode())) is None:
            return

        if type == "all":
            self._callback(client_id, b"request_done", pickle.dumps(list(client_info.interpreters)))
        elif type == "current":
            self._callback(client_id, b"request_done", pickle.dumps(client_info.current.environment))
        elif type == "default":
            self._callback(client_id, b"request_done", pickle.dumps(client_info.default_environment))

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
        # fmt: off
        _switch = lambda env: self._callback(
            client_id,
            b"request_done",
            pickle.dumps(self._client_manager.switch_interpreter(client_id_str, env))
        )
        # fmt: on
        try:
            if mode == "switch":
                _switch(environment)
            elif mode == "delete":
                self._client_manager.delete_interpreter(client_id_str, environment)
                _switch(self._client_manager.get_info(client_id_str).default_environment)  # type: ignore[union-attr]

        except Exception as e:
            print(str(e))
            self._callback(client_id, b"request_exception", str(e).encode())

    def _send_input_to_interpreter(self, client_id: bytes, **kwargs: Any) -> None:
        """
        Send input to interpreter.

        Args:
            client_id: The client id
            **kwargs: The input data
        """
        if (client_info := self._client_manager.get_info(client_id.decode())) is None:
            return

        for response in client_info.current.interpreter._send_input(**kwargs):
            self._callback(client_id, b"interpreter", pickle.dumps(response))

        # Tell client to not wait for more responses
        self._callback(client_id, b"request_done", b"")

    def run(self) -> None:
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

                if isinstance(request, GetPythonEnvironment):
                    self._get_python_environment(client_id, request.type)
                elif isinstance(request, ModifyInterpreter):
                    self._modify_interpreter(client_id, request.environment, request.mode)
                elif isinstance(request, (SetEnvironmentVariables, InstallRequirements, RunCode, RunCommand)):
                    self._send_input_to_interpreter(client_id, **request.__dict__)
                elif isinstance(request, Disconnect):
                    self._client_manager.remove(client_id.decode())
                    self._callback(client_id, b"request_done", b"")
            except QueueEmptyError:
                continue
            except Exception as e:
                self.logger.error(f"{e.__class__.__name__}: {e!s}")
