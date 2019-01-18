import sys
import logging
from logging import *

from . import package_root_dir


file = logging.FileHandler(filename=str(package_root_dir()/'rprblender.log'),  # TODO: Add creation time to this log name. Could be configurable.
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


class Log:
    __tag: str = "default"
    __default_level: int = logging.INFO
    __default_method_name: str = 'info'

    def __init__(self, tag: str = 'default', level: str = 'debug'):
        if tag:
            self.__tag = tag

        level, method = {
            'info': (logging.INFO, 'info'),
            'debug': (logging.DEBUG, 'debug'),
            'warn': (logging.WARN, 'warn'),
            'error': (logging.ERROR, 'error'),
            'critical': (logging.CRITICAL, 'critical'),
        }.get(level, (None, None))

        if method:
            self.__default_level = level
            self.__default_method_name = method

    def __call__(self, *args):
        if is_level_allowed(self.__default_level):
            _log(getattr(get_logger(self.__tag), self.__default_method_name), args)

    def info(self, *args):
        info(*args, tag=self.__tag)

    def debug(self, *args):
        debug(*args, tag=self.__tag)

    def warn(self, *args):
        warn(*args, tag=self.__tag)

    def error(self, *args):
        error(*args, tag=self.__tag)

    def critical(self, *args):
        critical(*args, tag=self.__tag)
