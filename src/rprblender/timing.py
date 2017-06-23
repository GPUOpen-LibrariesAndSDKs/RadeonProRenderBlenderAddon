import sys
import threading
import time

from rprblender import logging


class TimedContext:

    static = threading.local()

    def __init__(self, name):
        self.data = threading.local()
        self.data.name = name

    def __enter__(self):
        try:
            self.static.depth += 1
        except AttributeError:
            self.static.depth = 0
        self.data.time_start = time.clock()

    def __exit__(self, exc_type, exc_val, exc_tb):
        time_elapsed = time.clock()-self.data.time_start
        logging.debug('  ' * self.static.depth, self.data.name, " took ", time_elapsed, " seconds", tag="timing")
        sys.stdout.flush()

        self.static.depth -= 1