# Backend entry file should not have any heavy global import
# otherwise every child process will import them in spawn mode.
# The two module-level imports below are light: entry.py is stdlib-only,
# supervisor.py is stdlib-only. The actual backend entry (app.py, starlette,
# trio, hypercorn) is imported lazily in alasio.backend.entry.backend_entry.

from alasio.backend.entry import backend_entry
from alasio.backend.supervisor import Supervisor


class BackendSupervisor(Supervisor):
    # staticmethod wrapper is required: a plain function assigned as a class
    # attribute becomes a bound method on instance access, and pickling the
    # bound method would carry the Supervisor instance (with its
    # _thread.lock fields) into the backend child. `self.backend_entry` is
    # pickled into the backend child as spawn args, and the function lives
    # in alasio.backend.entry (stdlib-only), so the child process never
    # imports this file nor supervisor.py.
    backend_entry = staticmethod(backend_entry)

    def run_gui(self, args=None, root='', up=1):
        """
        Args:
            args (list[str] | None):
            root (str): input __file__ of gui.py
            up (int): Uppath from gui.py to project root
        """
        import sys

        from alasio.ext.path import PathStr

        gui_args = sys.argv[1:]
        if args:
            gui_args += args
        gui_args += ['--root', PathStr.new(root).uppath(up)]
        self.run(gui_args)
