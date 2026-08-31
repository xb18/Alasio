"""
Test worker mods for worker tests.

These functions are the entry implementations of test worker subprocesses,
started via WorkerManager.worker_start() with mod names like
"WorkerTestInfinite". They live in the tests directory (instead of
alasio/backend/worker/bridge.py) so test code never gets mixed into runtime
code. Tests patch WorkerManager.WORKER_ENTRY to worker_test_entry, which
dispatches to the worker functions by mod name.
"""
from alasio.backend.worker.bridge import BackendBridge
from alasio.backend.worker.event import ConfigEvent


def worker_test_infinite():
    # A worker that runs infinitely
    backend = BackendBridge()
    n = 0
    while 1:
        backend.send_log(str(n))
        n += 1
        backend.test_wait.wait(timeout=0.05)


def worker_test_run3():
    # A worker that runs only 3 times
    backend = BackendBridge()
    for n in range(3):
        backend.send_log(str(n))
        backend.test_wait.wait(timeout=0.05)


def worker_test_error():
    # A worker that will raise error
    backend = BackendBridge()
    backend.send_log('1')
    backend.test_wait.wait(timeout=0.05)
    raise Exception


def worker_test_scheduler():
    # A worker that simulates scheduler
    # - emits scheduler-waiting
    # - exits on scheduler_stopping after 0.5s
    backend = BackendBridge()
    backend.send_log('1')
    n = 0
    while 1:
        if n % 3 == 2:
            backend.send_worker_state('scheduler-waiting')
        else:
            backend.send_worker_state('running')
        n += 1
        if backend.scheduler_stopping.wait(0.05):
            backend.test_wait.wait(timeout=0.05)
            break
        else:
            backend.test_wait.wait(timeout=0.05)
            continue


def worker_test_send_events():
    # A worker that sends various config events for testing
    backend = BackendBridge()

    # Send log event
    backend.send_log('worker started')
    backend.test_wait.wait(timeout=0.05)

    # Send custom config events
    backend.send(ConfigEvent(t='CustomEvent', v='test_value_1'))
    backend.test_wait.wait(timeout=0.05)

    backend.send(ConfigEvent(t='CustomEvent', v='test_value_2'))
    backend.test_wait.wait(timeout=0.05)

    backend.send(ConfigEvent(t='DataUpdate', k=('task', 'group', 'arg'), v={'data': 123}))
    backend.test_wait.wait(timeout=0.05)

    # Send worker state
    backend.send_worker_state('scheduler-waiting')
    backend.test_wait.wait(timeout=0.05)

    backend.send_worker_state('running')
    backend.test_wait.wait(timeout=0.05)

    # Wait for stop signal
    while not backend.scheduler_stopping.wait(0.05):
        backend.send_log('still running')
        backend.test_wait.wait(timeout=0.05)


def worker_test_entry(mod_name, config_name, child_conn):
    """
    Worker subprocess entry for test mods

    Patched to WorkerManager.WORKER_ENTRY in tests, the spawned child process
    loads this function by reference from this module and dispatches to the
    worker functions by mod name.

    Args:
        mod_name (str): Mod name, e.g. "WorkerTestInfinite"
        config_name (str): Config name
        child_conn: Child end of the pipe connection
    """
    BackendBridge().init(mod_name, config_name, child_conn)
    try:
        worker = WORKER_TEST_MODS[mod_name]
    except KeyError:
        raise KeyError(f'No such mod to run {mod_name}') from None
    worker()


# mod name -> worker entry, dispatched by worker_test_entry()
WORKER_TEST_MODS = {
    'WorkerTestInfinite': worker_test_infinite,
    'WorkerTestRun3': worker_test_run3,
    'WorkerTestError': worker_test_error,
    'WorkerTestScheduler': worker_test_scheduler,
    'WorkerTestSendEvents': worker_test_send_events,
}
