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
    GetPythonEnvironment,
    InstallRequirements,
    ModifyInterpreter,
    PythonEnvironment,
    Result,
    RunCode,
    RunCommand,
    SetEnvironmentVariables,
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
        >>> # Switch to interpreter process with given environment
        >>> client.switch_interpreter("/path/to/python/env")
        >>> # Stop interpreter process running in given environment
        >>> client.delete_interpreter("/path/to/python/env")
        >>> # Install requirements in the current selected environment
        >>> client.install_requirements("pkg-name1", "pkg-name2")
        >>> # Run commands
        >>> client.run_command("echo", "Hello World")
        >>> # Set environment variables
        >>> client.set_environment_variables({"VAR1": "value1", "VAR2": "value2"})
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
        self.__default_environment: PythonEnvironment | None = None

        self.switch_interpreter(environment)

    # fmt: off
    @classmethod
    def new(
        cls,
        host: str | None = None,
        port: int | None = None,
        environment: PythonEnvironment | str = "$system"
    ) -> Client:
        # fmt: on
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
        """Client's identifier."""
        return self.__id

    @property
    def request_timeout(self) -> int | None:
        """Timeout for request in milliseconds."""
        return self.__timeout

    @request_timeout.setter
    def request_timeout(self, value: int) -> None:
        self.__timeout = value

    @property
    def default_environment(self) -> PythonEnvironment:
        """Default Python environment."""
        if self.__default_environment is None:
            self.__default_environment = self._get_return_value(GetPythonEnvironment(type="default"))
        return self.__default_environment

    @property
    def current_environment(self) -> PythonEnvironment:
        """Current interpreter's python environment."""
        if self.__current_environment is None:
            self.__current_environment = self._get_return_value(GetPythonEnvironment(type="current"))
        return self.__current_environment

    @property
    def all_environments(self) -> list[PythonEnvironment]:
        """All running interpreter's python environments."""
        return self._get_return_value(GetPythonEnvironment(type="all"))  # type: ignore[no-any-return]

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
        Switch to specified python environment's interpreter process.

        Creates a new interpreter process if it is not already running.

        Args:
            environment: The Python environment to use
        """
        self.__current_environment = self._get_return_value(ModifyInterpreter(environment, mode="switch"))

    def delete_interpreter(self, environment: PythonEnvironment | str) -> None:
        """
        Stop the specified python environment's interpreter process.

        Switches to default python environment's  interpreter process.

        Args:
            environment: The Python environment to use
        """
        self.__current_environment = self._get_return_value(ModifyInterpreter(environment, mode="delete"))

    def set_environment_variables(self, environment_variables: dict[str, str]) -> None:
        """
        Set environment variables for the current interpreter.

        Args:
            environment_variables: The environment variables to set
        """
        for _ in self._send_request(SetEnvironmentVariables(environment_variables)):
            ...

    def run_command(self, *cmd: str, on_stream: Callable[[Stream], None] | None = None) -> None:
        """
        Run the given command.

        ⚠️ WARNING: This class allows execution of system commands and should be used with EXTREME CAUTION.

        - Never run commands with user-supplied or untrusted input
        - Always validate and sanitize any command arguments
        - Be aware of potential security risks, especially with privilege escalation

        Args:
            cmd: The command to run
            on_stream: The callback to capture streaming output.
        """
        on_stream = on_stream or default_stream_processor
        for msg_type, body in self._send_request(RunCommand(cmd=cmd)):
            if msg_type != b"interpreter":
                continue

            on_stream(pickle.loads(body))

    # fmt: off
    def install_requirements(
        self, *requirements: str, on_stream: Callable[[Stream], None] | None = None
    ) -> None:
        # fmt: on
        """
        Install the given requirements in the current Python environment.

        Args:
            requirements: The requirements to install
        """
        on_stream = on_stream or default_stream_processor
        for msg_type, body in self._send_request(InstallRequirements(requirements)):
            if msg_type != b"interpreter":
                continue

            on_stream(pickle.loads(body))

    # fmt: off
    def run_code(
        self,
        code: str,
        on_stream: Callable[[Stream | ByteStream], None] | None = None
    ) -> Execution:
        # fmt: on
        """
        Run the code in the current selected interpreter.

        Args:
            code: The code to run
            on_stream: The callback to capture streaming output.

        Returns:
            The execution result containing the result, streams, byte streams and exception.
        """
        on_stream = on_stream or default_stream_processor
        result, streams, byte_streams, exception = Result(value=None), [], [], None
        for msg_type, body in self._send_request(RunCode(code=code)):
            if msg_type != b"interpreter":
                continue

            response = pickle.loads(body)
            if isinstance(response, Result):
                result = response
                continue
            elif isinstance(response, ExceptionInfo):
                exception = response
                continue

            if isinstance(response, Stream):
                streams.append(response)
            elif isinstance(response, ByteStream):
                byte_streams.append(response)

            on_stream(response)

        return Execution(
            result=result, streams=streams, byte_streams=byte_streams, exception=exception
        )

    def disconnect(self) -> None:
        """
        Close the connection to the server and remove the client.

        Don't use this if you want to reconnect to the server later.
        """
        for _ in self._send_request(Disconnect()):
            ...

        self._socket.close()
        self._socket.context.term()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.disconnect()
