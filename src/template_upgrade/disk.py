from __future__ import annotations
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from .exceptions import CacheDiskError
log = logging.getLogger(__name__)
DEFAULT_CACHE_DIR = Path('/var/tmp')
DEFAULT_SIZE_GB = 5
TEMPLATE_MOUNT_POINT = '/mnt/removable'

@dataclass
class CacheDisk:
    image_path: Path
    loop_dev: str
    block_id: str

def allocate(size_gb: int=DEFAULT_SIZE_GB) -> CacheDisk:
    img = Path(tempfile.mktemp(prefix='qubes-upgrade-cache-', suffix='.img', dir=DEFAULT_CACHE_DIR))
    log.info('Allocating %d GB cache disk at %s', size_gb, img)
    try:
        subprocess.run(['truncate', '-s', f'{size_gb}G', str(img)], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise CacheDiskError(f'truncate failed: {e.stderr.decode()}') from e
    try:
        result = subprocess.run(['sudo', 'losetup', '-f', '--show', str(img)], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        img.unlink(missing_ok=True)
        raise CacheDiskError(f'losetup failed: {e.stderr}') from e
    loop_dev = result.stdout.strip()
    block_id = Path(loop_dev).name
    log.info('Loop device: %s  block_id: %s', loop_dev, block_id)
    return CacheDisk(image_path=img, loop_dev=loop_dev, block_id=block_id)

def attach(disk: CacheDisk, template: str) -> None:
    log.info('Attaching %s to %s', disk.block_id, template)
    try:
        subprocess.run(['qvm-block', 'attach', template, f'dom0:{disk.block_id}'], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise CacheDiskError(f'qvm-block attach failed: {e.stderr.decode()}') from e

def detach(disk: CacheDisk, template: str) -> None:
    log.info('Detaching %s from %s', disk.block_id, template)
    result = subprocess.run(['qvm-block', 'detach', template, f'dom0:{disk.block_id}'], capture_output=True)
    if result.returncode != 0:
        log.warning('qvm-block detach returned %d: %s', result.returncode, result.stderr.decode())

def release_loop(disk: CacheDisk) -> None:
    log.info('Releasing loop device %s', disk.loop_dev)
    result = subprocess.run(['sudo', 'losetup', '-d', disk.loop_dev], capture_output=True)
    if result.returncode != 0:
        log.warning('losetup -d returned %d', result.returncode)

def cleanup(disk: CacheDisk, template: str) -> None:
    detach(disk, template)
    release_loop(disk)
    try:
        disk.image_path.unlink(missing_ok=True)
        log.info('Deleted cache image %s', disk.image_path)
    except OSError as e:
        log.warning('Could not delete cache image: %s', e)
