from __future__ import annotations
import logging
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
log = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 3600

@dataclass
class RunResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def last_stderr_lines(self, n: int=20) -> str:
        return '\n'.join(self.stderr.splitlines()[-n:])

def run_cmd(template: str, command: str, timeout: int=30, user: str='root') -> RunResult:
    log.debug('qvm-run [%s] $ %s', template, command)
    result = subprocess.run(['qvm-run', '--pass-io', f'--user={user}', template, command], capture_output=True, text=True, timeout=timeout)
    return RunResult(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)

def run_agent(template: str, agent_path: Path, env_vars: dict[str, str], timeout: int=DEFAULT_TIMEOUT) -> int:
    script_content = agent_path.read_text()
    env_prefix = ' '.join((f'{k}={v}' for k, v in env_vars.items()))
    command = f'{env_prefix} bash -s'
    log.info('Running agent %s inside %s (timeout=%ds)', agent_path.name, template, timeout)
    proc = subprocess.Popen(['qvm-run', '--pass-io', '--user=root', template, command], stdin=subprocess.PIPE)
    try:
        proc.stdin.write(script_content.encode())
        proc.stdin.close()
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        log.error('Agent timed out after %d seconds — killing', timeout)
        proc.kill()
        proc.wait()
        return 124
    except KeyboardInterrupt:
        log.warning('Interrupted — sending SIGTERM to agent')
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=10)
        raise
    log.info('Agent exited with code %d', proc.returncode)
    return proc.returncode

def start_template(template: str) -> None:
    subprocess.run(['qvm-start', '--skip-if-running', template], check=True)

def shutdown_template(template: str) -> None:
    result = subprocess.run(['qvm-shutdown', '--wait', template], capture_output=True)
    if result.returncode not in (0, 1):
        log.warning('qvm-shutdown returned %d', result.returncode)
