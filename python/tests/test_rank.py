# This file will contain tests for the rank module.

import pytest
from unittest.mock import patch
import sys # For capsys test

# Attempt to import from ghostmirror. If ghostmirror is not directly in PYTHONPATH,
# this might require adjustment based on how pytest discovers packages.
try:
    from ghostmirror import rank, fetch
    from ghostmirror.mirror import Mirror, MirrorStatus
except ImportError:
    from pathlib import Path
    # Add the 'python' directory to sys.path to find 'ghostmirror'
    project_root = Path(__file__).parent.parent.parent / 'python'
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from ghostmirror import rank, fetch
    from ghostmirror.mirror import Mirror, MirrorStatus

# Helper function for creating Mirror objects
def create_mock_mirror(
    url="http://mock.com", 
    country="MockCountry", 
    arch="x86_64", 
    status=MirrorStatus.UNKNOWN, 
    repos=None, 
    speed=0.0, 
    ping=-1.0, 
    outofdate=0, 
    uptodate=0, 
    morerecent=0, 
    total_packages_in_reference=0, 
    stability_score=0.0
) -> Mirror:
    m = Mirror(url, country, arch)
    m.status = status
    m.repos = repos if repos is not None else {}
    m.speed = speed
    m.ping = ping
    m.outofdate = outofdate
    m.uptodate = uptodate
    m.morerecent = morerecent
    m.total_packages_in_reference = total_packages_in_reference
    m.stability_score = stability_score
    return m

# 2. Tests for compare_versions
def test_compare_versions():
    assert rank.compare_versions("1.0", "1.0") == 0
    assert rank.compare_versions("1.0", "2.0") == -1
    assert rank.compare_versions("2.0", "1.0") == 1
    assert rank.compare_versions("1.0.1", "1.0.0") == 1
    # Add more sophisticated Arch version string tests if this function evolves
    # e.g., "1:2.0-1" vs "2.0-1"

# 3. Tests for build_reference_package_set
def test_build_ref_empty_input():
    assert rank.build_reference_package_set([]) == {}

def test_build_ref_basic():
    m1_repos = {"core": [{"name": "pkgA", "version": "1.0"}]}
    m1 = create_mock_mirror(url="m1", status=MirrorStatus.SUCCESS, repos=m1_repos)
    m2_repos = {"core": [{"name": "pkgB", "version": "1.0"}], "extra": [{"name": "pkgC", "version": "2.0"}]}
    m2 = create_mock_mirror(url="m2", status=MirrorStatus.SUCCESS, repos=m2_repos)
    
    expected_ref = {
        "core": {"pkgA": "1.0", "pkgB": "1.0"},
        "extra": {"pkgC": "2.0"}
    }
    actual_ref = rank.build_reference_package_set([m1, m2])
    assert actual_ref == expected_ref

def test_build_ref_selects_latest_version():
    m1_repos = {"core": [{"name": "pkgA", "version": "1.0"}]}
    m1 = create_mock_mirror(url="m1", status=MirrorStatus.SUCCESS, repos=m1_repos)
    m2_repos = {"core": [{"name": "pkgA", "version": "2.0"}]} # Newer version
    m2 = create_mock_mirror(url="m2", status=MirrorStatus.SUCCESS, repos=m2_repos)
    
    expected_ref = {"core": {"pkgA": "2.0"}}
    actual_ref = rank.build_reference_package_set([m1, m2])
    assert actual_ref == expected_ref

def test_build_ref_ignores_error_mirrors():
    m1_repos = {"core": [{"name": "pkgA", "version": "1.0"}]}
    m1 = create_mock_mirror(url="m1", status=MirrorStatus.ERROR, repos=m1_repos) # ERROR status
    m2_repos = {"core": [{"name": "pkgB", "version": "1.0"}]}
    m2 = create_mock_mirror(url="m2", status=MirrorStatus.SUCCESS, repos=m2_repos)

    expected_ref = {"core": {"pkgB": "1.0"}} # Only pkgB from m2
    actual_ref = rank.build_reference_package_set([m1, m2])
    assert actual_ref == expected_ref

# 4. Tests for compare_mirror_to_reference
def test_compare_mirror_results():
    reference_set = {
        "core": {"pkgA": "1.0", "pkgB": "2.0", "pkgC": "3.0"},
        "extra": {"pkgD": "1.0"}
    }
    
    # Mirror 1: All up-to-date
    m1_repos = {
        "core": [{"name": "pkgA", "version": "1.0"}, {"name": "pkgB", "version": "2.0"}, {"name": "pkgC", "version": "3.0"}],
        "extra": [{"name": "pkgD", "version": "1.0"}]
    }
    m1 = create_mock_mirror(url="m1", status=MirrorStatus.SUCCESS, repos=m1_repos)
    rank.compare_mirror_to_reference(m1, reference_set)
    assert m1.uptodate == 4
    assert m1.outofdate == 0
    assert m1.morerecent == 0
    assert m1.total_packages_in_reference == 4 # 3 in core + 1 in extra

    # Mirror 2: Some outdated, some missing, one more recent
    m2_repos = {
        "core": [{"name": "pkgA", "version": "0.9"}, {"name": "pkgC", "version": "3.1"}], # pkgA outdated, pkgB missing, pkgC morerecent
        # extra repo missing
    }
    m2 = create_mock_mirror(url="m2", status=MirrorStatus.SUCCESS, repos=m2_repos)
    rank.compare_mirror_to_reference(m2, reference_set)
    assert m2.uptodate == 0 
    assert m2.outofdate == 3 # pkgA (older), pkgB (missing from core), pkgD (missing from extra)
    assert m2.morerecent == 1 # pkgC
    assert m2.total_packages_in_reference == 4

    # Mirror 3: Error status
    m3 = create_mock_mirror(url="m3", status=MirrorStatus.ERROR, repos={}) # No repos needed as status is ERROR
    rank.compare_mirror_to_reference(m3, reference_set)
    assert m3.outofdate == 4 # All reference packages considered outofdate
    assert m3.uptodate == 0
    assert m3.morerecent == 0
    assert m3.total_packages_in_reference == 4 # Still calculated

    # Mirror 4: No relevant repos, but reference has repos
    m4_repos = {"community": [{"name": "pkgE", "version": "1.0"}]} # community not in SUPPORTED_REPOS (by default) or reference_set
    m4 = create_mock_mirror(url="m4", status=MirrorStatus.SUCCESS, repos=m4_repos)
    rank.compare_mirror_to_reference(m4, reference_set)
    assert m4.uptodate == 0
    assert m4.outofdate == 4 # All packages from core and extra in reference are missing
    assert m4.morerecent == 0
    assert m4.total_packages_in_reference == 4
    
    # Mirror 5: Has a supported repo not in reference_set (e.g. 'community')
    # This scenario means compare_mirror_to_reference won't count 'community' pkgs towards outofdate/uptodate
    # because it's not in reference_set. total_packages_in_reference remains based on reference_set.
    m5_repos = {"core": [{"name": "pkgA", "version": "1.0"}], "community": [{"name": "pkgX", "version": "1.0"}]}
    m5 = create_mock_mirror(url="m5", status=MirrorStatus.SUCCESS, repos=m5_repos)
    rank.compare_mirror_to_reference(m5, reference_set) # reference_set only has core, extra
    assert m5.uptodate == 1 # Only pkgA
    assert m5.outofdate == 3 # pkgB, pkgC from core missing, pkgD from extra missing
    assert m5.morerecent == 0
    assert m5.total_packages_in_reference == 4


# 5. Tests for test_mirror_speed
@patch('ghostmirror.fetch.perform_speed_test')
def test_test_mirror_speed_successful(mock_perform_speed_test):
    mock_perform_speed_test.return_value = (1024 * 1024, 1.0) # 1 MiB in 1.0 sec
    mirror = create_mock_mirror(url="http://test.com/$repo/os/$arch") # Ensure URL has placeholders
    
    rank.test_mirror_speed(mirror, "light", "x86_64", 5)
    
    assert mirror.speed == pytest.approx(1.0) # 1.0 MiB/s
    assert mirror.ping == pytest.approx(1000.0) # 1.0s * 1000 = 1000ms
    mock_perform_speed_test.assert_called_once_with("http://test.com/core/os/x86_64/core.db.tar.gz", 5)

@patch('ghostmirror.fetch.perform_speed_test')
def test_test_mirror_speed_failure(mock_perform_speed_test):
    mock_perform_speed_test.return_value = None
    mirror = create_mock_mirror(url="http://test.com/$repo/os/$arch")
    
    rank.test_mirror_speed(mirror, "light", "x86_64", 5)
    
    assert mirror.speed == 0.0
    assert mirror.ping == -1.0

@patch('ghostmirror.fetch.perform_speed_test')
def test_test_mirror_speed_zero_values(mock_perform_speed_test):
    mirror = create_mock_mirror(url="http://test.com/$repo/os/$arch")

    # Test 1: Zero bytes downloaded
    mock_perform_speed_test.return_value = (0, 1.0) # 0 bytes in 1.0 sec
    rank.test_mirror_speed(mirror, "light", "x86_64", 5)
    assert mirror.speed == 0.0 # perform_speed_test itself returns None if 0 bytes
    assert mirror.ping == -1.0 # So test_mirror_speed sees None

    # Test 2: Zero duration (should be handled by perform_speed_test returning small duration)
    # If perform_speed_test returns (bytes, 0), it adjusts duration to 1e-6
    mock_perform_speed_test.return_value = (1024*1024, 1e-6) # 1 MiB, effectively 0s adjusted
    rank.test_mirror_speed(mirror, "light", "x86_64", 5)
    assert mirror.speed == pytest.approx((1024*1024 / (1024*1024)) / 1e-6) # Approx 1,000,000 MiB/s
    assert mirror.ping == pytest.approx(1e-6 * 1000) # Approx 0.001 ms


# 6. Tests for calculate_mirror_stability
def test_calculate_mirror_stability_scenarios():
    # Scenario 1: Error status
    m_error = create_mock_mirror(status=MirrorStatus.ERROR)
    rank.calculate_mirror_stability(m_error)
    assert m_error.stability_score == 0.0

    # Scenario 2: Base success (no speed, no freshness data)
    m_base = create_mock_mirror(status=MirrorStatus.SUCCESS, total_packages_in_reference=0)
    rank.calculate_mirror_stability(m_base)
    assert m_base.stability_score == 1.0

    # Scenario 3: Success with speed bonus
    m_speed = create_mock_mirror(status=MirrorStatus.SUCCESS, speed=5.0, total_packages_in_reference=0)
    rank.calculate_mirror_stability(m_speed)
    assert m_speed.stability_score == 1.5 # 1.0 (base) + 0.5 (speed)

    # Scenario 4: Success with freshness bonus (100% uptodate)
    m_fresh = create_mock_mirror(status=MirrorStatus.SUCCESS, uptodate=100, total_packages_in_reference=100)
    rank.calculate_mirror_stability(m_fresh)
    assert m_fresh.stability_score == 2.0 # 1.0 (base) + 1.0 (freshness)

    # Scenario 5: Success with speed and freshness (50% uptodate)
    m_combo = create_mock_mirror(status=MirrorStatus.SUCCESS, speed=2.0, uptodate=50, total_packages_in_reference=100)
    rank.calculate_mirror_stability(m_combo)
    assert m_combo.stability_score == 2.0 # 1.0 (base) + 0.5 (speed) + 0.5 (freshness)
    
    # Scenario 6: Success, but total_packages_in_reference is 0, but has repos
    # (e.g. reference set was empty, or mirror has repos not in reference)
    m_no_ref_pkgs = create_mock_mirror(status=MirrorStatus.SUCCESS, repos={"core": [{"name": "a", "version": "1"}]}, total_packages_in_reference=0)
    rank.calculate_mirror_stability(m_no_ref_pkgs)
    assert m_no_ref_pkgs.stability_score == 1.0 # Only base score


# 7. Tests for sort_mirrors
def test_sort_mirrors_single_key():
    m1 = create_mock_mirror(url="m1", speed=10.0)
    m2 = create_mock_mirror(url="m2", speed=5.0)
    m3 = create_mock_mirror(url="m3", speed=20.0)
    mirrors = [m1, m2, m3]
    
    # Sort by speed descending
    sorted_list = rank.sort_mirrors(mirrors, ["-speed"])
    assert [m.url for m in sorted_list] == ["m3", "m1", "m2"]

    # Sort by speed ascending
    sorted_list_asc = rank.sort_mirrors(mirrors, ["speed"])
    assert [m.url for m in sorted_list_asc] == ["m2", "m1", "m3"]

def test_sort_mirrors_multiple_keys():
    m1 = create_mock_mirror(url="m1", country="USA", stability_score=1.5, speed=10)
    m2 = create_mock_mirror(url="m2", country="Canada", stability_score=2.0, speed=5)
    m3 = create_mock_mirror(url="m3", country="USA", stability_score=2.5, speed=20)
    m4 = create_mock_mirror(url="m4", country="Canada", stability_score=1.0, speed=15)
    mirrors = [m1, m2, m3, m4]

    # Sort by country (asc), then -stability_score (desc)
    sorted_list = rank.sort_mirrors(mirrors, ["country", "-stability_score"])
    # Expected: Canada (2.0), Canada (1.0), USA (2.5), USA (1.5)
    assert [m.url for m in sorted_list] == ["m2", "m4", "m3", "m1"]

def test_sort_mirrors_invalid_key(capsys):
    m1 = create_mock_mirror(url="m1")
    mirrors = [m1]
    
    sorted_list = rank.sort_mirrors(mirrors, ["invalid_field"])
    assert sorted_list == [m1] # Should return original list (or copy)
    
    captured = capsys.readouterr()
    assert "Warning: Unknown sort field 'invalid_field'. Skipping." in captured.err

pass # Final pass for the file
