from alasio.base.scheduler.scheduler import AlasioScheduler


# This file was auto-generated, do not modify it manually. To generate:
# ``` python -m module.config.gen ```

class TaskEntryGenerated(AlasioScheduler):
    """
    Task entry functions, generated from @alasio_task() markers
    """

    def Reward(self):
        from module.reward import Reward
        Reward(config=self.config, device=self.device).run()
