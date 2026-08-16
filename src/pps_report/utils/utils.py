import logging
import time

logger = logging.getLogger(__name__)


def timeit(func):
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        logger.debug("%s took %.4fs", func.__name__, end - start)
        return result
    return wrapper
