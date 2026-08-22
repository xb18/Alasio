import trio

SHUTDOWN_EVENT = trio.Event()


def mpipe_recv_loop(conn, trio_token):
    """
    Args:
        conn (PipeConnection):
        trio_token:
    """
    from alasio.backend.prefs import handle_stdin_set_dpi_scaling, handle_stdin_set_lang, handle_stdin_set_theme
    from alasio.logger import logger

    def request_shutdown(reason):
        """
        Request the backend to shut itself down.

        The shutdown event is always set, even if logging fails: when the
        supervisor or the host process (electron) died, the stdout pipe may
        be broken and the logger could raise. The backend must never be left
        running as an orphan just because the log message could not be
        written.

        Args:
            reason (str): Log message for the shutdown
        """
        try:
            trio.from_thread.run_sync(SHUTDOWN_EVENT.set, trio_token=trio_token)
        except Exception:
            # trio loop is already gone, nothing left to signal
            pass
        try:
            logger.info(reason)
        except Exception:
            # stdout pipe broken (host process died), drop the message
            pass

    while 1:
        try:
            msg = conn.recv_bytes()
        except (EOFError, OSError):
            request_shutdown('Backend disconnected to supervisor, shutting down backend')
            break

        if msg == b'command:stop':
            request_shutdown('Backend received stop request from supervisor, shutting down backend')
            break
        elif msg.startswith(b'command:set_lang:'):
            # Host-level webapp language from the stdin contract. Parse,
            # validate and persist; keep looping (do not break).
            lang = msg.split(b':', 2)[2].decode()
            handle_stdin_set_lang(lang)
        elif msg.startswith(b'command:set_theme:'):
            # Host-level webapp theme from the stdin contract.
            theme = msg.split(b':', 2)[2].decode()
            handle_stdin_set_theme(theme)
        elif msg.startswith(b'command:set_dpi_scaling:'):
            # Host-level webapp dpi scaling from the stdin contract. A
            # single value ('true'/'false'), no config/display split.
            dpi_scaling = msg.split(b':', 2)[2].decode()
            handle_stdin_set_dpi_scaling(dpi_scaling)
        else:
            logger.warning(f'Backend received unknown msg from supervisor: {msg}')


async def lifespan_restart():
    """
    Restart the entire backend
    """
    import builtins
    conn = getattr(builtins, '__mpipe_conn__', None)
    if conn is None:
        raise PermissionError(f'Cannot restart backend running without supervisor')

    # log
    from alasio.logger import logger
    logger.info('Backend received restart request from RPC, shutting down backend')

    # Send b'command:restart' to supervisor
    await trio.to_thread.run_sync(conn.send_bytes, b'command:restart')

    # stop backend
    SHUTDOWN_EVENT.set()


async def lifespan_stop():
    """
    Stop the entire backend
    """
    import builtins
    conn = getattr(builtins, '__mpipe_conn__', None)
    if conn is None:
        raise PermissionError(f'Cannot stop backend running without supervisor')

    # log
    from alasio.logger import logger
    logger.info('Backend received stop request from RPC, shutting down backend')

    # Send b'command:stop' to supervisor
    await trio.to_thread.run_sync(conn.send_bytes, b'command:stop')

    # stop backend
    SHUTDOWN_EVENT.set()


def get_shutdown_trigger():
    """
    Get shutdown_trigger function, or None if no daemon by supervisor.
    When shutdown_trigger() runs ended, hypercorn will stop serving connections.
    """
    import builtins

    from alasio.logger import logger
    conn = getattr(builtins, '__mpipe_conn__', None)
    if conn is None:
        # no supervisor, cannot restart
        logger.info('Backend running without supervisor')
        return None

    logger.info('Backend running with supervisor')
    trio_token = trio.lowlevel.current_trio_token()

    async def shutdown_trigger():
        # if shutdown event is set, shutdown_trigger() will stop hypercorn
        await SHUTDOWN_EVENT.wait()

    from threading import Thread
    thread = Thread(target=mpipe_recv_loop, args=(conn, trio_token),
                    name='mpipe_child_recv', daemon=True)
    thread.start()
    return shutdown_trigger
