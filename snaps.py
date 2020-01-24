#!/usr/bin/env python3

import argparse
from datetime import datetime

from common.logger import logger
from common.utils import Config, Instance
from common.decorators import human_time


config = Config()

parser = argparse.ArgumentParser(description='Snapshots-tools. To work, you must add instances id to the config file (space separated if multiple)')
parser.add_argument('-v', '--version', action='version',  version='yc-snapshoter 0.3.2')
parser.add_argument('-c', '--create', action='store_true', required=False, help='create snapshots for VMs')
parser.add_argument('-d', '--delete', action='store_true', required=False, help='delete all old snapshots for instances')
parser.add_argument('-f', '--full', action='store_true', required=False, help='create snapshots and delete old snapshots for instances')
args = parser.parse_args()


try:
    instances = [inst for inst in config.instances_list if inst != '']
except Exception as err:
    logger.error(err)


if not instances:
    msg = 'Instances ID is empty. Please type instance_id into config file. If you have multiple VMs, separate them with a space'
    logger.warning(msg)
    quit()


def delta_time(start, end):
    et = int((end - start).total_seconds())
    m_et = human_time(et, 2)
    logger.info('Elapsed time: {et}'.format(et=m_et))


# TODO: async
def snapshots_cleaner():
    logger.info(f'Search and deleting snapshots older than {config.lifetime} days')
    for instance in instances:
        vm = Instance(instance)
        snapshots = vm.get_old_snapshots()

        if snapshots:
            for snapshot in snapshots:
                delete_snap = vm.delete_snapshot(snapshot)
                if vm.operation_complete(delete_snap):
                    continue


# TODO: async
def snapshots_creater():
    logger.info('Creating snapshots')
    for instance in instances:
        vm = Instance(instance)

        if vm.get_data():
            if vm.status != 'STOPPED':
                stop_vm = vm.stop()
                if vm.operation_complete(stop_vm):
                    snap_create = vm.create_snapshot()
                if vm.operation_complete(snap_create):
                    if vm.status != 'RUNNING':
                        start_vm = vm.start()
                        if vm.operation_complete(start_vm):
                            continue

            else:
                logger.info(f'Instance {vm.name} already stopped.')
                create_snap = vm.create_snapshot()
                if vm.operation_complete(create_snap):
                    continue


def instance_status_info():
    logger.info('Getting instances status')
    for instance in instances:
        vm = Instance(instance)
        if vm.get_data():
            logger.info(vm)


if __name__ == '__main__':
    started = datetime.now()

    if args.create:
        snapshots_creater()
        instance_status_info()

    elif args.delete:
        snapshots_cleaner()

    elif args.full:
        snapshots_cleaner()
        snapshots_creater()
        instance_status_info()

    else:
        print('Input Error. Use --help for more details.')

    delta_time(started, datetime.now())
