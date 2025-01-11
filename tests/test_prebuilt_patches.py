import sys
from unittest.mock import Mock

import pytest
from matplotlib import pyplot
from PIL import Image

from cillow.patch import prebuilt
from cillow.types import ByteStream, Stream


def test_patch_stdout_stderr_write():
    """Test patching stdout and stderr write methods"""
    mock_callback = Mock()
    test_stdout = "Test stdout"
    test_stderr = "Test stderr"

    with prebuilt.patch_stdout_stderr_write(mock_callback):
        sys.stdout.write(test_stdout)
        sys.stderr.write(test_stderr)

    assert mock_callback.call_count == 2
    mock_callback.assert_any_call(Stream(type="stdout", data=test_stdout))
    mock_callback.assert_any_call(Stream(type="stderr", data=test_stderr))


def test_patch_matplotlib_pyplot_show():
    """Test patching matplotlib pyplot show function"""
    mock_callback = Mock()

    pyplot.plot([1, 2, 3], [1, 2, 3])

    with prebuilt.patch_matplotlib_pyplot_show(mock_callback):
        pyplot.show()

    assert mock_callback.call_count == 1
    call_arg = mock_callback.call_args[0][0]
    assert isinstance(call_arg, ByteStream)
    assert call_arg.type == "image"
    assert isinstance(call_arg.data, bytes)


def test_patch_pillow_show():
    """Test patching PIL Image show method"""
    mock_callback = Mock()

    image = Image.new("RGB", (100, 100), color="red")

    with prebuilt.patch_pillow_show(mock_callback):
        image.show()

    assert mock_callback.call_count == 1
    call_arg = mock_callback.call_args[0][0]
    assert isinstance(call_arg, ByteStream)
    assert call_arg.type == "image"
    assert isinstance(call_arg.data, bytes)


def test_patch_combination():
    """Test combining multiple patches"""
    mock_callback = Mock()

    with (
        prebuilt.patch_stdout_stderr_write(mock_callback),
        prebuilt.patch_matplotlib_pyplot_show(mock_callback),
        prebuilt.patch_pillow_show(mock_callback),
    ):
        sys.stdout.write("test")
        pyplot.show()
        Image.new("RGB", (100, 100)).show()

    assert mock_callback.call_count == 3


@pytest.mark.parametrize(
    "patch_context",
    [prebuilt.patch_stdout_stderr_write, prebuilt.patch_matplotlib_pyplot_show, prebuilt.patch_pillow_show],
)
def test_patch_error_handling(patch_context):
    """Test error handling in patches"""
    mock_callback = Mock()

    with pytest.raises(Exception), patch_context(mock_callback):  # noqa: B017
        raise Exception("Test error")

    assert sys.stdout.write is prebuilt.stdout_write_switchable.original
    assert sys.stderr.write is prebuilt.stderr_write_switchable.original
    assert pyplot.show is prebuilt.matplotlib_pyplot_show_switchable.original
    assert Image._show is prebuilt.pillow_show_switchable.original


def test_patch_stdout_stderr_write_unicode():
    """Test handling of unicode characters in stdout/stderr patches"""
    mock_callback = Mock()
    test_unicode = "Test 🚀 unicode ❤️"

    with prebuilt.patch_stdout_stderr_write(mock_callback):
        sys.stdout.write(test_unicode)

    mock_callback.assert_called_once_with(Stream(type="stdout", data=test_unicode))


def test_patch_matplotlib_pyplot_show_empty_plot():
    """Test handling of empty matplotlib plots"""
    mock_callback = Mock()

    with prebuilt.patch_matplotlib_pyplot_show(mock_callback):
        pyplot.show()

    assert mock_callback.call_count == 1
    call_arg = mock_callback.call_args[0][0]
    assert isinstance(call_arg.data, bytes)


def test_patch_pillow_show_different_formats():
    """Test handling of different image formats in Pillow patch"""
    mock_callback = Mock()
    formats = ["RGB", "RGBA", "L"]

    for fmt in formats:
        image = Image.new(fmt, (100, 100))
        with prebuilt.patch_pillow_show(mock_callback):
            image.show()

        assert mock_callback.call_count == 1
        mock_callback.reset_mock()
