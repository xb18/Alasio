import typing as t

if t.TYPE_CHECKING:
    from ..alasio import alasio_model as alasio
    from ..alasio import device_model as device


# This file was auto-generated, do not modify it manually. To generate:
# ``` python -m module.config.gen ```

class AlasioConfigGenerated:
    """
    A generated config struct to fool IDE's type-predict and auto-complete
    """

    """
    ========== nav: device ==========
    """
    # ----- Device -----
    Emulator: "device.Emulator"
    EmulatorInfo: "device.EmulatorInfo"
    Error: "device.Error"
    Optimization: "device.Optimization"

    # ----- RestartDevice -----
    # Scheduler: "alasio.SchedulerStatic"

    # ----- RestartGame -----
    # Scheduler: "alasio.SchedulerStatic"

    """
    ========== nav: alasio ==========
    """
    Scheduler: "alasio.Scheduler"

    """
    ========== nav: mixin ==========
    """

    """
    ========== nav: store ==========
    """
