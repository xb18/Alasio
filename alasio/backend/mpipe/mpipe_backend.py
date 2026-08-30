import threading


class MPipeBackend:
    """
    Backend-side access to the supervisor pipe.

    The pipe connection is stashed on builtins.__mpipe_conn__ by the
    backend spawn target (_backend_process_entry): the backend modules
    are imported by both the supervisor process and the backend process,
    so the connection cannot live in a module global at import time.

    All send_bytes on the backend side go through send() so the token
    ACK and the lifespan restart / stop messages share one writer lock
    (a multiprocessing Pipe corrupts its stream on concurrent writes
    from the same end).
    """

    def __init__(self):
        self._send_lock = threading.Lock()

    @staticmethod
    def _conn():
        import builtins
        return getattr(builtins, '__mpipe_conn__', None)

    @property
    def conn(self):
        """
        The pipe connection, or None when running without a supervisor.
        Read-only access for the recv thread (mpipe_recv_loop); all
        writes must go through send().

        Returns:
            PipeConnection | None:
        """
        return self._conn()

    def __bool__(self):
        """
        True when the backend was spawned by a supervisor and the pipe
        is available; False when running without a supervisor.

        Returns:
            bool:
        """
        return self._conn() is not None

    def send(self, data, strict=False):
        """
        Send bytes to the supervisor through the pipe.

        Args:
            data (bytes): Message to send
            strict (bool): When True, raise PermissionError when there
                is no pipe and propagate pipe errors (used by the
                lifespan restart / stop RPCs, which must fail loudly);
                the token ACK uses the default silent mode (a backend
                without supervisor has nothing to acknowledge to).

        Raises:
            PermissionError: When strict and no pipe is attached
        """
        conn = self._conn()
        if conn is None:
            if strict:
                raise PermissionError('Cannot reach supervisor')
            return
        with self._send_lock:
            if strict:
                conn.send_bytes(data)
                return
            try:
                conn.send_bytes(data)
            except (EOFError, OSError):
                # pipe broken, supervisor is gone
                pass


mpipe_backend = MPipeBackend()
