import sys
from importlib.machinery import ModuleSpec
from textwrap import dedent

import pytest

from cillow.importhook import EnvironmentImportHook, validate_environment


@pytest.fixture
def mock_environment(tmp_path):
    """Create a mock Python environment structure"""
    env_path = tmp_path / "mock_env"
    site_packages = env_path / "lib" / "site-packages"
    site_packages.mkdir(parents=True)
    return env_path


@pytest.fixture
def mock_package(mock_environment):
    """Create a mock package in the environment"""
    site_packages = mock_environment / "lib" / "site-packages"
    package_dir = site_packages / "mock_package"
    package_dir.mkdir()

    init_file = package_dir / "__init__.py"
    init_file.write_text(
        dedent("""
        def example_function():
            return "Hello from mock package!"
    """)
    )

    module_file = package_dir / "submodule.py"
    module_file.write_text(
        dedent("""
        def submodule_function():
            return "Hello from submodule!"
    """)
    )

    return package_dir


@pytest.fixture
def mock_module(mock_environment):
    """Create a mock module file in the environment"""
    site_packages = mock_environment / "lib" / "site-packages"
    module_file = site_packages / "mock_module.py"
    module_file.write_text(
        dedent("""
        def module_function():
            return "Hello from mock module!"
    """)
    )
    return module_file


def test_validate_system_environment():
    """Test validation of system environment"""
    assert validate_environment("$system") == "$system"


def test_validate_valid_environment(mock_environment):
    """Test validation of valid environment path"""
    assert validate_environment(mock_environment) == mock_environment


def test_validate_invalid_environment(tmp_path):
    """Test validation of invalid environment path"""
    with pytest.raises(LookupError):
        validate_environment(tmp_path / "nonexistent")


def test_validate_environment_expands_user():
    """Test that environment paths with ~ are expanded"""
    with pytest.raises(LookupError):
        validate_environment("~/nonexistent_env")


def test_import_hook_init(mock_environment):
    """Test successful initialization of import hook"""
    hook = EnvironmentImportHook(mock_environment)
    assert hook.environment == mock_environment
    assert hook.site_packages == mock_environment / "lib" / "site-packages"


def test_import_hook_init_invalid_env(tmp_path):
    """Test initialization with invalid environment"""
    with pytest.raises(NotADirectoryError):
        EnvironmentImportHook(tmp_path / "nonexistent")


def test_import_hook_init_expands_user():
    """Test that import hook expands user paths"""
    with pytest.raises(NotADirectoryError):
        EnvironmentImportHook("~/nonexistent_env")


def test_find_package(mock_package):
    """Test finding a package with __init__.py"""
    hook = EnvironmentImportHook(mock_package.parent.parent.parent)
    spec = hook.find_spec("mock_package")
    assert isinstance(spec, ModuleSpec)
    assert spec.name == "mock_package"
    assert spec.origin == str(mock_package / "__init__.py")


def test_find_submodule(mock_package):
    """Test finding a submodule within a package"""
    hook = EnvironmentImportHook(mock_package.parent.parent.parent)
    spec = hook.find_spec("mock_package.submodule")
    assert isinstance(spec, ModuleSpec)
    assert spec.name == "mock_package.submodule"
    assert spec.origin == str(mock_package / "submodule.py")


def test_find_module(mock_module):
    """Test finding a standalone module"""
    hook = EnvironmentImportHook(mock_module.parent.parent.parent)
    spec = hook.find_spec("mock_module")
    assert isinstance(spec, ModuleSpec)
    assert spec.name == "mock_module"
    assert spec.origin == str(mock_module)


def test_find_nonexistent_module(mock_environment):
    """Test finding a module that doesn't exist"""
    hook = EnvironmentImportHook(mock_environment)
    spec = hook.find_spec("nonexistent_module")
    assert spec is None


def test_actual_import(mock_package):
    """Test actually importing a module using the hook"""
    hook = EnvironmentImportHook(mock_package.parent.parent.parent)

    sys.meta_path.insert(0, hook)
    sys.path.insert(0, str(hook.site_packages))

    try:
        import mock_package  # type: ignore[import]

        assert mock_package.example_function() == "Hello from mock package!"

        from mock_package import submodule  # type: ignore[import]

        assert submodule.submodule_function() == "Hello from submodule!"
    finally:
        sys.meta_path.remove(hook)
        sys.path.remove(str(hook.site_packages))

        for module in list(sys.modules.keys()):
            if module.startswith("mock_package"):
                del sys.modules[module]


@pytest.mark.parametrize(
    "package_structure",
    [
        {"__init__.py": "value = 42"},
        {"module.py": "value = 42"},
        {"pkg/__init__.py": "value = 42"},
        {"pkg/module.py": "value = 42"},
    ],
)
def test_various_package_structures(mock_environment, package_structure):
    """Test different package and module structures"""
    site_packages = mock_environment / "lib" / "site-packages"

    for path, content in package_structure.items():
        full_path = site_packages / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    hook = EnvironmentImportHook(mock_environment)

    for path in package_structure:
        module_name = path.replace("/", ".").replace(".py", "")
        if module_name.endswith(".__init__"):
            module_name = module_name[:-9]

        spec = hook.find_spec(module_name)
        assert isinstance(spec, ModuleSpec)
        assert spec.name == module_name


def test_concurrent_imports(mock_environment, mock_package):
    """Test concurrent module imports"""
    import threading

    hook = EnvironmentImportHook(mock_environment)
    sys.meta_path.insert(0, hook)
    sys.path.insert(0, str(hook.site_packages))

    def import_module():
        import mock_package  # type: ignore[import]

        assert mock_package.example_function() == "Hello from mock package!"

    try:
        threads = [threading.Thread(target=import_module) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        sys.meta_path.remove(hook)
        sys.path.remove(str(hook.site_packages))
        if "mock_package" in sys.modules:
            del sys.modules["mock_package"]
