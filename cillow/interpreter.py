from __future__ import annotations

import os
import sys
from shutil import which as find_executable
from tempfile import NamedTemporaryFile
from traceback import format_tb as format_traceback
from typing import Any, Callable

from . import patch
from .code_meta import CodeMeta
from .importhook import EnvironmentImportHook
from .modutils import MODULE_TO_PACKAGE_MAP, get_installed_modules
from .shell import shell
from .types import ByteStream, ExceptionInfo, PythonEnvironment, Result, Stream

__all__ = ("Interpreter",)


PIP_INSTALL_CMD = ("uv", "pip", "install") if find_executable("uv") else ("pip", "install")


class Interpreter:
    """
    Create an interpreter from a given python environment.

    Examples:
        >>> import cillow
        >>>
        >>> interpreter = cillow.Interpreter()
        >>>
        >>> interpreter.run_code("x = 1; x + 1")
        Result(value=2)
        >>>
        >>> interpreter.install_requirements(["package-name"])

    Don't trust LLMS? Concerned about arbitrary code execution?
    Take full control by limiting functionalities using patches.

    To add patches, use the `add_patches()` function. To clear patches, use `clear_patches()`.

    Examples:
        >>> import cillow
        >>>
        >>> import os
        >>> from contextlib import contextmanager
        >>>
        >>> os_system_switchable = cillow.Switchable(os.system)
        >>>
        >>> @contextmanager
        ... def patch_os_system():
        ...     def disabled_os_system(command: str):
        ...         return "os.system has been disabled."
        ...
        ...     with os_system_switchable.switch_to(disabled_os_system):
        ...         yield
        ...
        >>> cillow.add_patches(patch_os_system)  # Disable os.system
        >>>
        >>> interpreter = cillow.Interpreter()
        >>> interpreter.run_code("import os;os.system('echo Hi')")
        Result(value='os.system has been disabled.')
    """

    def __init__(self, environment: PythonEnvironment = "$system") -> None:
        self.namespace: dict[str, Any] = {}
        self._import_hook = None
        if environment != "$system":
            self._import_hook = EnvironmentImportHook(environment)
            sys.meta_path.insert(0, self._import_hook)
            sys.path.insert(0, str(self._import_hook.site_packages))

    @property
    def environment(self) -> PythonEnvironment:
        """The current Python environment"""
        return getattr(self._import_hook, "environment", "$system")

    # fmt: off
    def run_command(
        self, *cmd: str, on_stream: Callable[[Stream], Any] | None = None
    ) -> None:
        # fmt: on
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
        for line in shell.stream(*cmd):
            on_stream(Stream(type="cmd_exec", data=line))

    # fmt: off
    def install_requirements(
        self, *requirements: str, on_stream: Callable[[Stream], None] | None = None
    ) -> None:
        # fmt: on
        """
        Install the given requirements.

        Args:
            requirements: The requirements to install
            on_stream: The callback to capture streaming output. (defaults to print)
        """
        install_args = []
        if self._import_hook is not None:
            install_args = ["--python", str(self._import_hook.environment)]

        with NamedTemporaryFile(mode="w") as handler:
            # Writing requirements to file, instead of directly
            # passing them as arguments, to avoid arbitrary command execution
            handler.write("\n".join(requirements))
            handler.flush()
            install_args.extend(["-r", handler.name])

            self.run_command(*PIP_INSTALL_CMD, *install_args, on_stream=on_stream)

    def run_code(
        self, code: str, on_stream: Callable[[Stream | ByteStream], None] | None = None
    ) -> Result | ExceptionInfo:
        """
        Run the given code.

        Args:
            code: The code to run
            on_stream: The callback to capture streaming output.

        Returns:
            Result or ExceptionInfo dataclass instance
        """
        try:
            code_meta = CodeMeta.from_code(code, filename="interpreter-process")
        except Exception as exc:
            return ExceptionInfo(type=exc.__class__.__name__, message=str(exc))

        on_stream = on_stream or default_stream_processor
        if not is_auto_install_disabled() and (module_names := code_meta.module_names):
            to_install = (module_names - sys.stdlib_module_names) - get_installed_modules()
            if to_install:
                packages = [MODULE_TO_PACKAGE_MAP.get(name, name) for name in to_install]
                self.install_requirements(*packages, on_stream=on_stream)

        try:
            with patch.load_patches(on_stream=on_stream):
                if to_exec := code_meta.to_exec:
                    exec(to_exec, self.namespace, self.namespace)  # noqa: S102

                result_value = None
                if to_eval := code_meta.to_eval:
                    result_value = eval(to_eval, self.namespace, self.namespace)  # noqa: S307

            return Result(value=result_value)

        except Exception as exc:
            exc_info = {
                "type": exc.__class__.__name__,
                "message": str(exc),
            }
            if tb := exc.__traceback__:
                exc_info["where"] = format_traceback(tb)[-1].strip()

            return ExceptionInfo(**exc_info)

    def __del__(self) -> None:
        if self._import_hook:
            sys.meta_path.pop(0)
            sys.path.pop(0)


def is_auto_install_disabled() -> bool:
    """Check if auto-install is disabled."""
    return os.environ.get("CILLOW_DISABLE_AUTO_INSTALL", "").lower() in ("1", "true", "yes")


def is_running_in_jupyter() -> bool:
    """Check if the interpreter is running in a Jupyter notebook"""
    try:
        shell = get_ipython().__class__.__name__  # type: ignore[name-defined]
        return shell == "ZMQInteractiveShell"  # type: ignore[no-any-return]
    except NameError:
        return False


def default_stream_processor(stream: Stream | ByteStream) -> None:
    """Interpreter's default stream processor."""
    if isinstance(stream, Stream):
        if stream.type == "stdout":
            original = patch.prebuilt.stdout_write_switchable.original
            prefix = "[STDOUT] "
        elif stream.type == "stderr":
            original = patch.prebuilt.stderr_write_switchable.original
            prefix = "[STDERR] "
        else:
            original = patch.prebuilt.stdout_write_switchable.original
            prefix = "[SHELL] "

        data = f"{prefix}{stream.data}" if stream.data.strip() else stream.data
        original(data)
        return

    if stream.type == "image":
        if is_running_in_jupyter():
            # Render the image in the Jupyter notebook output cell
            from IPython.display import Image, display  # type: ignore[unused-ignore,import-not-found]

            display(Image(data=stream.data))
        else:
            # Open the image in the default image viewer
            from io import BytesIO

            from PIL.Image import open as pil_open

            patch.prebuilt.pillow_show_switchable.original(pil_open(BytesIO(stream.data)))
