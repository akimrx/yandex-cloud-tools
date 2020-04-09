#!/usr/bin/env python3

import os
import asyncio
import logging
import time

from datetime import datetime

BASEDIR = os.path.abspath(os.path.dirname(__file__))
LOGDIR = os.path.join(BASEDIR, 'logs')
WATCH_STATUS = ['STOPPED']

'''Preparing'''

if not os.path.exists(LOGDIR):
    os.mkdir(LOGDIR)

logging.basicConfig(level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%d/%b/%y %H:%M:%S', 
    handlers=[
        logging.FileHandler(os.path.join(LOGDIR, 'watchdog.log')),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

from common.compute import Instance, NEGATIVE_STATES, POSITIVE_STATES
from common.config import Config as config

logger.info(f'Watchdog delay is {config.watchdog_delay} seconds')

# Instances generator from config
try:
    TARGETS = [t for t in config.targets_list if t != '']
except Exception as err:
    logger.error(err)

if not TARGETS:
    msg = 'Targets is empty. Please type targets into config file. If you have multiple targets, separate them with a space'
    logger.warning(msg)
    quit()

# Delete non-existent instances
for instance_id in TARGETS:
    if Instance(instance_id).name is None:
        TARGETS.remove(instance_id)


async def watchdog(instance_id):
    while True:
        await asyncio.sleep(int(config.watchdog_delay))
        instance = Instance(instance_id)

        if instance.status in WATCH_STATUS:
            logger.info(f'Instance {instance.name} is {instance.status}. Working..')
            await instance.async_operation_complete(instance.start())


def run():
    tasks = [watchdog(instance) for instance in TARGETS]
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait(tasks))


if __name__ == '__main__':
    run()
