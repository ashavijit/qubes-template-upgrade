from __future__ import annotations
import re
from dataclasses import dataclass
from .runner import RunResult, run_cmd

@dataclass(frozen=True, order=True)
class Package:
    name: str
    version: str

    def __str__(self) -> str:
        return f'{self.name}-{self.version}'

@dataclass
class PackageDelta:
    added: list[Package]
    removed: list[Package]
    upgraded: list[tuple[Package, Package]]

    @property
    def total_changed(self) -> int:
        return len(self.added) + len(self.removed) + len(self.upgraded)

    def summary(self) -> str:
        lines = [f'  Added:    {len(self.added):4d} packages', f'  Removed:  {len(self.removed):4d} packages', f'  Upgraded: {len(self.upgraded):4d} packages', f'  Total:    {self.total_changed:4d} changes']
        return '\n'.join(lines)

def capture(template: str) -> frozenset[Package]:
    result: RunResult = run_cmd(template, "rpm -qa --queryformat '%{NAME} %{VERSION}-%{RELEASE}\\n' 2>/dev/null || dpkg-query -W -f='${Package} ${Version}\\n' 2>/dev/null", timeout=60)
    if not result.ok or not result.stdout.strip():
        return frozenset()
    packages: set[Package] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            packages.add(Package(name=parts[0], version=parts[1]))
    return frozenset(packages)

def diff(before: frozenset[Package], after: frozenset[Package]) -> PackageDelta:
    names_before: dict[str, Package] = {p.name: p for p in before}
    names_after: dict[str, Package] = {p.name: p for p in after}
    name_set_before = set(names_before)
    name_set_after = set(names_after)
    added_names = name_set_after - name_set_before
    removed_names = name_set_before - name_set_after
    common_names = name_set_before & name_set_after
    added = sorted((names_after[n] for n in added_names))
    removed = sorted((names_before[n] for n in removed_names))
    upgraded = sorted(((names_before[n], names_after[n]) for n in common_names if names_before[n].version != names_after[n].version))
    return PackageDelta(added=added, removed=removed, upgraded=upgraded)
