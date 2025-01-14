import os
import sys
from contextlib import contextmanager
from unittest.mock import Mock, call, patch

import pytest

from cillow import Interpreter, Switchable, add_patches, clear_patches
from cillow.types import Result, Stream


@pytest.fixture
def interpreter():
    """Fixture providing a clean interpreter instance"""
    return Interpreter()


@pytest.fixture
def tmp_env_path(tmp_path):
    """Create a temporary valid Python environment structure"""
    site_packages = tmp_path / "lib" / "site-packages"
    site_packages.mkdir(parents=True)
    return tmp_path


@pytest.fixture(autouse=True)
def cleanup():
    """Cleanup patches after each test"""
    yield
    clear_patches()


def test_interpreter_initialization(tmp_env_path):
    """Test interpreter initialization with different environments"""
    sys_interpreter = Interpreter()
    assert sys_interpreter.environment == "$system"
    assert sys_interpreter.namespace == {}

    env_interpreter = Interpreter(environment=tmp_env_path)
    assert env_interpreter.environment == tmp_env_path
    assert env_interpreter._import_hook is not None

    env_interpreter.__del__()


def test_interpreter_run_command(interpreter):
    """Test command execution functionality"""

    def on_stream(stream):
        assert isinstance(stream, Stream)
        assert stream.type == "cmd_exec"
        assert "hello" in stream.data or "world" in stream.data

    interpreter.run_command("echo", "hello world", on_stream=on_stream)


def test_code_safety_with_patch(interpreter):
    """Test that dangerous operations are properly handled using cillow patches"""
    os_system_switchable = Switchable(os.system)

    @contextmanager
    def patch_os_system():
        def disabled_os_system(command: str):
            return "os.system has been disabled."

        with os_system_switchable.switch_to(disabled_os_system):
            yield

    add_patches(patch_os_system)

    test_codes = [
        "import os\nos.system('rm -rf /')",
        "import os\nos.system('echo dangerous')",
        "__import__('os').system('rm -rf /')",
    ]

    for code in test_codes:
        result = interpreter.run_code(code)
        assert isinstance(result, Result)
        assert result.value == "os.system has been disabled."


@patch("cillow.interpreter.shell.stream")
def test_install_requirements(mock_stream, interpreter):
    """Test package installation functionality"""
    mock_stream.return_value = ["Installing...", "Successfully installed"]
    mock_callback = Mock()

    interpreter.install_requirements("requests", on_stream=mock_callback)

    mock_stream.assert_called_once()
    args = mock_stream.call_args[0]
    assert "pip" in args[0] or "uv" in args[0]

    mock_callback.assert_has_calls([
        call(Stream(type="cmd_exec", data="Installing...")),
        call(Stream(type="cmd_exec", data="Successfully installed")),
    ])


@patch("cillow.interpreter.shell.stream")
def test_install_requirements_with_custom_python_env(mock_stream, tmp_env_path):
    """Test package installation in custom python environment"""
    mock_stream.return_value = ["Installing..."]
    interpreter = Interpreter(environment=tmp_env_path)

    interpreter.install_requirements("requests")

    install_cmd = mock_stream.call_args[0]
    assert "--python" in install_cmd
    assert str(tmp_env_path) in install_cmd


def test_cleanup(tmp_env_path):
    """Test proper cleanup when interpreter is destroyed"""
    interpreter = Interpreter(environment=tmp_env_path)
    original_meta_path_len = len(sys.meta_path)
    original_path_len = len(sys.path)

    interpreter.__del__()

    assert len(sys.meta_path) == original_meta_path_len - 1
    assert len(sys.path) == original_path_len - 1
