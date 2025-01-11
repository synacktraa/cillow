from __future__ import annotations

from importlib.machinery import ModuleSpec
from importlib.util import spec_from_file_location
from pathlib import Path

from .types import PythonEnvironment

__all__ = "EnvironmentImportHook", "validate_environment"


def validate_environment(environment: PythonEnvironment | str) -> PythonEnvironment:
    """
    Validate the given environment.

    Args:
        environment: The environment to validate

    Raises:
        LookupError: If the environment is invalid or not found

    Returns:
        The validated environment value
    """
    if environment != "$system":
        environment = Path(environment).expanduser().resolve()
        if not (environment / "lib" / "site-packages").is_dir():
            raise LookupError(f"Python environment {str(environment)!r} is invalid or not found.")

    return environment


class EnvironmentImportHook:
    """
    Custom import hook to allow importing modules from another Python environment.

    Examples:
        >>> import sys
        >>>
        >>> hook = EnvironmentImportHook("/path/to/python/env")
        >>> sys.meta_path.insert(0, hook)
        >>> sys.path.insert(0, hook.site_packages)
    """

    def __init__(self, environment: str | Path) -> None:
        """
        Environment import hook instance.

        Args:
            environment: Path to the Python environment
        """
        environment = Path(environment).expanduser().resolve()
        site_packages = environment / "lib" / "site-packages"
        if not site_packages.is_dir():
            raise NotADirectoryError(f"Python environment {str(environment)!r} is invalid or not found.")

        self._environment = environment
        self._site_packages = site_packages

    @property
    def environment(self) -> Path:
        """The environment path"""
        return self._environment

    @property
    def site_packages(self) -> Path:
        """The site-packages path in the environment"""
        return self._site_packages

    def find_spec(self, fullname: str, path=None, target=None) -> ModuleSpec | None:  # type: ignore[no-untyped-def]
        """
        Find the module spec for the given module name.

        Args:
            fullname: Fully qualified module name

        Returns:
            ModuleSpec object or None if the module is not found
        """
        package = self._site_packages.joinpath(*fullname.split("."))

        # Check for package directory with __init__.py
        init_file = package / "__init__.py"
        if package.is_dir() and init_file.is_file():
            return spec_from_file_location(fullname, init_file)

        # Check for single source file
        src_file = package.with_suffix(".py")
        if src_file.is_file():
            return spec_from_file_location(fullname, src_file)

        return None
