from __future__ import annotations

import pickle
from collections.abc import Generator
from typing import Any, Callable
from uuid import uuid4

import zmq

from .interpreter import default_stream_processor
from .types import (
    ByteStream,
    Disconnect,
    ExceptionInfo,
    Execution,
    GetEnvrionment,
    InstallRequirements,
    ModifyInterpreter,
    PythonEnvironment,
    Result,
    RunCode,
    Stream,
)

__all__ = ("Client",)


class Client:
    """
    Cillow client interface.

    Examples:
        >>> import cillow
        >>>
        >>> client = cillow.Client.new()  # Connect as a new client
        >>> # OR
        >>> client = cillow.Client(id="<uid>")  # Connect as an existing client
        >>>
        >>> client.current_environment  # Get environment of selected interpreter
        '$system'
        >>> client.all_environments  # Get environments of all running interpreter processes
        ['$system']
        >>> client.run_code(\"\"\"
        ... from PIL import Image, ImageDraw
        ...
        ... img = Image.new('RGB', (400, 300), 'white')
        ...
        ... draw = ImageDraw.Draw(img)
        ... draw.rectangle([50, 50, 150, 150], fill='blue')
        ... draw.ellipse([200, 50, 300, 150], fill='red')
        ... draw.line([50, 200, 350, 200], fill='green', width=5)
        ...
        ... img.show()
        ... \"\"\")
        >>> client.switch_interpreter("/path/to/python/env")  # Switch to interpreter process with given environment
        >>> client.delete_interpreter("/path/to/python/env")  # Stop interpreter process running in given environment
        >>> client.install_requirements(["pkg-name1", "pkg-name2"])  # Install requirements in the current interpreter process
    """

    def __init__(
        self,
        id: str,  # noqa: A002
        host: str | None = None,
        port: int | None = None,
        environment: PythonEnvironment | str = "$system",
    ) -> None:
        """
        Connect to the server as an existing client.

        Args:
            id: The client id
            host: The host to connect to (defaults to localhost)
            port: The port to connect to (defaults to 5556)
            environment: The default python environment to use (defaults to "$system")
        """
        self._socket = zmq.Context().socket(zmq.DEALER)
        self._socket.identity = id.encode()

        self._url = f"tcp://{host or 'localhost'}:{port or 5556}"
        self._socket.connect(self._url)

        self.__id = id
        self.__timeout: int | None = None
        self.__current_environment: PythonEnvironment | None = None

        self.switch_interpreter(environment)

    @classmethod
    def new(
        cls, host: str | None = None, port: int | None = None, environment: PythonEnvironment | str = "$system"
    ) -> Client:
        """
        Connect to the server as a new client.

        Args:
            host: The host to connect to (defaults to localhost)
            port: The port to connect to (defaults to 5556)
            environment: The default python environment to use (defaults to "$system")
        """
        return cls(id=str(uuid4()), host=host, port=port, environment=environment)

    def __enter__(self) -> Client:
        return self

    @property
    def id(self) -> str:
        """Identifier of the client."""
        return self.__id

    @property
    def timeout(self) -> int | None:
        """Timeout for request in milliseconds."""
        return self.__timeout

    @timeout.setter
    def timeout(self, value: int) -> None:
        self.__timeout = value

    @property
    def current_environment(self) -> PythonEnvironment:
        """Current Python environment"""
        if self.__current_environment is None:
            self.__current_environment = self._get_return_value(GetEnvrionment(environment_type="current"))
        return self.__current_environment

    @property
    def all_environments(self) -> list[PythonEnvironment]:
        """All running Python environments"""
        return self._get_return_value(GetEnvrionment(environment_type="all"))  # type: ignore[no-any-return]

    def _send_request(self, request_dataclass: Any) -> Generator[tuple[bytes, bytes], None, bytes]:
        """
        Send a request to the server and get response generator. This is a blocking operation.

        Args:
            request_dataclass: Dataclass to send as request

        Yields:
            A tuple of message type and body
        """
        self._socket.send_multipart([b"", pickle.dumps(request_dataclass)], flags=zmq.NOBLOCK)
        poller = zmq.Poller()
        poller.register(self._socket, zmq.POLLIN)

        if not poller.poll(self.__timeout):
            raise TimeoutError("Request timed out")

        try:
            while True:
                frames = self._socket.recv_multipart()
                msg_type, body = frames[1], frames[2]
                if msg_type == b"request_done":
                    return body
                if msg_type == b"request_exception":
                    raise Exception(body.decode())
                yield msg_type, body
        finally:
            poller.unregister(self._socket)

    def _get_return_value(self, request_dataclass: Any) -> Any:
        gen = self._send_request(request_dataclass)
        while True:
            try:
                next(gen)
            except StopIteration as e:
                return pickle.loads(e.value)

    def switch_interpreter(self, environment: PythonEnvironment | str) -> None:
        """
        Switch to interpreter associated with the given Python environment.

        Creates a new interpreter process if it doesn't exists.

        Args:
            environment: The Python environment to use
        """
        self.__current_environment = self._get_return_value(ModifyInterpreter(environment=environment, mode="switch"))

    def delete_interpreter(self, environment: PythonEnvironment | str) -> None:
        """
        Delete the interpreter associated with the given Python environment.
        After deletion, the current environment is set to `$system`.

        Args:
            environment: The Python environment to use
        """
        self.__current_environment = self._get_return_value(ModifyInterpreter(environment=environment, mode="delete"))

    def install_requirements(self, requirements: list[str], on_stream: Callable[[Stream], None] | None = None) -> None:
        """
        Install the given requirements in the current Python environment.

        Args:
            requirements: The requirements to install
        """
        on_stream = on_stream or default_stream_processor
        for msg_type, body in self._send_request(InstallRequirements(requirements=requirements)):
            if msg_type != b"interpreter":
                continue

            on_stream(pickle.loads(body))

    def run_code(self, code: str, on_stream: Callable[[Stream | ByteStream], None] | None = None) -> Execution:
        """
        Run the code in the current selected interpreter.

        Args:
            code: The code to run
            on_stream: The callback to capture streaming output.

        Returns:
            The execution result containing the result, streams, byte streams and exception.
        """
        on_stream = on_stream or default_stream_processor
        streams, byte_streams = [], []  # type: ignore[var-annotated]
        for msg_type, body in self._send_request(RunCode(code=code)):
            if msg_type != b"interpreter":
                continue

            response = pickle.loads(body)
            if isinstance(response, Result):
                return Execution(result=response, streams=streams, byte_streams=byte_streams)

            elif isinstance(response, ExceptionInfo):
                return Execution(
                    result=Result(value=None), streams=streams, byte_streams=byte_streams, exception=response
                )

            if isinstance(response, Stream):
                streams.append(response)
            elif isinstance(response, ByteStream):
                byte_streams.append(response)

            on_stream(response)

        return Execution(  # This should never happen
            result=Result(value=None), streams=streams, byte_streams=byte_streams, exception=None
        )

    def disconnect(self) -> None:
        """Close the connection to the server and clean up all the resources being used by the client."""
        for _ in self._send_request(Disconnect()):
            ...
        self._socket.close()
        self._socket.context.term()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.disconnect()
