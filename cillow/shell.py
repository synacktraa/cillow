from __future__ import annotations

import os
import subprocess
from collections.abc import Generator
from pathlib import Path, PurePath
from typing import Any, cast

__all__ = ("Shell",)


class Shell:
    """
    Interface for running commands.

    If os is windows, all commands are executed using `PowerShell`.

    ⚠️ WARNING: This class allows execution of system commands and should be used with EXTREME CAUTION.

    - Never run commands with user-supplied or untrusted input
    - Always validate and sanitize any command arguments
    - Be aware of potential security risks, especially with privilege escalation

    Examples:
        >>> # Initialize the shell
        >>> shell = Shell(workdir="/path/to/directory")
        >>>
        >>> shell.run("echo", "'Hello from shell!'")
        Hello from shell!
        >>>
        >>> for line in shell.stream("echo", "Hello from shell!"):
        ...     print(line)
        Hello
        from
        shell!
    """

    def __init__(self, *, workdir: str | Path | None = None) -> None:
        """
        Initialize the CommandExecutor.

        Args:
            workdir: The working directory to execute commands in
        """
        if workdir:
            w_dir = Path(workdir)
            if not w_dir.is_dir():
                raise NotADirectoryError(f"{str(w_dir)!r} is not a directory.")
            self.__workdir = PurePath(w_dir)
        else:
            self.__workdir = PurePath(Path.cwd())

    @staticmethod
    def __validate_cmd(cmd: tuple[str, ...]) -> tuple[str, ...]:
        if os.name == "nt" and "SHELL" not in os.environ:
            return ("powershell", "-NoProfile", "-NonInteractive", "-Command", *cmd)
        return cmd

    @property
    def workdir(self) -> PurePath:
        """The working directory."""
        return self.__workdir

    def __prepare_common_kwargs(self, env: dict[str, str] | None = None) -> dict[str, Any]:
        kwargs = {"cwd": self.__workdir, "text": True}
        if env:
            kwargs["env"] = {**os.environ, **env}
        return kwargs

    def run(self, *cmd: str, env: dict[str, str] | None = None) -> str:
        """
        Run a command and return the output.

        Args:
            cmd: The arguments to pass as command
            env: Environment variables to set

        Returns:
            Output of the executed command
        """
        process = cast(
            subprocess.CompletedProcess[str],
            subprocess.run(self.__validate_cmd(cmd), capture_output=True, **self.__prepare_common_kwargs(env)),  # noqa: S603
        )
        string = ""
        if error := process.stderr.strip():
            string += error

        if output := process.stdout.strip():
            string += output

        return string

    def stream(self, *cmd: str, env: dict[str, str] | None = None) -> Generator[str, Any, None]:
        """
        Run a command and stream the output.

        Args:
            cmd: The arguments to pass as command
            env: Environment variables to set

        Returns:
            Output stream of the executed command
        """
        process = subprocess.Popen(  # noqa: S603
            self.__validate_cmd(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **self.__prepare_common_kwargs(env),
        )

        if error := process.stderr:
            yield from error

        if output := process.stdout:
            yield from output


shell = Shell()
