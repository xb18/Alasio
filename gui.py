# =============================================================================
# PROCESS BOUNDARY -- heavy imports must stay inside the `if __name__ ==
# '__main__':` block.
#
# This entry script is re-executed by EVERY spawn child (as __mp_main__):
# backend and worker children run the module level of this file. Module
# level must stay minimal (patch_startup only); the BackendSupervisor
# import must stay inside the __main__ block, or the children would import
# the whole supervisor stack.
# =============================================================================

from alasio.backport.patch import patch_startup

patch_startup()

if __name__ == '__main__':
    # run
    from alasio.backend.backend import BackendSupervisor

    supervisor = BackendSupervisor().multiprocessing_freeze_support()
    supervisor.run_gui()
