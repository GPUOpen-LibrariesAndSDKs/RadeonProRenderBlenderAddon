from rprblender import config
from rprblender.utils import logging


log = logging.Log(tag='Notifier')


class Notifier:
    def __init__(self, rpr_engine, title):
        self.rpr_engine = rpr_engine
        self.title = title
        log(self.title)

    def update_info(self, progress, info):
        self.rpr_engine.update_progress(progress)
        self.rpr_engine.update_stats(self.title, info)

        if config.notifier_log_calls:
            log(progress, info)
