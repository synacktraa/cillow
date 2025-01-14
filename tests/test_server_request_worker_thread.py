import pickle
from pathlib import Path
from queue import Queue
from threading import Event
from unittest.mock import MagicMock

import pytest

from cillow.server.client_manager import ClientManager
from cillow.server.request_worker import RequestWorker
from cillow.types import (
    GetPythonEnvironment,
    InstallRequirements,
    ModifyInterpreter,
    RunCode,
    RunCommand,
    SetEnvironmentVariables,
)


@pytest.fixture
def mock_client_manager():
    """Fixture for mocking the ClientManager."""
    mock_manager = MagicMock(ClientManager)
    mock_manager.get_info.return_value = None
    return mock_manager


@pytest.fixture
def mock_interpreter_process():
    """Fixture for mocking _InterpreterProcess."""
    mock_interpreter = MagicMock()
    mock_interpreter._send_input.return_value = []  # Mock return value of _send_input
    return mock_interpreter


@pytest.fixture
def worker(mock_client_manager):
    """Fixture for initializing the RequestWorker."""
    queue = Queue()
    stop_event = Event()
    callback = MagicMock()
    worker = RequestWorker(queue=queue, client_manager=mock_client_manager, callback=callback, stop_event=stop_event)
    yield worker
    stop_event.set()  # Stop the worker after the test


def test_get_python_environment(mock_client_manager, worker):
    """Test the _get_python_environment method for 'current' environment."""
    client_id = b"client_1"
    mock_client_manager.get_info.return_value = MagicMock(current=MagicMock(environment=Path("/path/to/env")))
    request = GetPythonEnvironment(type="current")

    # Run the worker logic
    worker._get_python_environment(client_id, request.type)

    # Ensure callback is called with expected arguments
    worker._callback.assert_called_once_with(client_id, b"request_done", pickle.dumps(Path("/path/to/env")))


def test_modify_interpreter_switch(mock_client_manager, worker):
    """Test the _modify_interpreter method with 'switch' mode."""
    client_id = b"client_1"
    mock_client_manager.switch_interpreter.return_value = Path("/path/to/new_env")
    request = ModifyInterpreter(environment=Path("/path/to/new_env"), mode="switch")

    # Run the worker logic
    worker._modify_interpreter(client_id, request.environment, request.mode)

    # Ensure callback is called with expected arguments
    worker._callback.assert_called_once_with(client_id, b"request_done", pickle.dumps(Path("/path/to/new_env")))


def test_modify_interpreter_delete(mock_client_manager, worker):
    """Test the _modify_interpreter method with 'delete' mode."""
    client_id = b"client_1"
    mock_client_manager.delete_interpreter.return_value = None
    mock_client_manager.get_info.return_value = MagicMock(default_environment=Path("/path/to/default"))
    mock_client_manager.switch_interpreter.return_value = Path("/path/to/default")

    request = ModifyInterpreter(environment=Path("/path/to/env"), mode="delete")

    # Run the worker logic
    worker._modify_interpreter(client_id, request.environment, request.mode)

    # Ensure callback is called with expected arguments
    worker._callback.assert_called_with(client_id, b"request_done", pickle.dumps(Path("/path/to/default")))


def test_set_environment_variables(mock_client_manager, worker, mock_interpreter_process):
    """Test the _send_input_to_interpreter method for setting environment variables."""
    client_id = b"client_1"
    mock_client_manager.get_info.return_value = MagicMock(current=MagicMock(interpreter=mock_interpreter_process))

    env_vars = {"VAR1": "value1", "VAR2": "value2"}
    request = SetEnvironmentVariables(environment_variables=env_vars)

    # Run the worker logic
    worker._send_input_to_interpreter(client_id, **request.__dict__)

    # Ensure _send_input is called with correct arguments
    mock_interpreter_process._send_input.assert_called_once_with(environment_variables=env_vars)


def test_run_command(mock_client_manager, worker, mock_interpreter_process):
    """Test the _send_input_to_interpreter method for running commands."""
    client_id = b"client_1"
    mock_client_manager.get_info.return_value = MagicMock(current=MagicMock(interpreter=mock_interpreter_process))

    cmd = ("echo", "Hello World")
    request = RunCommand(cmd=cmd)

    # Run the worker logic
    worker._send_input_to_interpreter(client_id, **request.__dict__)

    # Ensure _send_input is called with correct arguments
    mock_interpreter_process._send_input.assert_called_once_with(cmd=cmd)


def test_run_code(mock_client_manager, worker, mock_interpreter_process):
    """Test the _send_input_to_interpreter method for running code."""
    client_id = b"client_1"
    mock_client_manager.get_info.return_value = MagicMock(current=MagicMock(interpreter=mock_interpreter_process))

    code = "print('Hello World')"
    request = RunCode(code=code)

    # Run the worker logic
    worker._send_input_to_interpreter(client_id, **request.__dict__)

    # Ensure _send_input is called with correct arguments
    mock_interpreter_process._send_input.assert_called_once_with(code=code)


def test_install_requirements(mock_client_manager, worker, mock_interpreter_process):
    """Test the _send_input_to_interpreter method for installing requirements."""
    client_id = b"client_1"
    mock_client_manager.get_info.return_value = MagicMock(current=MagicMock(interpreter=mock_interpreter_process))

    requirements = ("cillow", "pillow")
    request = InstallRequirements(requirements=requirements)

    # Run the worker logic
    worker._send_input_to_interpreter(client_id, **request.__dict__)

    # Ensure _send_input is called with correct arguments
    mock_interpreter_process._send_input.assert_called_once_with(requirements=requirements)
