def alasio_task(task_name):
    """
    Mark a class method as a task entry. Config generation will scan MOD code
    for this marker and generate the task entry function in
    {path_config}/_index/task_entry.py, so main.py only needs to inherit
    TaskEntryGenerated.

    The decorated method must be defined in a class. The class is instantiated
    with the scheduler's config and device, so its __init__ must accept
    "config" and "device" arguments (the contract of alasio.base.base.ModuleBase).
    If you override __init__ with a different signature, a TypeError will be
    raised at runtime instead of a config generation error.

    Examples:
        # module/reward/reward.py
        class Reward:
            @alasio_task('Reward')
            def run(self):
                # actual implement

    Args:
        task_name (str): Task name in scheduler, must match ^[A-Z][a-zA-Z0-9]*$

    Returns:
        callable: The decorated function, unchanged
    """

    def decorator(func):
        """
        Args:
            func (callable): The decorated function

        Returns:
            callable: The function itself, this decorator does nothing at runtime
        """
        return func

    return decorator
