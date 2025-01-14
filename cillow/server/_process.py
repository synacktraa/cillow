from __future__ import annotations

from collections.abc import Generator
from multiprocessing import Event as MpEvent
from multiprocessing import Process
from multiprocessing import Queue as MpQueue
from multiprocessing.synchronize import Event as MpEventType
from queue import Empty as EmptyQueueError
from typing import Any

from ..interpreter import Interpreter
from ..types import PythonEnvironment

__all__ = ("_InterpreterProcess",)


class _InterpreterProcess:
    """
    Create an interpreter from a given python environment in a separate process.

    This is not supposed to be used directly. Use cillow.Interpreter instead.
    """

    def __init__(self, environment: PythonEnvironment):
        """
        Args:
            environment: The Python environment to use
        """
        self._input_queue = MpQueue()  # type: ignore[var-annotated]
        self._output_queue = MpQueue()  # type: ignore[var-annotated]
        self._process_event = MpEvent()

        # fmt: off
        self._process = Process(
            target=_process_event_loop, args=(
                environment, self._input_queue, self._output_queue, self._process_event
            )
        )
        self._process.start()
        # fmt: on

    def _send_input(self, **kwargs: Any) -> Generator[Any, None, None]:
        self._input_queue.put(kwargs)
        while True:
            try:
                output = self._output_queue.get(timeout=1)

                if output is _completed:
                    break
                yield output

            except EmptyQueueError:
                continue

    def stop(self) -> None:
        """Stop the interpreter process."""
        self._process_event.set()

        if self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=5)

        # Force kill if still running
        if self._process.is_alive():
            self._process.kill()
            self._process.join()

        self._process.close()
        self._input_queue.close()
        self._output_queue.close()


class _completed:
    """A sentinel value to indicate to stop reading from the output queue."""


def _process_event_loop(
    environment: PythonEnvironment, input_queue: MpQueue, output_queue: MpQueue, process_event: MpEventType
) -> None:
    """
    The main loop that runs in the separate process.

    Args:
        environment: The Python environment to use
        input_queue: The queue to receive code from
        output_queue: The queue to write output to
        process_event: The event to stop the process
    """
    import os

    instance = Interpreter(environment)
    try:
        while not process_event.is_set():
            request = input_queue.get()

            if "code" in request:
                output_queue.put(instance.run_code(request["code"], on_stream=output_queue.put))
            elif "cmd" in request:
                instance.run_command(*request["cmd"], on_stream=output_queue.put)
            elif "requirements" in request:
                instance.install_requirements(*request["requirements"], on_stream=output_queue.put)
            elif "environment_variables" in request:
                os.environ.update(request["environment_variables"])
            else:
                continue
            output_queue.put(_completed)
    except KeyboardInterrupt:
        return
    finally:
        del instance
