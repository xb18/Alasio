"""
Root propagation tests.

The project root set by the supervisor (gui.py --root, computed with stdlib
from the entry file) must reach every process of the chain:

- backend: create_config sets env.PROJECT_ROOT and os.chdir() to the root,
  so both PROJECT_ROOT and cwd equal the supervisor-provided root even when
  the chain was started from a foreign cwd
- worker: PROJECT_ROOT propagates through the spawn args (mod_entry calls
  env.set_project_root(project_root)); the worker cwd is the mod_root by
  design (mod_entry chdirs to the mod folder as the mod's relative-path
  base), while the worker's initial cwd inherits the backend cwd (= root)

The test launches tests/backend/root_propagation.py from a temporary
foreign cwd and asserts on the stdout markers printed by the backend and
the worker processes.
"""
import os
import subprocess
import sys
import tempfile
import time

# Project root, the value passed as --root (also the repo layout)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'root_propagation.py')

# generous window: the chain imports starlette / trio / hypercorn
START_TIMEOUT = 30
# backend prints markers, spawns a worker, then asks the supervisor to stop
EXIT_TIMEOUT = 15


def _run_chain():
    """
    Start the supervisor script from a foreign cwd with --root <ROOT> and
    collect its stdout until exit.

    Returns:
        str: Full stdout of the whole process chain
    """
    foreign_cwd = tempfile.mkdtemp(prefix='alasio_root_test_cwd_')
    env = os.environ.copy()
    existing = env.get('PYTHONPATH')
    env['PYTHONPATH'] = ROOT + (os.pathsep + existing if existing else '')

    proc = subprocess.Popen(
        [sys.executable, SCRIPT, '--root', ROOT],
        cwd=foreign_cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
        bufsize=1,
    )

    output = ''
    deadline = time.time() + START_TIMEOUT
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        output += line
        if 'WORKER_ROOT=' in output:
            # markers complete, the backend asks the supervisor to stop now
            break

    try:
        proc.wait(timeout=EXIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

    return output


def _marker(output, name):
    """
    Extract the value of a `NAME=value` marker from the output.

    Args:
        output (str): Collected chain stdout
        name (str): Marker name

    Returns:
        str | None: The marker value, or None when missing
    """
    for line in output.splitlines():
        if line.startswith(f'{name}='):
            return line.partition('=')[2]
    return None


def _norm(value):
    """
    Normalize path separators for comparison: PROJECT_ROOT is a PathStr
    using forward slashes while os.getcwd() uses the platform separator.

    Args:
        value (str | None):

    Returns:
        str | None:
    """
    if value is None:
        return None
    return os.path.normpath(value)


class TestRootPropagation:
    """
    --root set by the supervisor must reach backend and worker, and the
    backend cwd must follow the root (chdir) even from a foreign cwd.
    """

    def test_backend_cwd_and_project_root_equal_root(self):
        output = _run_chain()
        assert _norm(_marker(output, 'BACKEND_CWD')) == ROOT, output
        assert _norm(_marker(output, 'BACKEND_ROOT')) == ROOT, output

    def test_worker_project_root_propagates(self):
        output = _run_chain()
        assert _norm(_marker(output, 'WORKER_ROOT')) == ROOT, output

    def test_worker_cwd_is_mod_root(self):
        """
        The worker chdirs to the mod folder (mod_entry, the mod's
        relative-path base); the mod_root marker must match the worker cwd.
        """
        output = _run_chain()
        mod_root = _marker(output, 'MOD_ROOT')
        assert mod_root is not None, output
        assert _marker(output, 'WORKER_CWD') == mod_root, output
