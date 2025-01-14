from __future__ import annotations

from queue import Full as QueueFullError
from queue import Queue
from signal import Signals, signal
from threading import Event as ThreadEvent

import zmq

from ..logger import Logger
from .client_manager import ClientManager
from .request_worker import RequestWorker

__all__ = ("Server",)


class Server(Logger):
    """
    Cillow server component.

    This class is responsible for managing request workers and client manager.

    - `max_interpreters` limits the total number of processes that can be created.
    - `interpreters_per_client` limits the number of processes that can be created per client.
    - `num_worker_threads` limits the number of request worker threads.
    - `max_queue_size` limits the maximum size of the request queue.

    Examples:
        >>> import cillow
        >>>
        >>> if __name__ == "__main__":
        ...     server = cillow.Server(port=5556, max_interpreters=2, interpreters_per_client=1)
        ...     server.run()

    Don't trust LLMS? Concerned about arbitrary code execution?
    Take full control by limiting functionalities using patches.

    To add patches, use the `add_patches()` function. To clear patches, use `clear_patches()`.

    Examples:
        >>> import cillow
        >>>
        >>> import os
        >>> from contextlib import contextmanager
        >>>
        >>> os_system_switchable = cillow.Switchable(os.system)
        >>>
        >>> @contextmanager
        ... def patch_os_system():
        ...     def disabled_os_system(command: str):
        ...         return "os.system has been disabled."
        ...
        ...     with os_system_switchable.switch_to(disabled_os_system):
        ...         yield
        ...
        >>> cillow.add_patches(
        ...     patch_os_system,  # Disable os.system
        ...     cillow.prebuilt_patches.patch_stdout_stderr_write,  # To capture stdout and stderr
        ...     cillow.prebuilt_patches.patch_matplotlib_pyplot_show,  # To capture matplotlib figures
        ...     cillow.prebuilt_patches.patch_pillow_show,  # To capture PIL images
        ... )
        >>>
        >>> if __name__ == "__main__":
        ...     server = cillow.Server(port=5556, max_interpreters=2, interpreters_per_client=1)
        ...     server.run()
    """

    def __init__(
        self,
        *,
        port: int,
        max_interpreters: int | None = None,
        interpreters_per_client: int | None = None,
        num_worker_threads: int | None = None,
        max_queue_size: int | None = None,
    ):
        """
        Args:
            port: The port to bind the server to
            max_interpreters: Maximum total interpreter processes allowed. (defaults to `os.cpu_count()`)
            interpreters_per_client: Maximum interpreters per client (defaults to `min(2, max_interpreters)`)
            num_worker_threads: Number of worker threads (defaults to `min(2 * max_clients, os.cpu_count())`)
            max_queue_size: Maximum queue size (defaults to `max_clients * interpreters_per_client * 2`)
        """
        self.socket = zmq.Context().socket(zmq.ROUTER)
        self._url = f"tcp://0.0.0.0:{port}"
        self.socket.bind(self._url)

        self._client_manager = ClientManager(max_interpreters, interpreters_per_client)

        if num_worker_threads is None:
            num_worker_threads = self._client_manager.optimal_number_of_request_workers

        if max_queue_size is None:
            max_queue_size = self._client_manager.optimal_max_queue_size

        self.logger.info(f"Max interpreter processes: {self._client_manager.max_interpreters}")
        self.logger.info(f"Interpreter processes per client: {self._client_manager.interpreters_per_client}")
        self.logger.info(f"Number of worker threads: {num_worker_threads}")
        self.logger.info(f"Max request queue size: {max_queue_size}")

        self._request_queue = Queue(maxsize=max_queue_size)  # type: ignore[var-annotated]

        def send_cb(client_id: bytes, msg_type: bytes, msg_body: bytes) -> None:
            self.socket.send_multipart([client_id, b"", msg_type, msg_body])

        self._callback = send_cb
        self._server_event = ThreadEvent()
        self._request_workers = [
            RequestWorker(
                self._request_queue,
                self._client_manager,
                self._callback,  # type: ignore[arg-type]
                self._server_event,
            )
            for _ in range(num_worker_threads)
        ]

    def run(self) -> None:
        """Run the server and block until interrupted."""

        self.logger.info("Starting worker threads...")
        for worker in self._request_workers:
            worker.start()

        signal(Signals.SIGINT, lambda s, f: self._server_event.set())
        signal(Signals.SIGTERM, lambda s, f: self._server_event.set())

        self._server_event.clear()

        try:
            self.logger.info(f"Listening on {self._url}")
            self.logger.info("Press Ctrl+C to exit.")
            while not self._server_event.is_set():
                if not self.socket.poll(timeout=1000):
                    continue

                try:
                    frames = self.socket.recv_multipart(flags=zmq.NOBLOCK)
                    if len(frames) != 3:
                        self._callback(frames[0], b"request_exception", b"Invalid number of frames received")

                    client_id, _, request_bytes = frames
                    try:
                        self._request_queue.put_nowait((client_id, request_bytes))
                    except QueueFullError:
                        self._callback(
                            client_id, b"request_exception", b"Server request queue is full. Try again later."
                        )

                except zmq.ZMQError:
                    pass

        except Exception as e:
            self.logger.error(f"{e.__class__.__name__}: {e!s}")

        finally:
            self.logger.info("Cleaning up resources...")
            self._client_manager.cleanup()

            self.logger.info("Stopping worker threads...")
            for worker in self._request_workers:
                worker.join()

            self.socket.close()
            self.socket.context.term()
            self.logger.info("Shutdown complete.")
