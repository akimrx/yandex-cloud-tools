#!/usr/bin/env python3

import os
import asyncio
import argparse
import logging
from datetime import datetime

BASEDIR = os.path.abspath(os.path.dirname(__file__))
LOGDIR = os.path.join(BASEDIR, 'logs')

if not os.path.exists(LOGDIR):
    os.mkdir(LOGDIR)

logging.basicConfig(level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%d/%b/%y %H:%M:%S', 
    handlers=[
        logging.FileHandler(os.path.join(LOGDIR, 'snaps.log')),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

from common.utils import Config, Instance
from common.decorators import human_time

STOPPED_INSTANCES = []
NEGATIVE_STATES = ['STOPPED', 'STOPPING', 'ERROR', 'CRASHED']
POSITIVE_STATES = ['RUNNING', 'PROVISIONING', 'CREATING']

config = Config()

parser = argparse.ArgumentParser(description='Snapshots-tools. To work, you must add instances id to the config file (space separated if multiple)')
parser.add_argument('-v', '--version', action='version',  version='yc-snaps 0.4.2')
parser.add_argument('-c', '--create', action='store_true', required=False, help='create snapshots for VMs')
parser.add_argument('-d', '--delete', action='store_true', required=False, help='delete all old snapshots for instances')
parser.add_argument('-f', '--full', action='store_true', required=False, help='create snapshots and delete old snapshots for instances')
parser.add_argument('--run-async', '--async', action='store_true', required=False, help='use this arg only if disks count <= 15 (active-operations-count limit)')
args = parser.parse_args()


# Instances generator from config
try:
    INSTANCES = [inst for inst in config.instances_list if inst != '']
except Exception as err:
    logger.error(err)

if not INSTANCES:
    msg = 'Instances ID is empty. Please type instance_id into config file. If you have multiple VMs, separate them with a space'
    logger.warning(msg)
    quit()

# Delete non-existent instances
for instance_id in INSTANCES:
    if Instance(instance_id).name is None:
        INSTANCES.remove(instance_id)


def delta_time(start, end):
    et = int((end - start).total_seconds())
    m_et = human_time(et, 2)
    logger.info(f'Elapsed time: {m_et}')


def snapshots_cleaner():
    logger.info(f'Search and deleting snapshots older than {config.lifetime} days')
    for instance in INSTANCES:
        vm = Instance(instance)
        snapshots = vm.get_old_snapshots()

        if not snapshots:
            logger.info(f'Snapshots older than {config.lifetime} days not found for instance {vm.name}')
            continue

        for snapshot in snapshots:
            delete_snap = vm.delete_snapshot(snapshot)
            if vm.operation_complete(delete_snap):
                continue


async def async_snapshots_cleaner(instance):
    vm = Instance(instance)
    logger.info(f'Search and deleting snapshots older than {config.lifetime} days for instance {vm.name}')
    snapshots = vm.get_old_snapshots()

    if not snapshots:
        logger.info(f'Snapshots older than {config.lifetime} days not found for instance {vm.name}')
        return

    for snapshot in snapshots:
        await vm.async_operation_complete(vm.delete_snapshot(snapshot))


def snapshots_creater():
    logger.info('Preparing instances to create a snapshot')
    for instance in INSTANCES:
        vm = Instance(instance)

        if vm.get_data():
            if vm.status not in NEGATIVE_STATES:
                stop_vm = vm.stop()
                if vm.operation_complete(stop_vm):
                    snap_create = vm.create_snapshot()
                if vm.operation_complete(snap_create):
                    if vm.status not in POSITIVE_STATES:
                        start_vm = vm.start()
                        if vm.operation_complete(start_vm):
                            continue

            else:
                logger.info(f'Instance {vm.name} already stopped.')
                create_snap = vm.create_snapshot()
                if vm.operation_complete(create_snap):
                    continue


async def async_snapshots_creater(instance):
    vm = Instance(instance)
    logger.info(f'Preparing instance {vm.name} to create a snapshot')
    if vm.get_data():
        if vm.status not in NEGATIVE_STATES:
            stop_vm = vm.operation_complete(vm.stop())
            STOPPED_INSTANCES.append(instance)
            if stop_vm:
                await vm.async_operation_complete(vm.create_snapshot())

        else:
            logger.info(f'Instance {vm.name} already stopped.')
            await vm.async_operation_complete(vm.create_snapshot())


async def instance_run(instance):
    vm = Instance(instance)
    if vm.status not in POSITIVE_STATES:
        await vm.async_operation_complete(vm.start())


def run_stopped_instances():
    if not STOPPED_INSTANCES:
        return

    vm_start_task = [instance_run(instance) for instance in STOPPED_INSTANCES if STOPPED_INSTANCES]
    vm_loop = asyncio.get_event_loop()
    vm_loop.run_until_complete(asyncio.wait(vm_start_task))


def async_creater_run():
    snapshot_tasks = [async_snapshots_creater(instance) for instance in INSTANCES]
    create_snap_loop = asyncio.get_event_loop()
    create_snap_loop.run_until_complete(asyncio.wait(snapshot_tasks))

    run_stopped_instances()
    instance_status()


def async_cleaner_run():
    tasks = [async_snapshots_cleaner(instance) for instance in INSTANCES]
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait(tasks))


def instance_status():
    logger.info('Getting instances status')
    for instance in INSTANCES:
        vm = Instance(instance)
        if vm.name is not None:
            logger.info(vm)


if __name__ == '__main__':
    started = datetime.now()

    if args.create:
        if args.run_async:
            async_creater_run()
        else:
            snapshots_creater()
            instance_status()

    elif args.delete:
        if args.run_async:
            async_cleaner_run()
        else:
            snapshots_cleaner()

    elif args.full:
        if args.run_async:
            async_cleaner_run()
            async_creater_run()
        else:
            snapshots_cleaner()
            snapshots_creater()
            instance_status()

    else:
        print('Input Error. Use --help for more details.')

    delta_time(started, datetime.now())
