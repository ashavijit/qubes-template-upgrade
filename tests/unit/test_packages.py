import pytest
from template_upgrade.packages import Package, PackageDelta, diff

def pkg(name, ver):
    return Package(name=name, version=ver)

class TestDiff:

    def test_all_same_no_changes(self):
        pkgs = frozenset([pkg('bash', '5.1'), pkg('curl', '7.88')])
        delta = diff(pkgs, pkgs)
        assert delta.added == []
        assert delta.removed == []
        assert delta.upgraded == []
        assert delta.total_changed == 0

    def test_added_packages(self):
        before = frozenset([pkg('bash', '5.1')])
        after = frozenset([pkg('bash', '5.1'), pkg('curl', '7.88')])
        delta = diff(before, after)
        assert len(delta.added) == 1
        assert delta.added[0].name == 'curl'

    def test_removed_packages(self):
        before = frozenset([pkg('bash', '5.1'), pkg('old-pkg', '1.0')])
        after = frozenset([pkg('bash', '5.1')])
        delta = diff(before, after)
        assert len(delta.removed) == 1
        assert delta.removed[0].name == 'old-pkg'

    def test_upgraded_packages(self):
        before = frozenset([pkg('bash', '5.1'), pkg('curl', '7.88')])
        after = frozenset([pkg('bash', '5.2'), pkg('curl', '8.0')])
        delta = diff(before, after)
        assert delta.added == []
        assert delta.removed == []
        assert len(delta.upgraded) == 2
        names = {b.name for b, _ in delta.upgraded}
        assert names == {'bash', 'curl'}

    def test_mixed_changes(self):
        before = frozenset([pkg('bash', '5.1'), pkg('old-lib', '1.0'), pkg('vim', '9.0')])
        after = frozenset([pkg('bash', '5.2'), pkg('new-lib', '2.0'), pkg('vim', '9.0')])
        delta = diff(before, after)
        assert len(delta.added) == 1
        assert len(delta.removed) == 1
        assert len(delta.upgraded) == 1
        assert delta.total_changed == 3

    def test_frozenset_inputs_not_mutated(self):
        before = frozenset([pkg('bash', '5.1')])
        after = frozenset([pkg('bash', '5.2')])
        _ = diff(before, after)
        assert pkg('bash', '5.1') in before

    def test_summary_string(self):
        before = frozenset([pkg('bash', '5.1')])
        after = frozenset([pkg('bash', '5.2'), pkg('curl', '7.88')])
        delta = diff(before, after)
        summary = delta.summary()
        assert 'Added' in summary
        assert 'Upgraded' in summary
