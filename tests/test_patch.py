from collections.abc import Generator
from contextlib import contextmanager
from typing import Any
from unittest.mock import Mock

import pytest

from cillow.patch import _patches_with_callback, _patches_without_callback, add_patches, clear_patches, load_patches
from cillow.types import Stream


@pytest.fixture(autouse=True)
def cleanup_patches():
    """Ensure patches are cleared after each test"""
    yield
    clear_patches()


@contextmanager
def dummy_patch() -> Generator[None, None, None]:
    """Simple patch without callback for testing"""
    yield


@contextmanager
def dummy_patch_with_callback(callback: Any) -> Generator[None, None, None]:
    """Simple patch with callback for testing"""
    callback(Stream(type="test", data="test_data"))
    yield


def test_add_patches_without_callback():
    """Test adding patches without callbacks"""
    add_patches(dummy_patch)
    assert len(_patches_without_callback) == 1
    assert len(_patches_with_callback) == 0


def test_add_patches_with_callback():
    """Test adding patches with callbacks"""
    add_patches(dummy_patch_with_callback)
    assert len(_patches_with_callback) == 1
    assert len(_patches_without_callback) == 0


def test_add_multiple_patches():
    """Test adding multiple patches of different types"""
    add_patches(dummy_patch, dummy_patch_with_callback)
    assert len(_patches_without_callback) == 1
    assert len(_patches_with_callback) == 1


def test_clear_patches():
    """Test clearing all patches"""
    add_patches(dummy_patch, dummy_patch_with_callback)
    clear_patches()
    assert len(_patches_without_callback) == 0
    assert len(_patches_with_callback) == 0


def test_load_patches():
    """Test loading patches with callback"""
    mock_callback = Mock()
    add_patches(dummy_patch, dummy_patch_with_callback)

    with load_patches(mock_callback):
        pass

    mock_callback.assert_called_once_with(Stream(type="test", data="test_data"))
