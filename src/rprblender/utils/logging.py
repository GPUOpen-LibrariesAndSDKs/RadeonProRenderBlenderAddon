import sys
import os
from pathlib import Path

import logging
from logging import *


file = logging.FileHandler(filename=str(Path(__file__).parent/'rprblender.log'),
                           mode='w',
                           encoding='utf-8')
file.setFormatter(logging.Formatter('%(asctime)s %(name)s [%(thread)d]: %(levelname)s %(message)s'))


console = logging.StreamHandler(stream=sys.stdout)
logger = logging.getLogger('rpr')  # root logger for the addon
logger.addHandler(console)
console.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s [%(thread)d]:  %(message)s'))

logging.basicConfig(level=logging.DEBUG, handlers=[file])

console_filter = None

class Filter(logging.Filter):

    level_show_always = logging.ERROR

    def __init__(self, name, level_show_always, level_show_min):
        super().__init__(name)
        self.level_show_min = level_show_min
        self.level_show_always = level_show_always

    def filter(self, record: logging.LogRecord):
        if self.level_show_always is not None:
            if record.levelno >= self.level_show_always:
                return True
        return super().filter(record)


def is_level_allowed(levelno):
    if not console_filter:
        return True
    if console_filter.level_show_min is not None:
        if levelno < console_filter.level_show_min:
            return False
    return True


def limit_log(name, level_show_always=logging.INFO, level_show_min=logging.DEBUG):
    global console_filter
    if console_filter:
        console.removeFilter(console_filter)
        console_filter = None
    if name is not None:
        console_filter = Filter('rpr.'+name, level_show_always, level_show_min)
        console.addFilter(console_filter)


def get_logger(tag):
    return logger.getChild(tag) if tag else logger


def _log(log_fun, args):
    msg = ' '.join(str(arg) for arg in args)
    log_fun(msg)


def debug(*args, tag='default'):
    if is_level_allowed(logging.DEBUG):
        _log(get_logger(tag).debug, args)


def info(*args, tag='default'):
    if is_level_allowed(logging.INFO):
        _log(get_logger(tag).info, args)


def warn(*args, tag='default'):
    if is_level_allowed(logging.WARN):
        _log(get_logger(tag).warning, args)


def error(*args, tag='default'):
    if is_level_allowed(logging.ERROR):
        _log(get_logger(tag).error, args)


def critical(*args, tag='default'):
    if is_level_allowed(logging.CRITICAL):
        _log(get_logger(tag).critical, args)
