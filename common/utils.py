import os
import json
import time
import asyncio
import pathlib
import requests
import configparser

from os import getenv

from .logger import logger
from .decorators import retry

from datetime import datetime
from requests.exceptions import ConnectionError, Timeout


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
                logger.warning('Lifetime is empty. Using default value: 365 days')
                lifetime = 365

            instances_list = config.get('Instances', 'IDs').split(' ')
            logger.info(f'Config loaded. Snapshot lifetime is {lifetime} days')

        except (FileNotFoundError, ValueError, configparser.NoSectionError):
            logger.error('Corrupted config or no config file present. Please verify or create ~/.ya-tools/yndx.cfg')
            quit()


class Instance:
    config = Config()

    IAM_URL = 'https://iam.api.cloud.yandex.net/iam/v1/tokens'
    SNAP_URL = 'https://compute.api.cloud.yandex.net/compute/v1/snapshots/'
    COMPUTE_URL = 'https://compute.api.cloud.yandex.net/compute/v1/instances/'
    DISK_URL = 'https://compute.api.cloud.yandex.net/compute/v1/disks/'
    OPERATION_URL = 'https://operation.api.cloud.yandex.net/operations/'

    def __init__(self, instance_id):
        self.iam_token = self.get_iam(self.config.oauth_token)
        self.instance_id = instance_id
        self.lifetime = int(self.config.lifetime)
        self.headers = {
            'Authorization': f'Bearer {self.iam_token}',
            'content-type': 'application/json'
        }
        self.instance_data = self.get_data()

    @retry((ConnectionError, Timeout))
    def get_iam(self, token):
        r = requests.post(self.IAM_URL, json={'yandexPassportOauthToken': token})
        data = json.loads(r.text)

        if r.status_code != 200:
            logger.error(f'{r.status_code} Error in get_iam: {data["message"]}')
            quit()

        else:
            iam_token = data.get('iamToken')
            return iam_token

    def call_time(self):
        current_time = datetime.now()
        raw_time = current_time.strftime('%d-%m-%Y-%H-%M-%S')
        return raw_time

    @retry((ConnectionError, Timeout))
    def get_data(self):
        r = requests.get(self.COMPUTE_URL + self.instance_id, headers=self.headers)
        res = json.loads(r.text)

        if r.status_code == 404:
            logger.warning(f'Instance with ID {self.instance_id} not exist')
        elif r.status_code != 200:
            logger.error(f'{r.status_code} Error in get_data: {res["message"]}')
        else:
            return res

    @property
    def folder_id(self):
        folder_id = self.instance_data.get('folderId')
        return folder_id

    @property
    def name(self):
        name = self.instance_data.get('name')
        return name

    @property
    def boot_disk(self):
        boot_disk = self.instance_data['bootDisk']['diskId']
        return boot_disk

    @property
    def status(self):
        status = self.get_data().get('status')
        return status

    def __repr__(self):
        data = {
            "InstanceID": self.instance_id,
            "FolderID": self.folder_id,
            "Name": self.name,
            "BootDisk": self.boot_disk,
            "Status": self.status
        }

        return data

    def __str__(self):
        try:
            data = self.__repr__()
            result = ", ".join([f'{key}: {value}' for key, value in data.items()])
            return result

        except (TypeError, AttributeError):
            logger.info(f'Instance with ID {self.instance_id} not found.')

    @retry((ConnectionError, Timeout))
    def get_all_snapshots(self):
        try:
            r = requests.get(self.SNAP_URL, headers=self.headers, json={'folderId': self.folder_id})
            res = json.loads(r.text)

            if r.status_code != 200:
                logger.error(f'{r.status_code} Error in get_all_snapshots: {res["message"]}')

            else:
                result = []
                snapshots = res.get('snapshots')

                for snapshot in snapshots:
                    if snapshot['sourceDiskId'] == self.boot_disk:
                        result.append(snapshot)

                return result

        except TypeError:
            logger.info(f'Snapshots for {self.name} not found.')
        except AttributeError:
            logger.warning(f"Can't find snapshots for non-existent instance {self.instance_id}")

    def get_old_snapshots(self):
        result = []
        all_snapshots = self.get_all_snapshots()
    
        if all_snapshots:
            for snapshot in all_snapshots:
                created_at = datetime.strptime(snapshot['createdAt'], '%Y-%m-%dT%H:%M:%Sz')
                today = datetime.utcnow()
                age = int((today - created_at).total_seconds()) // 86400

                if age >= self.lifetime:
                    result.append(snapshot)

            return result

    @retry((ConnectionError, Timeout))
    def operation_status(self, operation_id):
        try:
            r = requests.get(self.OPERATION_URL + operation_id, headers=self.headers)
            res = json.loads(r.text)

            if r.status_code != 200:
                logger.error(f'{r.status_code} Error in operation_status: {res["message"]}')

            else:
                return res

        except requests.exceptions.ConnectionError:
            logger.warning('Connection error. Please check your network connection')
        except Exception as err:
            logger.error(f'Error in operation_status: {err}')

    async def async_operation_complete(self, operation_id):
        if operation_id:
            timeout = 0
            while True:
                operation = self.operation_status(operation_id)
                await asyncio.sleep(2)
                timeout += 2

                if operation.get('done') is True:
                    msg = f'Operation {operation.get("description")} with ID {operation_id} completed'
                    logger.info(msg)
                    return msg

                elif timeout == 600:
                    msg = f'Operation {operation.get("description")} with {operation_id} running too long.'
                    logger.warning(msg)
                    return msg

    def operation_complete(self, operation_id):
        if operation_id:
            timeout = 0
            while True:
                operation = self.operation_status(operation_id)
                time.sleep(2)
                timeout += 2

                if operation.get('done') is True:
                    msg = f'Operation {operation.get("description")} with ID {operation_id} completed'
                    logger.info(msg)
                    return msg

                elif timeout == 600:
                    msg = f'Operation {operation.get("description")} with {operation_id} running too long.'
                    logger.warning(msg)
                    return msg

    @retry((ConnectionError, Timeout))
    def start(self):
        if self.status != 'RUNNING':
            r = requests.post(self.COMPUTE_URL + f'{self.instance_id}:start', headers=self.headers)
            res = json.loads(r.text)

            if r.status_code != 200:
                logger.error(f'{r.status_code} Error in start_vm: {res["message"]}')

            else:
                logger.info(f'Starting instance {self.name} ({self.instance_id})')
                # Return operation ID
                return res.get('id')

        else:
            logger.warning(f'Instance {self.name} has an invalid state for this operation.')

    @retry((ConnectionError, Timeout))
    def stop(self):
        if self.status != 'STOPPED':
            r = requests.post(self.COMPUTE_URL + f'{self.instance_id}:stop', headers=self.headers)
            res = json.loads(r.text)

            if r.status_code != 200:
                logger.error(f'{r.status_code} Error in stop_vm: {res["message"]}')
            else:
                logger.info(f'Stopping instance {self.name} ({self.instance_id})')
                # Return operation ID
                return res.get('id')

        elif self.status == 'STOPPED':
            logger.info(f'Instance {self.name} already stopped.')
        else:
            logger.warning(f'Instance {self.name} has an invalid state for this operation.')

    @retry((ConnectionError, Timeout))
    def create_snapshot(self):
        data = {
            'folderId': self.folder_id,
            'diskId': self.boot_disk,
            'name': f'{self.name}-{self.call_time()}'
        }
        r = requests.post(self.SNAP_URL, json=data, headers=self.headers)
        res = json.loads(r.text)

        if r.status_code == 429:
            logger.warning(f'Snapshot NOT CREATED for instance {self.name}. Error: {res["message"]}')
            logger.error(f'QUOTA ERROR: {res["message"]}')

        elif r.status_code != 200:
            logger.error(f'{r.status_code} Error in create_snapshot: {res["message"]}')

        else:
            logger.info(f'Starting create snapshot for boot-disk {self.boot_disk} on {self.name}')
            # Return operation ID
            return res.get('id')

    @retry((ConnectionError, Timeout))
    def delete_snapshot(self, data=None):
        r = requests.delete(self.SNAP_URL + data["id"], headers=self.headers)
        res = json.loads(r.text)

        if r.status_code != 200:
            logger.error(f'{r.status_code} Error in delete_snapshot: {res["message"]}')
        else:
            logger.info(f'Starting delete snapshot {data["name"]}')
            # Return operation ID
            return res.get('id')
