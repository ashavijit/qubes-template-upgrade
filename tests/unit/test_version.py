import pytest
from template_upgrade.exceptions import VersionDetectionError, VersionPathError
from template_upgrade.version import find_upgrade_path, next_supported_version, parse_template_name

class TestParseTemplateName:

    def test_fedora_plain(self):
        assert parse_template_name('fedora-42') == ('fedora', 42)

    def test_fedora_minimal(self):
        assert parse_template_name('fedora-42-minimal') == ('fedora', 42)

    def test_debian_plain(self):
        assert parse_template_name('debian-12') == ('debian', 12)

    def test_debian_xfce(self):
        assert parse_template_name('debian-12-xfce') == ('debian', 12)

    def test_invalid_raises(self):
        with pytest.raises(VersionDetectionError):
            parse_template_name('whonix-ws-17')

    def test_empty_raises(self):
        with pytest.raises(VersionDetectionError):
            parse_template_name('')

class TestFindUpgradePath:

    def test_single_hop_fedora(self):
        assert find_upgrade_path('fedora', 42, 43) == [42, 43]

    def test_multi_hop_fedora(self):
        assert find_upgrade_path('fedora', 40, 43) == [40, 41, 42, 43]

    def test_single_hop_debian(self):
        assert find_upgrade_path('debian', 11, 12) == [11, 12]

    def test_already_at_target(self):
        assert find_upgrade_path('fedora', 43, 43) == [43]

    def test_no_path_raises(self):
        with pytest.raises(VersionPathError):
            find_upgrade_path('fedora', 43, 40)

    def test_unknown_distro_raises(self):
        with pytest.raises(VersionPathError):
            find_upgrade_path('arch', 1, 2)

    def test_bfs_returns_shortest(self):
        path = find_upgrade_path('fedora', 38, 43)
        assert path == [38, 39, 40, 41, 42, 43]
        assert len(path) == 6

class TestNextSupportedVersion:

    def test_fedora_next(self):
        assert next_supported_version('fedora', 42) == 43

    def test_debian_next(self):
        assert next_supported_version('debian', 11) == 12

    def test_at_latest_returns_none(self):
        assert next_supported_version('fedora', 44) is None

    def test_unknown_distro_returns_none(self):
        assert next_supported_version('ubuntu', 22) is None
