import json
import time
import logging
import requests
import configparser
from functools import wraps
from datetime import datetime
from requests.exceptions import ConnectionError, Timeout


log_name = str(datetime.today().strftime('%d-%m-%Y'))
logging.basicConfig(filename=f'{log_name}.log',
                    filemode='w',
                    format='[%(asctime)s] [%(levelname)s] %(message)s',
                    datefmt='%D %H:%M:%S',
                    level=logging.INFO)


def retry(exceptions, tries=4, delay=5, backoff=2, logger=True):
    def retry_decorator(func):
        @wraps(func)
        def func_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    msg = '{}, Retrying in {} seconds...'.format(e, mdelay)
                    if logger:
                        logging.warning(msg)
                    else:
                        print(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return func(*args, **kwargs)
        return func_retry
    return retry_decorator


class Config:
    try:
        config = configparser.RawConfigParser()
        config.read('yndx.cfg')
        oauth_token = config.get('Auth', 'OAuth_token')
        lifetime = int(config.get('Snapshots', 'Lifetime'))
        instances_list = config.get('Instances', 'IDs').split(' ')
        logging.info(f'Config loaded. Snapshot lifetime is {lifetime} days')
        if oauth_token == '':
            logging.error('OAuth_token is empty. Please add oAuth-token to yndx.cfg')
            print('ERROR: OAuth_token is empty. Please add oAuth-token to yndx.cfg')
            quit()
    except (FileNotFoundError, configparser.NoSectionError):
        print('Corrupted config or no config file present. Please check yndx.cfg')
        logging.error('Corrupted config or no config file present. Please check yndx.cfg')
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
        self.lifetime = self.config.lifetime
        self.headers = {
            'Authorization': f'Bearer {self.iam_token}',
            'content-type': 'application/json'
        }

    @retry((ConnectionError, Timeout))
    def get_iam(self, token):
        r = requests.post(self.IAM_URL, json={'yandexPassportOauthToken': token})
        data = json.loads(r.text)
        if r.status_code != 200:
            logging.error(f'{r.status_code} Error in get_iam: {data["message"]}')
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
            logging.warning(f'Instance with ID {self.instance_id} not exist')
        elif r.status_code != 200:
            logging.error(f'{r.status_code} Error in get_data: {res["message"]}')
        else:
            return res

    def folder_id(self):
        folder_id = self.get_data().get('folderId')
        return folder_id

    def name(self):
        name = self.get_data().get('name')
        return name

    def boot_disk(self):
        boot_disk = self.get_data()['bootDisk']['diskId']
        return boot_disk

    def status(self):
        status = self.get_data().get('status')
        return status

    def __repr__(self):
        data = {
            "InstanceID": self.instance_id,
            "FolderID": self.folder_id(),
            "Name": self.name(),
            "BootDisk": self.boot_disk(),
            "Status": self.status()
        }
        return data

    def __str__(self):
        try:
            data = self.__repr__()
            result = ", ".join([f'{key}: {value}' for key, value in data.items()])
            return result
        except (TypeError, AttributeError):
            logging.info(f'Instance with ID {self.instance_id} not found.')

    @retry((ConnectionError, Timeout))
    def get_all_snapshots(self):
        try:
            r = requests.get(self.SNAP_URL, headers=self.headers, json={'folderId': self.folder_id()})
            res = json.loads(r.text)
            if r.status_code != 200:
                logging.error(f'{r.status_code} Error in get_all_snapshots: {res["message"]}')
            else:
                result = []
                snapshots = res.get('snapshots')
                for snapshot in snapshots:
                    if snapshot['sourceDiskId'] == self.boot_disk():
                        result.append(snapshot)
                return result
        except TypeError:
            logging.info(f'Snapshots for {self.name()} not found.')
        except AttributeError:
            logging.warning(f"Can't find snapshots for non-existent instance {self.instance_id}")

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
                logging.error(f'{r.status_code} Error in operation_status: {res["message"]}')
            else:
                return res
        except requests.exceptions.ConnectionError:
            logging.warning('Connection error. Please check your network connection')
        except Exception as err:
            logging.error(f'Error in operation_status: {err}')

    def operation_complete(self, operation_id):
        if operation_id:
            timeout = 0
            while True:
                operation = self.operation_status(operation_id)
                time.sleep(2)
                timeout += 2
                if operation.get('done') is True:
                    logging.info(f'Operation {operation.get("description")} with ID {operation_id} completed')
                    return True
                elif timeout == 600:
                    logging.warning(f'Operation {operation.get("description")} with {operation_id} running too long.')
                    return True

    @retry((ConnectionError, Timeout))
    def start(self):
        if self.status() != 'RUNNING':
            r = requests.post(self.COMPUTE_URL + f'{self.instance_id}:start', headers=self.headers)
            res = json.loads(r.text)
            if r.status_code != 200:
                logging.error(f'{r.status_code} Error in start_vm: {res["message"]}')
            else:
                logging.info(f'Starting instance {self.name()} ({self.instance_id})')
                # Return operation ID
                return res.get('id')
        else:
            logging.warning(f'Instance {self.name()} has an invalid state for this operation.')

    @retry((ConnectionError, Timeout))
    def stop(self):
        if self.status() != 'STOPPED':
            r = requests.post(self.COMPUTE_URL + f'{self.instance_id}:stop', headers=self.headers)
            res = json.loads(r.text)
            if r.status_code != 200:
                logging.error(f'{r.status_code} Error in stop_vm: {res["message"]}')
            else:
                logging.info(f'Stopping instance {self.name()} ({self.instance_id})')
                # Return operation ID
                return res.get('id')
        elif self.status() == 'STOPPED':
            logging.info(f'Instance {self.name()} already stopped.')
        else:
            loggin.warning(f'Instance {self.name()} has an invalid state for this operation.')

    @retry((ConnectionError, Timeout))
    def create_snapshot(self):
        data = {
            'folderId': self.folder_id(),
            'diskId': self.boot_disk(),
            'name': f'{self.name()}-{self.call_time()}'
        }
        r = requests.post(self.SNAP_URL, json=data, headers=self.headers)
        res = json.loads(r.text)
        if r.status_code == 429:
            logging.warning(f'Snapshot NOT CREATED for instance {self.name()}. Error: {res["message"]}')
            print(f'QUOTA ERROR: {res["message"]}')
        elif r.status_code != 200:
            logging.error(f'{r.status_code} Error in create_snapshot: {res["message"]}')
        else:
            logging.info(f'Starting create snapshot for boot-disk {self.boot_disk()} on {self.name()}')
            # Return operation ID
            return res.get('id')

    @retry((ConnectionError, Timeout))
    def delete_snapshot(self, data=None):
        r = requests.delete(self.SNAP_URL + data["id"], headers=self.headers)
        res = json.loads(r.text)
        if r.status_code != 200:
            logging.error(f'{r.status_code} Error in delete_snapshot: {res["message"]}')
        else:
            logging.info(f'Starting delete snapshot {data["name"]}')
            # Return operation ID
            return res.get('id')
