from alasio.base.scheduler.task_entry import alasio_task
from alasio.logger import logger


class Reward:
    def __init__(self, config, device):
        self.config = config
        self.device = device

    @alasio_task('Reward')
    def run(self):
        logger.info('Run task Reward')
