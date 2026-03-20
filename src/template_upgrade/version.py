from __future__ import annotations
import re
import subprocess
from collections import deque
from typing import Optional
from .exceptions import VersionDetectionError, VersionPathError
SUPPORTED_HOPS: dict[str, list[tuple[int, int]]] = {'fedora': [(37, 38), (38, 39), (39, 40), (40, 41), (41, 42), (42, 43), (43, 44)], 'debian': [(11, 12), (12, 13)]}
DEBIAN_CODENAMES: dict[int, str] = {11: 'bullseye', 12: 'bookworm', 13: 'trixie'}
_TEMPLATE_NAME_RE = re.compile('^(?P<distro>fedora|debian)-(?P<version>\\d+)(?P<suffix>-.+)?$')

def parse_template_name(name: str) -> tuple[str, int]:
    m = _TEMPLATE_NAME_RE.match(name.strip())
    if not m:
        raise VersionDetectionError(f"Cannot parse template name '{name}'. Expected format: fedora-NN or debian-NN[-suffix].")
    return (m.group('distro'), int(m.group('version')))

def get_template_info(template_name: str) -> dict:
    result = subprocess.run(['qvm-features', template_name, 'template-name'], capture_output=True, text=True)
    feature_name = result.stdout.strip()
    if not feature_name:
        feature_name = template_name
    distro, version = parse_template_name(feature_name)
    return {'distro': distro, 'version': version, 'feature_name': feature_name}

def next_supported_version(distro: str, current: int) -> Optional[int]:
    for src, dst in SUPPORTED_HOPS.get(distro, []):
        if src == current:
            return dst
    return None

def find_upgrade_path(distro: str, current: int, target: int) -> list[int]:
    if current == target:
        return [current]
    graph: dict[int, list[int]] = {}
    for src, dst in SUPPORTED_HOPS.get(distro, []):
        graph.setdefault(src, []).append(dst)
    queue: deque[list[int]] = deque([[current]])
    visited: set[int] = {current}
    while queue:
        path = queue.popleft()
        node = path[-1]
        if node == target:
            return path
        for neighbour in graph.get(node, []):
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append(path + [neighbour])
    raise VersionPathError(f'No supported upgrade path from {distro}-{current} to {distro}-{target}. Check SUPPORTED_HOPS in version.py.')

def list_installed_templates(distro: Optional[str]=None) -> list[dict]:
    result = subprocess.run(['qvm-ls', '--raw-list', '--type', 'TemplateVM'], capture_output=True, text=True)
    templates = []
    for name in result.stdout.splitlines():
        name = name.strip()
        if not name:
            continue
        try:
            d, v = parse_template_name(name)
        except VersionDetectionError:
            continue
        if distro is None or d == distro:
            templates.append({'name': name, 'distro': d, 'version': v})
    return templates
