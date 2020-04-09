import os
import logging
import pathlib
import configparser

from os import getenv

logger = logging.getLogger(__name__)

SERVERLESS = False  # later


class Config:

    if SERVERLESS:
        oauth_token = getenv('TOKEN')
        lifetime = getenv('LIFETIME')
        instances_list = getenv('INSTANCES').split(',')

    else:
        try:
            config_path = pathlib.Path.home().joinpath('.ya-tools/')

            if not os.path.exists(config_path):
                os.system('mkdir -p {path}'.format(path=config_path))

            config_file = pathlib.Path.home().joinpath('.ya-tools/yndx.cfg')
            config = configparser.RawConfigParser()
            config.read(config_file)

            oauth_token = config.get('Auth', 'OAuth_token')
            if not oauth_token:
                logger.error('OAuth_token is empty. Please add oAuth-token to ~/.ya-tools/yndx.cfg')
                quit()

            lifetime = config.get('Snapshots', 'Lifetime')
            if not lifetime:
                logger.warning('Snapshot lifetime is empty. Using default value: 365 days')
                lifetime = 365

            watchdog_delay = config.get('Watchdog', 'delay')
            if not watchdog_delay:
                logger.warning('Watchdog delay is empty. Using default delay: 10 seconds')
                watchdog_delay = 10

            instances_list = config.get('Instances', 'IDs').split(' ')
            targets_list = config.get('Watchdog', 'targets').split(' ')

            logger.info(f'Config loaded')

        except (FileNotFoundError, ValueError, configparser.NoSectionError):
            logger.error('Corrupted config or no config file present. Please verify or create ~/.ya-tools/yndx.cfg')
            quit()
