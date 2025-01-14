from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cillow.server.client_manager import ClientManager


@pytest.fixture(scope="module")
def client_manager():
    """Fixture for initializing the ClientManager."""
    with patch("cillow.server.client_manager._InterpreterProcess") as MockInterpreterProcess:
        mock_interpreter = MagicMock()
        MockInterpreterProcess.return_value = mock_interpreter
        client_manager = ClientManager(max_interpreters=4, interpreters_per_client=2)
        yield client_manager
        client_manager.cleanup()


@pytest.fixture
def fake_env(tmp_path):
    """Fixture for creating a fake Python environment."""
    env_path = tmp_path / "fake_env"
    site_packages = env_path / "lib" / "site-packages"
    site_packages.mkdir(parents=True)
    return str(env_path)


def test_optimal_number_of_request_workers(client_manager):
    """Test optimal number of request workers."""
    assert client_manager.optimal_number_of_request_workers == min(
        2 * client_manager.max_clients, client_manager.cpu_count
    )


def test_optimal_max_queue_size(client_manager):
    """Test optimal maximum queue size."""
    assert (
        client_manager.optimal_max_queue_size == client_manager.max_clients * client_manager.interpreters_per_client * 2
    )


def test_register_client(client_manager, fake_env):
    """Test registering a client."""
    client_id = "client_1"
    client_manager.register(client_id, environment=fake_env)

    assert client_id in client_manager._clients
    client_info = client_manager._clients[client_id]
    assert client_info.default_environment == Path(fake_env).resolve()


def test_register_client_exceeds_limit(client_manager, fake_env):
    """Test registering more clients than allowed."""
    client_manager.register("client_2", environment=fake_env)

    with pytest.raises(Exception, match="Client limit exceeded"):
        client_manager.register("client_3", environment=fake_env)


def test_switch_interpreter(client_manager, fake_env):
    """Test switching interpreters."""
    client_id = "client_1"

    new_environment = client_manager.switch_interpreter(client_id, environment=fake_env)
    assert new_environment == Path(fake_env).resolve()

    client_info = client_manager._clients[client_id]
    assert client_info.current.environment == Path(fake_env).resolve()


def test_switch_interpreter_exceeds_limit(client_manager, fake_env):
    """Test switching interpreters exceeding process limits."""
    client_id = "client_1"
    with pytest.raises(Exception, match="Unable to create new interpreter due to process limit"):
        client_manager.switch_interpreter(client_id, environment=fake_env)


def test_delete_interpreter(client_manager):
    """Test deleting an interpreter."""
    client_id = "client_1"
    current_env = client_manager.get_info(client_id).current.environment

    client_manager.delete_interpreter(client_id, environment=current_env)

    assert current_env not in client_manager.get_info(client_id).interpreters


def test_remove_client(client_manager):
    """Test removing a client."""
    client_id = "client_1"
    client_manager.remove(client_id)

    assert client_id not in client_manager._clients
