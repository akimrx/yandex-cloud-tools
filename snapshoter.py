#!/usr/bin/env python3

import logging
import argparse
from datetime import datetime
from utils import Config, Instance

config = Config()

parser = argparse.ArgumentParser(description='Snapshots-tools. To work, you must add instances id to the config file (space separated if multiple)')
parser.add_argument('-v', '--version', action='version',  version='yc-snapshoter 0.3.0')
parser.add_argument('-c', '--create', action='store_true', required=False, help='create snapshots for VMs')
parser.add_argument('-d', '--delete', action='store_true', required=False, help='delete all old snapshots for instances')
parser.add_argument('-f', '--full', action='store_true', required=False, help='create snapshots and delete old snapshots for instances')
args = parser.parse_args()


try:
    instances = [inst for inst in config.instances_list if inst != '']
except Exception as err:
    logging.error(err)
    print(err)


if not instances:
    msg = 'Instances ID is empty. Please type instance_id into config file. If you have multiple VMs, separate them with a space'
    logging.warning(msg)
    print(msg)
    quit()


def snapshots_cleaner():
    print(f'Search and deleting snapshots older than {config.lifetime} days')
    for instance in instances:
        vm = Instance(instance)
        snapshots = vm.get_old_snapshots()
        if snapshots:
            for snapshot in snapshots:
                delete_snap = vm.delete_snapshot(snapshot)
                if vm.operation_complete(delete_snap):
                    pass  # logging.info from class Instance returned


def snapshots_creater():
    print('Creating snapshots')
    for instance in instances:
        vm = Instance(instance)
        if vm.get_data():
            if vm.status() != 'STOPPED':
                stop_vm = vm.stop()
                if vm.operation_complete(stop_vm):
                    snap_create = vm.create_snapshot()
                if vm.operation_complete(snap_create):
                    if vm.status() != 'RUNNING':
                        start_vm = vm.start()
                        if vm.operation_complete(start_vm):
                            pass  # logging.info from class Instance returned
            else:
                logging.info(f'Instance {vm.name()} already stopped.')
                create_snap = vm.create_snapshot()
                if vm.operation_complete(create_snap):
                    pass  # logging.info from class Instance returned


def instance_status_info():
    print('Getting instances status')
    for instance in instances:
        vm = Instance(instance)
        if vm.get_data():
            logging.info(vm)
            print(vm)


if args.create:
    snapshots_creater()
    vm_status_info()
elif args.delete:
    snapshots_cleaner()
elif args.full:
    snapshots_cleaner()
    snapshots_creater()
    instance_status_info()
else:
    print('Input Error. Use --help for more details.')
