from unittest.mock import MagicMock, patch

import pytest

from cillow.interpreter import ExceptionInfo, Stream
from cillow.server._process import _completed, _InterpreterProcess


@pytest.fixture
def global_interpreter_process():
    with patch("multiprocessing.Process") as MockProcess:
        # Mock the Process and simulate the behavior
        mock_process = MagicMock()
        MockProcess.return_value = mock_process

        # Mock behavior of the process (is_alive, start, etc.)
        mock_process.is_alive.return_value = True

        # Initialize _InterpreterProcess with the mock
        _process = _InterpreterProcess("$system")
        yield _process
        _process.stop()


@pytest.fixture
def non_global_interpreter_process(tmp_path_factory):
    with patch("multiprocessing.Process") as MockProcess:
        # Mock the Process for the non-global interpreter
        mock_process = MagicMock()
        MockProcess.return_value = mock_process

        # Mock behavior of the process (is_alive, start, etc.)
        mock_process.is_alive.return_value = True

        tmp_path = tmp_path_factory.mktemp("interpreter_session")
        (tmp_path / "lib" / "site-packages").mkdir(parents=True)
        _process = _InterpreterProcess(tmp_path)
        yield _process
        _process.stop()


def test_global_interpreter_process(global_interpreter_process):
    assert global_interpreter_process._process.is_alive()
    assert not global_interpreter_process._process_event.is_set()


def test_non_global_interpreter_process(non_global_interpreter_process):
    assert non_global_interpreter_process._process.is_alive()
    assert not non_global_interpreter_process._process_event.is_set()


def test_run_code(global_interpreter_process):
    test_code = "print('hello')"
    expected_output = Stream(type="stdout", data="hello")

    # Mock the queue behavior
    global_interpreter_process._output_queue.put(expected_output)
    global_interpreter_process._output_queue.put(_completed)

    outputs = list(global_interpreter_process._send_input(code=test_code))
    assert outputs == [expected_output]


def test_run_code_with_exception(global_interpreter_process):
    test_code = "raise ValueError('test error')"
    expected_output = ExceptionInfo(type="ValueError", message="test error", where="test_location")

    global_interpreter_process._output_queue.put(expected_output)
    global_interpreter_process._output_queue.put(_completed)

    outputs = list(global_interpreter_process._send_input(code=test_code))
    assert outputs == [expected_output]


def test_run_command(global_interpreter_process):
    test_command = ("pip", "install", "package")
    expected_output = Stream(type="cmd_exec", data="Successfully installed package")

    global_interpreter_process._output_queue.put(expected_output)
    global_interpreter_process._output_queue.put(_completed)

    outputs = list(global_interpreter_process._send_input(command=test_command))
    assert outputs == [expected_output]


def test_install_requirements(global_interpreter_process):
    requirements = ["numpy", "pandas"]
    expected_output = Stream(type="cmd_exec", data="Installing packages...")

    global_interpreter_process._output_queue.put(expected_output)
    global_interpreter_process._output_queue.put(_completed)

    outputs = list(global_interpreter_process._send_input(requirements=requirements))
    assert outputs == [expected_output]


def test_set_environment_variables(global_interpreter_process):
    env_vars = {"TEST_VAR": "test_value"}

    global_interpreter_process._output_queue.put(_completed)
    outputs = list(global_interpreter_process._send_input(environment_variables=env_vars))

    assert outputs == []


@pytest.mark.timeout(3)  # Ensure test doesn't hang
def test_empty_queue_timeout(global_interpreter_process):
    # Test handling of EmptyQueueError
    outputs = []
    global_interpreter_process._output_queue.put(_completed)

    for output in global_interpreter_process._send_input(code="print('test')"):
        outputs.append(output)

    assert outputs == []
