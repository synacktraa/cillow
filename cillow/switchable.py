from collections.abc import Generator
from contextlib import contextmanager
from inspect import getmodule
from types import ModuleType
from typing import Callable, Generic, ParamSpec, TypeVar

__all__ = "Switchable", "switch"


P_Spec = ParamSpec("P_Spec")
T_Retval = TypeVar("T_Retval")


class Switchable(Generic[P_Spec, T_Retval]):
    """
    Create a switch from callable that can be replaced with another callable temporarily.
    Supports module-level functions, classes, class methods and instance methods.

    Features:

    - Supports re-entrant context managers (nested switching)
    - When exiting a context manager, the callable is restored to the previous state:
        - For nested switches, this means restoring to the previous replacement
        - Only when exiting the outermost context manager is the original callable restored
    - Works with any callable that has a parent object (module, class, or instance)

    Examples:
        >>> # Example 1: Redirecting sys.stdout.write to a file
        >>> import sys
        >>> from pathlib import Path
        >>>
        >>> switchable = Switchable(sys.stdout.write)
        >>> with switchable.switch_to(Path('test.txt').open('a').write):
        ...     # Redirect print output to the file 'test.txt'
        ...     print("This will go into the file!")
        >>> print("This will print to the console.")
        This will print to the console.
        >>>
        >>> # Example 2: Nested switching with re-entrant context managers
        >>> import logging
        >>>
        >>> def custom_write_1(text):
        ...     logging.error(f"[Logger 1] {text}")
        >>>
        >>> def custom_write_2(text):
        ...     logging.error(f"[Logger 2] {text}")
        >>>
        >>> switchable = Switchable(print)
        >>> with switchable.switch_to(custom_write_1):
        ...     print("Message 1")
        ...     with switchable.switch_to(custom_write_2):
        ...         print("Message 2")
        ...     print("Message 3")
        >>> print("Message 4")
        ERROR:root:[Logger 1] Message 1
        ERROR:root:[Logger 2] Message 2
        ERROR:root:[Logger 1] Message 3
        Message 4
        >>>
        >>> # Example 3: Mocking a callable for testing
        >>> import random
        >>>
        >>> def mock_random_choice(seq):
        ...     return seq[0]  # Always return the first element
        >>>
        >>> switchable = Switchable(random.choice)
        >>> with switchable.switch_to(mock_random_choice):
        ...     print(random.choice(list(range(10))))
        >>> print(random.choice(list(range(10))))
        0
        5
    """

    def __init__(self, target: Callable[P_Spec, T_Retval]) -> None:
        """
        Initialize the switchable with the given callable.

        Args:
            target: The callable to override
        """
        if hasattr(target, "__self__"):
            module = getmodule(parent := target.__self__)
            variable = getattr(module, target.__name__, None)
            if variable and id(target) == id(variable):
                parent = module
        else:
            parts = target.__qualname__.split(".")
            parent = getmodule(target) if len(parts) == 1 else target.__globals__.get(parts[0])

        if parent is None:
            raise ValueError(f"Could not determine the parent object of the {target} callable")

        if isinstance(parent, ModuleType):
            # This was an interesting edge case
            import os

            if parent.__name__ == os.name:
                parent = os
            elif parent.__name__ == f"{os.name}path":
                parent = os.path

        self._current_target = target
        self._name = target.__name__
        self._parent = parent
        self._target_stack: list[Callable] = []  # For re-entrant context managers

    @property
    def original(self) -> Callable[P_Spec, T_Retval]:
        """Access the original callable."""
        if self._target_stack:
            return self._target_stack[0]

        return self._current_target

    def __call__(self, *args: P_Spec.args, **kwargs: P_Spec.kwargs) -> T_Retval:
        """
        Call the current target callable

        Args:
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Return value of the original or the current target callable
        """
        return self._current_target(*args, **kwargs)

    @contextmanager
    def switch_to(self, target: Callable[P_Spec, T_Retval]) -> Generator[None, None, None]:
        """
        Switch to another target callable temporarily.

        Inside the context, you can either use the switchable instance or the
        original callable to call the target callable.

        Args:
            target: The new target callable with same signature
        """
        self._target_stack.append(self._current_target)
        self._current_target = target

        try:
            setattr(self._parent, self._name, target)
            yield
        finally:
            self._current_target = self._target_stack.pop()
            setattr(self._parent, self._name, self._current_target)


@contextmanager
def switch(
    __from: Callable[P_Spec, T_Retval], __to: Callable[P_Spec, T_Retval]
) -> Generator[Switchable[P_Spec, T_Retval], None, None]:
    """
    Switches from one callable to another temporarily and provides access to the underlying
    Switchable instance. This provides both a convenient one-off switch and the ability
    to perform additional switches within the same context if needed.

    Args:
        __from: The callable to switch from
        __to: The callable to switch to

    Returns:
        The Switchable instance being used for the switch

    Examples:
        >>> import random
        >>>
        >>> # Simple usage
        >>> with switch(random.random, lambda: 0.42):
        ...     assert random.random() == 0.42
        >>>
        >>> # Advanced usage with nested switches
        >>> with switch(random.random, lambda: 0.42) as switchable:
        ...     assert random.random() == 0.42
        ...     with switchable.switch_to(lambda: 0.99):
        ...         assert random.random() == 0.99
    """
    with (switchable := Switchable(__from)).switch_to(__to):
        yield switchable
