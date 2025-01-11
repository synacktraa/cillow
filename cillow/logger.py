from __future__ import annotations

import sys

from loguru import logger
from loguru._logger import Logger as LoguruLogger

__all__ = ("Logger",)


logger.remove(0)

DEFAULT_LOGGER_FORMAT = "<bg #0f0707>[{extra[class_name]}]</bg #0f0707> <level>{message}</level>"


class Logger:
    """
    Logger class that can be inherited for class based logging.

    Examples:
        >>> class ClassName(Logger, format="<level>{message}</level>"):
        ...     def __init__(self):
        ...         self.logger.info("Class initialized")
        ...
        ...     @classmethod
        ...     def cls_method(cls):
        ...         cls.logger.info("Class method called")
        ...
        >>> ClassName()
        >>> ClassName.cls_method()
        >>> ClassName.logger.info("Hello Logger")
    """

    logger: LoguruLogger

    @classmethod
    def __init_subclass__(cls, *, format: str | None = None):  # noqa: A002
        """
        Args:
            format: Logging format to use.
        """
        logger.add(
            sys.stdout,
            format=format or DEFAULT_LOGGER_FORMAT,
            filter=lambda record: record["extra"].get("class_name") == cls.__name__,
        )
        cls.logger = logger.bind(class_name=cls.__name__).opt(colors=True)  # type: ignore[assignment]
