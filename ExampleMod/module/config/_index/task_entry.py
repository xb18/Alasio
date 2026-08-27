# This file was auto-generated, do not modify it manually.
# Generated from @alasio_task() markers in MOD code.

class TaskEntryGenerated:
    """
    Task entry functions, generated from @alasio_task() markers
    """

    def Reward(self):
        from module.reward import Reward
        Reward(config=self.config, device=self.device).run()
