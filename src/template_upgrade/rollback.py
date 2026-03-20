from __future__ import annotations
import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional
from .exceptions import BackupError, RollbackError
log = logging.getLogger(__name__)

@dataclass
class Snapshot:
    from_version: int
    clone_name: str
    created_at: float = field(default_factory=time.time)

class RollbackManager:

    def __init__(self, original: str) -> None:
        self.original = original
        self._stack: list[Snapshot] = []

    def create_snapshot(self, from_version: int) -> Snapshot:
        ts = int(time.time())
        clone_name = f'{self.original}-snap-{ts}'
        log.info('Creating snapshot: %s → %s', self.original, clone_name)
        try:
            subprocess.run(['qvm-clone', self.original, clone_name], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise BackupError(f'qvm-clone failed: {e.stderr.decode()}') from e
        snap = Snapshot(from_version=from_version, clone_name=clone_name)
        self._stack.append(snap)
        return snap

    def commit(self, snapshot: Snapshot) -> None:
        log.info('Committing snapshot %s (removing clone)', snapshot.clone_name)
        if self._stack and self._stack[-1].clone_name == snapshot.clone_name:
            self._stack.pop()
        self._remove_vm(snapshot.clone_name)

    def restore(self, snapshot: Snapshot) -> int:
        log.warning('Rolling back %s to version %d from snapshot %s', self.original, snapshot.from_version, snapshot.clone_name)
        while self._stack and self._stack[-1].clone_name != snapshot.clone_name:
            top = self._stack.pop()
            log.info('Removing intermediate snapshot %s', top.clone_name)
            self._remove_vm(top.clone_name)
        if self._stack:
            self._stack.pop()
        try:
            self._remove_vm(self.original)
            subprocess.run(['qvm-clone', snapshot.clone_name, self.original], check=True, capture_output=True)
            self._remove_vm(snapshot.clone_name)
        except subprocess.CalledProcessError as e:
            raise RollbackError(f'Rollback failed while replacing {self.original}: {e.stderr.decode()}') from e
        log.info('Rollback complete. %s is at version %d', self.original, snapshot.from_version)
        return snapshot.from_version

    def current_snapshots(self) -> list[Snapshot]:
        return list(self._stack)

    @staticmethod
    def _remove_vm(name: str) -> None:
        result = subprocess.run(['qvm-remove', '--force', name], capture_output=True)
        if result.returncode not in (0,):
            log.warning('qvm-remove %s returned %d: %s', name, result.returncode, result.stderr.decode())
