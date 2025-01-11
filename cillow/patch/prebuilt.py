from collections.abc import Generator
from contextlib import contextmanager
from io import BytesIO
from sys import stderr as sys_stderr
from sys import stdout as sys_stdout
from typing import Any, Callable

from matplotlib import pyplot
from matplotlib import use as use_backend
from PIL import Image

from ..switchable import Switchable
from ..types import ByteStream, Stream

stdout_write_switchable = Switchable(sys_stdout.write)
stderr_write_switchable = Switchable(sys_stderr.write)


@contextmanager
def patch_stdout_stderr_write(callback: Callable[[Stream], Any]) -> Generator[None, None, None]:
    """
    Patch the `write` method of `sys.stdout` and `sys.stderr`.

    Args:
        callback: The callback to process the string content.
    """
    with (
        stdout_write_switchable.switch_to(lambda s: callback(Stream(type="stdout", data=s))),
        stderr_write_switchable.switch_to(lambda s: callback(Stream(type="stderr", data=s))),
    ):
        yield


matplotlib_pyplot_show_switchable = Switchable(pyplot.show)
matplotlib_use_backend_switchable = Switchable(use_backend)


@contextmanager
def patch_matplotlib_pyplot_show(callback: Callable[[ByteStream], Any]) -> Generator[None, None, None]:
    """
    Patch the `matplotlib.pyplot.show` function.

    Args:
        callback: The callback to process the figure image bytes.
    """

    def override_show(*args: Any, **kwargs: Any) -> Any:
        buffer = BytesIO()
        try:
            pyplot.savefig(buffer, format="png")
            buffer.seek(0)

            return callback(ByteStream(type="image", data=buffer.getvalue()))
        finally:
            buffer.close()
            pyplot.close()

    with (
        matplotlib_pyplot_show_switchable.switch_to(override_show),
        matplotlib_use_backend_switchable.switch_to(lambda b, f=True: None),  # type: ignore[misc,arg-type]
    ):
        yield


pillow_show_switchable = Switchable(Image._show)


@contextmanager
def patch_pillow_show(callback: Callable[[ByteStream], Any]) -> Generator[None, None, None]:
    """
    Patch the `PIL.Image.show` method.

    Args:
        callback: The callback to process the image bytes.
    """

    def override_show(image: Image.Image, **options: Any) -> Any:
        data = image._repr_image("PNG", compress_level=1)
        if data:
            return callback(ByteStream(type="image", data=data))

    with pillow_show_switchable.switch_to(override_show):
        yield
