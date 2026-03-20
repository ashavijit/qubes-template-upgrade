from __future__ import annotations
import logging
import signal
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional
from . import disk, packages, runner
from .exceptions import AgentError, CacheDiskError, DiskSpaceError, MaxRetriesExceeded, UpgradeError, VerificationError
from .retry import RetryScheduler
from .rollback import RollbackManager, Snapshot
from .state import StateMachine, Step
from .version import DEBIAN_CODENAMES, find_upgrade_path, get_template_info, next_supported_version
log = logging.getLogger(__name__)
AGENTS_DIR = Path(__file__).parent / 'agents'
STATE_FILE = Path('/run/qubes-upgrade-state.json')

def upgrade(template_name: str, target_version: Optional[int]=None, *, keep_backup: bool=False, yes: bool=False, switch_qubes: bool=True, dry_run: bool=False, confirm_fn: Callable[[str], bool]=lambda msg: input(f'{msg} [y/N] ').lower() == 'y', print_fn: Callable[[str], None]=print) -> bool:
    info = get_template_info(template_name)
    distro = info['distro']
    current = info['version']
    if target_version is None:
        target_version = next_supported_version(distro, current)
        if target_version is None:
            print_fn(f'{template_name} is already at the latest supported version.')
            return True
    path = find_upgrade_path(distro, current, target_version)
    _print_plan(print_fn, template_name, distro, path)
    if not yes and (not confirm_fn('Continue?')):
        print_fn('Aborted.')
        return False
    if dry_run:
        print_fn('\n[dry-run] No changes made.')
        return True
    rollback_mgr = RollbackManager(template_name)
    _install_sigint_handler(rollback_mgr)
    for i, (hop_from, hop_to) in enumerate(zip(path[:-1], path[1:]), start=1):
        print_fn(f'\n[{i}/{len(path) - 1}] Upgrading {distro}-{hop_from} → {distro}-{hop_to}')
        sm = StateMachine(template=template_name, hop_from=hop_from, hop_to=hop_to)
        sm.save(STATE_FILE)
        pkgs_before = packages.capture(template_name)
        _run_hop(template=template_name, distro=distro, hop_from=hop_from, hop_to=hop_to, rollback_mgr=rollback_mgr, state=sm, keep_backup=keep_backup, confirm_fn=confirm_fn if not yes else lambda _: True, print_fn=print_fn)
        pkgs_after = packages.capture(template_name)
        delta = packages.diff(pkgs_before, pkgs_after)
        print_fn(f'\n  Package changes:\n{delta.summary()}')
    _set_template_features(template_name, distro, target_version)
    if switch_qubes and (not yes):
        _offer_switch_qubes(template_name, confirm_fn, print_fn)
    elif switch_qubes and yes:
        _switch_all_qubes(template_name, print_fn)
    STATE_FILE.unlink(missing_ok=True)
    print_fn(f'\nUpgrade complete. {template_name} is now running {distro}-{target_version}.')
    return True

def _run_hop(template: str, distro: str, hop_from: int, hop_to: int, rollback_mgr: RollbackManager, state: StateMachine, keep_backup: bool, confirm_fn: Callable[[str], bool], print_fn: Callable[[str], None]) -> None:
    cache: Optional[disk.CacheDisk] = None
    snapshot: Optional[Snapshot] = None
    try:
        print_fn(f'  [1/4] Creating snapshot…')
        snapshot = rollback_mgr.create_snapshot(hop_from)
        state.advance(Step.CHECKPOINT_CREATED)
        state.save(STATE_FILE)
        print_fn(f'  [2/4] Allocating cache disk…')
        cache = disk.allocate()
        runner.start_template(template)
        disk.attach(cache, template)
        state.advance(Step.CACHE_READY)
        state.save(STATE_FILE)
        print_fn(f'  [3/4] Running upgrade agent (this may take 10–30 min)…')
        state.advance(Step.AGENT_RUNNING)
        state.save(STATE_FILE)
        exit_code = _run_agent_with_retry(template=template, distro=distro, hop_to=hop_to, cache=cache, confirm_fn=confirm_fn, print_fn=print_fn)
        if exit_code != 0:
            raise AgentError(f'Agent exited with code {exit_code}', exit_code=exit_code)
        state.advance(Step.AGENT_SUCCEEDED)
        state.save(STATE_FILE)
        print_fn(f'  [4/4] Verifying upgrade…')
        _verify(template, distro, hop_to)
        runner.shutdown_template(template)
        disk.cleanup(cache, template)
        cache = None
        state.advance(Step.CLEANED_UP)
        state.save(STATE_FILE)
        if not keep_backup:
            rollback_mgr.commit(snapshot)
        print_fn(f'  ✓ Hop {hop_from} → {hop_to} complete.')
    except (UpgradeError, KeyboardInterrupt) as exc:
        print_fn(f'\n  ✗ Hop {hop_from} → {hop_to} failed: {exc}')
        _emergency_cleanup(cache, template)
        if snapshot:
            restored = rollback_mgr.restore(snapshot)
            print_fn(f'  Rolled back to {distro}-{restored}.')
        raise

def _run_agent_with_retry(template: str, distro: str, hop_to: int, cache: disk.CacheDisk, confirm_fn: Callable[[str], bool], print_fn: Callable[[str], None]) -> int:
    agent_path = AGENTS_DIR / f'{distro}.sh'
    env_vars = {'TARGET_VERSION': str(hop_to), 'CACHE_MOUNT': disk.TEMPLATE_MOUNT_POINT, 'BLOCK_DEV': '/dev/xvdi'}
    if distro == 'debian':
        env_vars['TARGET_CODENAME'] = DEBIAN_CODENAMES[hop_to]
    sched = RetryScheduler(max_attempts=3)
    sched.schedule('agent', attempt=0)
    while not sched.is_empty():
        item = sched.next_ready()
        if item is None:
            wait = sched.seconds_until_next() or 0.1
            time.sleep(min(wait, 0.5))
            continue
        _, attempt = item
        exit_code = runner.run_agent(template, agent_path, env_vars)
        if exit_code == 0:
            return 0
        if exit_code == 28:
            raise DiskSpaceError(needed_mb=512)
        if exit_code in (1, 6, 35):
            if sched.has_budget(attempt + 1):
                print_fn(f'  ⚠ Network error (attempt {attempt + 1}) — retrying…')
                sched.schedule('agent', attempt=attempt + 1)
            else:
                raise MaxRetriesExceeded(f'Agent failed {attempt + 1} times. Last exit code: {exit_code}')
        else:
            return exit_code
    return 1

def _verify(template: str, distro: str, expected_version: int) -> None:
    result = runner.run_cmd(template, "cat /etc/os-release | grep '^VERSION_ID='", timeout=15)
    if not result.ok:
        raise VerificationError(expected_version, -1)
    for line in result.stdout.splitlines():
        if line.startswith('VERSION_ID='):
            raw = line.split('=', 1)[1].strip().strip('"')
            try:
                actual = int(raw.split('.')[0])
                if actual != expected_version:
                    raise VerificationError(expected_version, actual)
                return
            except ValueError:
                pass
    raise VerificationError(expected_version, -1)

def _set_template_features(template: str, distro: str, version: int) -> None:
    feature_name = f'{distro}-{version}'
    subprocess.run(['qvm-features', template, 'template-name', feature_name], check=True)
    log.info('Set template-name feature: %s', feature_name)

def _offer_switch_qubes(template: str, confirm_fn: Callable[[str], bool], print_fn: Callable[[str], None]) -> None:
    qubes = _find_qubes_using(template)
    if not qubes:
        return
    names = ', '.join(qubes)
    if confirm_fn(f'\nSwitch {names} to use {template}?'):
        _switch_all_qubes(template, print_fn)

def _switch_all_qubes(template: str, print_fn: Callable[[str], None]) -> None:
    qubes = _find_qubes_using(template)
    for qube in qubes:
        subprocess.run(['qvm-prefs', qube, 'template', template], check=True)
        print_fn(f'  Switched: {qube}')

def _find_qubes_using(template: str) -> list[str]:
    result = subprocess.run(['qvm-ls', '--raw-list', '--fields', 'NAME,TEMPLATE'], capture_output=True, text=True)
    qubes = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[1].strip() == template:
            qubes.append(parts[0])
    return qubes

def _emergency_cleanup(cache: Optional[disk.CacheDisk], template: str) -> None:
    if cache:
        try:
            disk.cleanup(cache, template)
        except Exception as e:
            log.warning('Emergency cache cleanup failed: %s', e)

def _print_plan(print_fn: Callable[[str], None], template: str, distro: str, path: list[int]) -> None:
    hops = ' → '.join((f'{distro}-{v}' for v in path))
    print_fn(f'\nUpgrade plan for {template}:')
    print_fn(f'  Path:  {hops}')
    print_fn(f'  Hops:  {len(path) - 1}')
    print_fn(f'\nThis will:')
    print_fn(f'  1. Create a snapshot clone before each hop')
    print_fn(f'  2. Attach a 5 GB temporary cache disk')
    print_fn(f'  3. Run the distro upgrade agent inside the template')
    print_fn(f'  4. Verify the new version, then clean up')

def _install_sigint_handler(rollback_mgr: RollbackManager) -> None:

    def _handler(sig: int, frame: object) -> None:
        log.warning('SIGINT received — initiating rollback')
        snaps = rollback_mgr.current_snapshots()
        if snaps:
            rollback_mgr.restore(snaps[-1])
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, _handler)
