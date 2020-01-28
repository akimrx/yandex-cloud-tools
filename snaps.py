#!/usr/bin/env python3

import asyncio
import argparse
from datetime import datetime

from common.logger import logger
from common.utils import Config, Instance
from common.decorators import human_time

STOPPED_INSTANCES = []
config = Config()

parser = argparse.ArgumentParser(description='Snapshots-tools. To work, you must add instances id to the config file (space separated if multiple)')
parser.add_argument('-v', '--version', action='version',  version='yc-snapshoter 0.4')
parser.add_argument('-c', '--create', action='store_true', required=False, help='create snapshots for VMs')
parser.add_argument('-d', '--delete', action='store_true', required=False, help='delete all old snapshots for instances')
parser.add_argument('-f', '--full', action='store_true', required=False, help='create snapshots and delete old snapshots for instances')
parser.add_argument('--run-async', '--async', action='store_true', required=False, help='use this arg only if disks count <= 15 (active-operations-count limit)')
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


def snapshots_cleaner():
    logger.info(f'Search and deleting snapshots older than {config.lifetime} days')
    for instance in instances:
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
        delete_snap = await vm.async_operation_complete(vm.delete_snapshot(snapshot))


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


async def async_snapshots_creater(instance):
    vm = Instance(instance)
    logger.info(f'Creating snapshot for instance {vm.name}')
    if vm.get_data():
        if vm.status != 'STOPPED':
            stop_vm = vm.operation_complete(vm.stop())
            STOPPED_INSTANCES.append(instance)
            if stop_vm:
                snap_create = await vm.async_operation_complete(vm.create_snapshot())
                return snap_create

        else:
            logger.info(f'Instance {vm.name} already stopped.')
            create_snap = await vm.async_operation_complete(vm.create_snapshot())
            return create_snap


async def instance_run(instance):
    vm = Instance(instance)

    if vm.status != 'RUNNING':
        start_vm = await vm.async_operation_complete(vm.start())
        return start_vm


def run_stopped_instances():
    vm_start_task = [instance_run(instance) for instance in STOPPED_INSTANCES if STOPPED_INSTANCES]
    vm_loop = asyncio.get_event_loop()
    vm_loop.run_until_complete(asyncio.wait(vm_start_task))


def creater_run():
    snapshot_tasks = [async_snapshots_creater(instance) for instance in instances]
    create_snap_loop = asyncio.get_event_loop()
    create_snap_loop.run_until_complete(asyncio.wait(snapshot_tasks))

    run_stopped_instances()
    instance_status()


def cleaner_run():
    tasks = [async_snapshots_cleaner(instance) for instance in instances]
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait(tasks))


def instance_status():
    logger.info('Getting instances status')
    for instance in instances:
        vm = Instance(instance)
        logger.info(vm)


if __name__ == '__main__':
    started = datetime.now()

    if args.create:
        if args.run_async:
            creater_run()
        else:
            snapshots_creater()
            instance_status()

    elif args.delete:
        if args.run_async:
            cleaner_run()
        else:
            snapshots_cleaner()

    elif args.full:
        if args.run_async:
            cleaner_run()
            creater_run()
        else:
            snapshots_cleaner()
            snapshots_creater()
            instance_status()

    else:
        print('Input Error. Use --help for more details.')

    delta_time(started, datetime.now())
