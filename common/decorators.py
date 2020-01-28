import threading
from functools import wraps

from .logger import logger


def retry(exceptions, tries=4, delay=5, backoff=2, logger=True):
    def retry_decorator(func):
        @wraps(func)
        def func_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    msg = 'Network problems. Retrying in {} seconds...'.format(mdelay)
                    if logger:
                        logger.warning(msg)
                    else:
                        print(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return func(*args, **kwargs)
        return func_retry
    return retry_decorator


def thread(func):
    def wrapper(*args, **kwargs):
        current_thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        current_thread.start()
    return wrapper


def human_time(seconds, granularity=2):
    result = []
    intervals = (
        ('years', 31104000),
        ('months', 2592000),
        ('weeks', 604800),
        ('days', 86400),
        ('hours', 3600),
        ('minutes', 60),
        ('seconds', 1),
    )
    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = name.rstrip('s')
            result.append("{} {}".format(value, name))
    return ', '.join(result[:granularity])
