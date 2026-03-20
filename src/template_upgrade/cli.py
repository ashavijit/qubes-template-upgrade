from __future__ import annotations
import logging
import sys
import click
from . import __version__
from .exceptions import UpgradeError
from .orchestrator import upgrade
from .version import list_installed_templates, next_supported_version

@click.group(context_settings={'help_option_names': ['-h', '--help']})
@click.version_option(__version__, '-V', '--version', prog_name='qvm-template-upgrade')
@click.option('--verbose', '-v', is_flag=True, help='Show debug output.')
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING, format='%(levelname)s %(name)s: %(message)s')

@cli.command()
@click.argument('template_name')
@click.option('--target-version', '-t', type=int, default=None, help='Target version number. Default: next supported version.')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompts.')
@click.option('--keep-backup', is_flag=True, help='Keep snapshot clones after a successful upgrade.')
@click.option('--no-switch', is_flag=True, help='Do not offer to re-point app qubes to the new template.')
@click.option('--dry-run', is_flag=True, help='Print what would happen without doing anything.')
def upgrade_cmd(template_name: str, target_version: int | None, yes: bool, keep_backup: bool, no_switch: bool, dry_run: bool) -> None:
    try:
        ok = upgrade(template_name=template_name, target_version=target_version, keep_backup=keep_backup, yes=yes, switch_qubes=not no_switch, dry_run=dry_run)
        sys.exit(0 if ok else 1)
    except UpgradeError as exc:
        click.echo(f'\nError: {exc}', err=True)
        sys.exit(2)
    except KeyboardInterrupt:
        click.echo('\nAborted.', err=True)
        sys.exit(130)

@cli.command('upgrade-all')
@click.option('--fedora', 'distro', flag_value='fedora', help='Upgrade all Fedora templates.')
@click.option('--debian', 'distro', flag_value='debian', help='Upgrade all Debian templates.')
@click.option('--yes', '-y', is_flag=True)
@click.option('--keep-backup', is_flag=True)
@click.option('--dry-run', is_flag=True)
def upgrade_all(distro: str, yes: bool, keep_backup: bool, dry_run: bool) -> None:
    if not distro:
        click.echo('Specify --fedora or --debian.', err=True)
        sys.exit(1)
    templates = list_installed_templates(distro)
    if not templates:
        click.echo(f'No {distro} templates found.')
        return
    upgradeable = [t for t in templates if next_supported_version(t['distro'], t['version']) is not None]
    if not upgradeable:
        click.echo(f'All {distro} templates are at the latest supported version.')
        return
    click.echo(f'Found {len(upgradeable)} template(s) to upgrade:')
    for t in upgradeable:
        nxt = next_supported_version(t['distro'], t['version'])
        click.echo(f"  {t['name']}  →  {t['distro']}-{nxt}")
    if not yes and (not click.confirm('\nProceed?')):
        sys.exit(0)
    failed = []
    for t in upgradeable:
        click.echo(f"\n{'─' * 60}")
        try:
            upgrade(template_name=t['name'], keep_backup=keep_backup, yes=True, dry_run=dry_run)
        except UpgradeError as exc:
            click.echo(f'  Failed: {exc}', err=True)
            failed.append(t['name'])
    if failed:
        click.echo(f"\n{len(failed)} template(s) failed: {', '.join(failed)}")
        sys.exit(2)
    click.echo('\nAll templates upgraded successfully.')

@cli.command()
def list_cmd() -> None:
    all_templates = list_installed_templates()
    if not all_templates:
        click.echo('No Fedora or Debian templates found.')
        return
    click.echo(f"{'Template':<30} {'Current':>8} {'Next':>8}  Status")
    click.echo('─' * 65)
    for t in sorted(all_templates, key=lambda x: (x['distro'], x['version'])):
        nxt = next_supported_version(t['distro'], t['version'])
        status = f"→ {t['distro']}-{nxt}" if nxt else 'up to date'
        click.echo(f"{t['name']:<30} {t['version']:>8} {nxt or '—':>8}  {status}")

@cli.command()
def doctor() -> None:
    import shutil
    ok = True
    checks = [('qvm-run', 'qvm-run'), ('qvm-clone', 'qvm-clone'), ('qvm-block', 'qvm-block'), ('qvm-features', 'qvm-features'), ('qvm-ls', 'qvm-ls'), ('losetup', 'losetup'), ('truncate', 'truncate')]
    for label, cmd in checks:
        found = shutil.which(cmd) is not None
        mark = '✓' if found else '✗'
        click.echo(f'  {mark}  {label}')
        if not found:
            ok = False
    click.echo()
    if ok:
        click.echo('All checks passed.')
    else:
        click.echo('Some tools are missing. Run from dom0.', err=True)
        sys.exit(1)
cli.add_command(upgrade_cmd, name='upgrade')
cli.add_command(list_cmd, name='list')
