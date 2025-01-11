import os
from pathlib import Path, PurePath
from unittest.mock import MagicMock, patch

import pytest

from cillow.shell import Shell


@pytest.fixture
def temp_workdir(tmp_path):
    """Create a temporary working directory"""
    return tmp_path


@pytest.fixture
def shell(temp_workdir):
    """Create a Shell instance with temporary working directory"""
    return Shell(workdir=temp_workdir)


def test_shell_init_default():
    """Test Shell initialization with default working directory"""
    shell = Shell()
    assert shell.workdir == PurePath(Path.cwd())


def test_shell_init_with_workdir(temp_workdir):
    """Test Shell initialization with specific working directory"""
    shell = Shell(workdir=temp_workdir)
    assert shell.workdir == PurePath(temp_workdir)


def test_shell_init_invalid_workdir():
    """Test Shell initialization with non-existent directory"""
    with pytest.raises(NotADirectoryError):
        Shell(workdir="/nonexistent/directory")


@patch("subprocess.run")
def test_run_basic_command(mock_run, shell):
    """Test basic command execution"""
    mock_process = MagicMock()
    mock_process.stdout = "command output"
    mock_process.stderr = ""
    mock_run.return_value = mock_process

    result = shell.run("echo", "test")
    assert result == "command output"
    mock_run.assert_called_once()


@patch("subprocess.run")
def test_run_command_with_error(mock_run, shell):
    """Test command execution with error output"""
    mock_process = MagicMock()
    mock_process.stdout = "standard output"
    mock_process.stderr = "error output"
    mock_run.return_value = mock_process

    result = shell.run("invalid_command")
    assert "error output" in result
    assert "standard output" in result


@patch("subprocess.Popen")
def test_stream_command(mock_popen, shell):
    """Test streaming command execution"""
    mock_process = MagicMock()
    mock_process.stdout = ["line1\n", "line2\n"]
    mock_process.stderr = []
    mock_popen.return_value = mock_process

    lines = list(shell.stream("echo", "test"))
    assert lines == ["line1\n", "line2\n"]
    mock_popen.assert_called_once()


@patch("subprocess.Popen")
def test_stream_command_with_error(mock_popen, shell):
    """Test streaming command with error output"""
    mock_process = MagicMock()
    mock_process.stdout = ["output1\n"]
    mock_process.stderr = ["error1\n"]
    mock_popen.return_value = mock_process

    lines = list(shell.stream("invalid_command"))
    assert "error1\n" in lines
    assert "output1\n" in lines


@patch("subprocess.run")
def test_run_with_env_vars(mock_run, shell):
    """Test command execution with environment variables"""
    mock_process = MagicMock()
    mock_process.stdout = "output"
    mock_process.stderr = ""
    mock_run.return_value = mock_process

    env = {"TEST_VAR": "test_value"}
    shell.run("echo", "test", env=env)

    called_kwargs = mock_run.call_args[1]
    assert "env" in called_kwargs
    assert called_kwargs["env"]["TEST_VAR"] == "test_value"
    assert all(key in called_kwargs["env"] for key in os.environ)


@pytest.mark.skipif(os.name != "nt", reason="Windows-specific test")
def test_windows_powershell_command(shell):
    """Test PowerShell command formatting on Windows"""
    with patch("subprocess.run") as mock_run:
        mock_process = MagicMock()
        mock_process.stdout = "output"
        mock_process.stderr = ""
        mock_run.return_value = mock_process

        shell.run("echo", "test")

        called_args = mock_run.call_args[0][0]
        assert called_args[0] == "powershell"
        assert "-NoProfile" in called_args
        assert "-NonInteractive" in called_args
        assert "-Command" in called_args


@pytest.mark.skipif(os.name == "nt", reason="Unix-specific test")
def test_unix_command_execution(shell):
    """Test direct command execution on Unix systems"""
    with patch("subprocess.run") as mock_run:
        mock_process = MagicMock()
        mock_process.stdout = "output"
        mock_process.stderr = ""
        mock_run.return_value = mock_process

        shell.run("echo", "test")

        called_args = mock_run.call_args[0][0]
        assert called_args == ("echo", "test")


def test_real_echo_command(shell):
    """Test actual echo command execution"""
    result = shell.run("echo", "test")
    assert "test" in result.lower()


def test_real_directory_listing(shell, temp_workdir):
    """Test actual directory listing command"""
    test_file = temp_workdir / "test.txt"
    test_file.touch()

    result = shell.run("dir") if os.name == "nt" else shell.run("ls")
    assert "test.txt" in result


def test_workdir_command_execution(shell, temp_workdir):
    """Test command execution in specified working directory"""
    test_file = temp_workdir / "unique_test_file.txt"
    test_file.touch()

    result = shell.run("dir") if os.name == "nt" else shell.run("ls")
    assert "unique_test_file.txt" in result


def test_stream_large_output(shell):
    """Test streaming of large command output"""
    if os.name == "nt":  # noqa: SIM108
        cmd = ("powershell", "-Command", "1..5 | ForEach-Object { echo $_ }")
    else:
        cmd = ("seq", "1", "5")

    lines = list(shell.stream(*cmd))
    assert len(lines) == 5


@pytest.mark.asyncio
async def test_stream_concurrent_usage(shell):
    """Test concurrent usage of stream method"""
    import asyncio

    async def stream_command():
        return list(shell.stream("echo", "test"))

    tasks = [stream_command() for _ in range(3)]
    results = await asyncio.gather(*tasks)

    assert all(len(result) > 0 for result in results)
