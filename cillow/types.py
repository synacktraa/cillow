from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

PythonEnvironment = Literal["$system"] | Path
"""Python environment type - either `$system` or a path to a python environment"""

# -----Request Types-----


@dataclass(frozen=True)
class GetPythonEnvironment:
    """Get python environment request type"""

    type: Literal["all", "current", "default"]

    def __post_init__(self) -> None:
        if not isinstance(self.type, str):
            raise TypeError("Environment type must be a string")

        if self.type not in ["all", "current", "default"]:
            raise ValueError("Environment type must be 'all', 'current' or 'default'")


@dataclass(frozen=True)
class ModifyInterpreter:
    """Modify interpreter request type"""

    environment: PythonEnvironment | str
    mode: Literal["switch", "delete"]

    def __post_init__(self) -> None:
        if not isinstance(self.environment, (str, Path)):
            raise TypeError("environment must be a string or Path")

        if not isinstance(self.mode, str):
            raise TypeError("mode must be a string")

        if self.mode not in ["switch", "delete"]:
            raise ValueError("mode must be 'switch' or 'delete'")


@dataclass(frozen=True)
class SetEnvironmentVariables:
    """Set environment variables request type"""

    environment_variables: dict[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.environment_variables, dict):
            raise TypeError("environment_variables must be a dictionary")

        if not all(isinstance(k, str) and isinstance(v, str) for k, v in self.environment_variables.items()):
            raise TypeError("environment_variables must be a dictionary of strings")


@dataclass(frozen=True)
class RunCommand:
    """Run command request type"""

    cmd: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.cmd, tuple):
            raise TypeError("cmd must be a tuple")

        if not all(isinstance(c, str) for c in self.cmd):
            raise TypeError("cmd must be a tuple of strings")


@dataclass(frozen=True)
class InstallRequirements:
    """Install requirements request type"""

    requirements: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.requirements, tuple):
            raise TypeError("requirements must be a tuple")

        if not all(isinstance(r, str) for r in self.requirements):
            raise TypeError("requirements must be a tuple of strings")


@dataclass(frozen=True)
class RunCode:
    """Run code request type"""

    code: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, str):
            raise TypeError("code must be a string")


@dataclass(frozen=True)
class Disconnect:
    """Disconnect request type"""


# -----Response Types-----


@dataclass(frozen=True)
class Stream:
    """Stream response type generated during code or command execution"""

    type: Literal["stdout", "stderr", "cmd_exec"]
    """The stream type"""
    data: str
    """The stream data"""


@dataclass(frozen=True)
class ByteStream:
    """Byte stream response type generated during code execution"""

    type: Literal["image", "audio", "video"]
    """The byte stream type"""
    data: bytes
    """The byte stream data"""
    id: str | None = field(default=None)
    """Identifier if stream data is of audio or video type"""


@dataclass(frozen=True)
class ExceptionInfo:
    """Exception information response type generated during code execution"""

    type: str
    """Exception type"""
    message: str
    """Exception message"""
    where: str | None = field(default=None)
    """Where the exception occurred"""

    def __str__(self) -> str:
        string = f"{self.type}: {self.message}"
        if self.where:
            string += f"\n{self.where}"
        return string


@dataclass(frozen=True)
class Result:
    """Result response type generated during code execution"""

    value: Any
    """The result value"""


@dataclass(frozen=True)
class Execution:
    """Final execution response type returned by the the client's run_code method"""

    result: Result
    streams: list[Stream]
    byte_streams: list[ByteStream]
    exception: ExceptionInfo | None = field(default=None)
