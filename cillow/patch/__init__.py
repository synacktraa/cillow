from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from inspect import signature
from typing import Any, Callable, ContextManager, Protocol  # noqa: UP035

from ..types import ByteStream, Stream

__all__ = "add_patches", "clear_patches", "load_patches"


class PatchProtocol(Protocol):
    """Patch callable protocol"""

    def __call__(self) -> ContextManager[None]: ...


class StreamCapturePatchProtcol(Protocol):
    """Patch callable protocol with stream capture callback"""

    def __call__(self, on_stream: Callable[[Stream | ByteStream], Any]) -> ContextManager[None]: ...


_patches_with_callback: list[StreamCapturePatchProtcol] = []
_patches_without_callback: list[PatchProtocol] = []


def add_patches(*patches: PatchProtocol | StreamCapturePatchProtcol) -> None:
    """
    Add new patches to be used by all Interpreter instances.

    Args:
        patches: The context manager callables to add
    """
    for patch in patches:
        if len(signature(patch).parameters) == 0:
            _patches_without_callback.append(patch)  # type: ignore[arg-type]
        else:
            _patches_with_callback.append(patch)  # type: ignore[arg-type]


@contextmanager
def load_patches(on_stream: Callable[[Stream | ByteStream], Any]) -> Generator[None, None, None]:
    """
    Load the patches inside a context.

    Args:
        on_stream: The callback to capture streaming output.
    """
    with ExitStack() as stack:
        for patch_fn in _patches_without_callback:
            stack.enter_context(patch_fn())
        for _patch_fn in _patches_with_callback:
            stack.enter_context(_patch_fn(on_stream))
        yield


def clear_patches() -> None:
    """Clear all the added patches."""
    _patches_with_callback.clear()
    _patches_without_callback.clear()
