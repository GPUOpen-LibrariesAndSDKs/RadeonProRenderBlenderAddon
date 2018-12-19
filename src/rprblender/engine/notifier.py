from rprblender import logging, config


class Notifier:
    def __init__(self, rpr_engine, title):
        self.rpr_engine = rpr_engine
        self.title = title
        logging.info(self.title, tag='Notifier')

    def update_info(self, progress, info):
        self.rpr_engine.update_progress(progress)
        self.rpr_engine.update_stats(self.title, info)

        if config.notifier_log_calls:
            logging.info(progress, info, tag='Notifier')
