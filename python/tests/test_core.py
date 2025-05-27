# This file will contain tests for the core module.

import pytest
from unittest.mock import patch, mock_open, MagicMock, call
import sys # Required for capsys and potentially sys.path manipulation

# Attempt to import from ghostmirror. If ghostmirror is not directly in PYTHONPATH,
# this might require adjustment based on how pytest discovers packages.
try:
    from ghostmirror.core import process_mirrors
    from ghostmirror.mirror import Mirror, MirrorStatus
except ImportError:
    from pathlib import Path
    # Add the 'python' directory to sys.path to find 'ghostmirror'
    project_root = Path(__file__).parent.parent.parent / 'python'
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from ghostmirror.core import process_mirrors
    from ghostmirror.mirror import Mirror, MirrorStatus


@patch('ghostmirror.core.output')
@patch('ghostmirror.core.rank')
@patch('ghostmirror.core.country')
@patch('ghostmirror.core.parse')
@patch('ghostmirror.core.fetch')
def test_core_country_list_flow(m_fetch, m_parse, m_country, m_rank, m_output):
    config = {
        "country_list_flag": True, 
        "arch": "x86_64", 
        "uncommented_only": False, # Corrected key based on core.py
        "mirror_types": ["all"], 
        "timeout": 5,
        # Add other minimal keys expected by core.py if any, e.g. for mirrorlist URL fallback
        "mirrorlist_url": "http://default.com/mirrorlist", # if core.py uses it
        "mirrorfile": None # Ensure mirrorfile is not set if URL is intended
    }
    
    m_fetch.load_mirrorlist_from_url.return_value = "## Country1\nServer = http://a.com"
    m_parse.parse_mirrorfile_content.return_value = [{'url': 'http://a.com', 'country': 'Country1', 'arch': 'x86_64'}]
    # The core.py logic for country_list_flag directly uses m_country.get_country_list
    # with the list of Mirror objects. So this mock is for that direct call.
    m_country.get_country_list.return_value = ["Country1"] 
    
    process_mirrors(config)
    
    m_fetch.load_mirrorlist_from_url.assert_called_once()
    m_parse.parse_mirrorfile_content.assert_called_once()
    # The core.py, when country_list_flag is true, now directly passes Mirror objects
    # to country.get_country_list.
    m_country.get_country_list.assert_called_once()
    
    m_rank.build_reference_package_set.assert_not_called()
    m_output.generate_table_output.assert_not_called()


@patch('ghostmirror.core.output')
@patch('ghostmirror.core.rank')
@patch('ghostmirror.core.country')
@patch('ghostmirror.core.parse')
@patch('ghostmirror.core.fetch')
def test_core_full_run_table_output(m_fetch, m_parse, m_country, m_rank, m_output):
    config = {
        "arch": "x86_64", 
        "uncommented_only": False, 
        "mirror_types": ["all"], 
        "timeout": 5, 
        "speed_test_mode": "light", 
        "sort_fields": ["-speed"], 
        "output_table": True, 
        "progress": False, 
        "progress_colors": False, 
        "max_list": None,
        "mirrorfile": None, # Ensure not to use local file
        "mirrorlist_url": "http://default.com/mirrorlist",
        "country_filter": None # Ensure no country filtering for this test
    }
    
    # Mock return values for a successful run with one mirror:
    m_fetch.load_mirrorlist_from_url.return_value = "## C1\nServer = http://mock.com/$repo/os/$arch"
    # parse_mirrorfile_content returns list of dicts
    parsed_mirror_data = [{'url': 'http://mock.com/$repo/os/$arch', 'country': 'C1', 'arch': 'x86_64'}]
    m_parse.parse_mirrorfile_content.return_value = parsed_mirror_data
    
    # country.filter_mirrors_by_country is called with list[Mirror], returns list[Mirror]
    # We need to ensure that the Mirror objects passed into it are correctly handled.
    # The easiest way is to have it return its first argument if no filtering is intended.
    def mock_filter_mirrors(mirrors_list, _countries): # _countries is the filter list
        return mirrors_list
    m_country.filter_mirrors_by_country.side_effect = mock_filter_mirrors

    m_fetch.fetch_database_archive.return_value = b"db_bytes"
    m_parse.parse_database_archive.return_value = [{'name': 'pkgA', 'version': '1.0'}]
    m_rank.build_reference_package_set.return_value = {'core': {'pkgA': '1.0'}}
    
    # rank.sort_mirrors also takes list[Mirror] and returns list[Mirror]
    def mock_sort_mirrors(mirrors_list, _sort_keys):
        return mirrors_list
    m_rank.sort_mirrors.side_effect = mock_sort_mirrors
    
    process_mirrors(config)
    
    m_fetch.load_mirrorlist_from_url.assert_called_once()
    m_parse.parse_mirrorfile_content.assert_called_once()
    
    # fetch_database_archive is called for each supported repo
    # Mirror.SUPPORTED_REPOS default is ["core", "extra", "community"]
    assert m_fetch.fetch_database_archive.call_count == len(Mirror.SUPPORTED_REPOS)
    assert m_parse.parse_database_archive.call_count == len(Mirror.SUPPORTED_REPOS) # Potentially, if all fetch_db succeed
    
    m_rank.build_reference_package_set.assert_called_once()
    m_rank.compare_mirror_to_reference.assert_called_once()
    m_rank.test_mirror_speed.assert_called_once()
    m_rank.calculate_mirror_stability.assert_called_once()
    m_rank.sort_mirrors.assert_called_once()
    m_output.generate_table_output.assert_called_once()


@patch('ghostmirror.core.output')
@patch('ghostmirror.core.rank')
@patch('ghostmirror.core.country')
@patch('ghostmirror.core.parse')
@patch('ghostmirror.core.fetch')
@patch('builtins.open', new_callable=mock_open)
def test_core_full_run_file_output(mock_builtin_open, m_fetch, m_parse, m_country, m_rank, m_output):
    config = {
        "arch": "x86_64", 
        "uncommented_only": False, 
        "mirror_types": ["all"], 
        "timeout": 5, 
        "speed_test_mode": "none", # No speed test for this variant
        "sort_fields": ["-stability_score"], 
        "output_table": False, # No table output
        "list_output_file": "out.txt",
        "progress": False, 
        "progress_colors": False, 
        "max_list": None,
        "mirrorfile": None,
        "mirrorlist_url": "http://default.com/mirrorlist",
        "country_filter": None
    }

    m_fetch.load_mirrorlist_from_url.return_value = "## C1\nServer = http://mock.com/$repo/os/$arch"
    m_parse.parse_mirrorfile_content.return_value = [{'url': 'http://mock.com/$repo/os/$arch', 'country': 'C1', 'arch': 'x86_64'}]
    m_country.filter_mirrors_by_country.side_effect = lambda mirrors, countries: mirrors
    m_fetch.fetch_database_archive.return_value = b"db_bytes"
    m_parse.parse_database_archive.return_value = [{'name': 'pkgA', 'version': '1.0'}]
    m_rank.build_reference_package_set.return_value = {'core': {'pkgA': '1.0'}}
    m_rank.sort_mirrors.side_effect = lambda mirrors, sort_keys: mirrors
    
    mock_file_content = "Server = http://mock.com/core/os/x86_64"
    m_output.generate_mirrorlist_file_content.return_value = mock_file_content
    
    process_mirrors(config)
    
    m_output.generate_mirrorlist_file_content.assert_called_once()
    mock_builtin_open.assert_called_once_with("out.txt", "w", encoding="utf-8")
    mock_builtin_open().write.assert_called_once_with(mock_file_content)
    
    # Check that speed test was NOT called due to "none" mode
    m_rank.test_mirror_speed.assert_not_called()


@patch('ghostmirror.core.output')
@patch('ghostmirror.core.rank')
@patch('ghostmirror.core.country')
@patch('ghostmirror.core.parse')
@patch('ghostmirror.core.fetch')
def test_core_fetch_list_fails(m_fetch, m_parse, m_country, m_rank, m_output, capsys):
    config = {
        "timeout": 1,
        "mirrorfile": None,
        "mirrorlist_url": "http://default.com/mirrorlist", # Required for URL path
        # Other minimal defaults to avoid KeyErrors if core.py accesses them before returning
        "arch": "x86_64", "uncommented_only": False, "mirror_types": ["all"]
    }
    
    m_fetch.load_mirrorlist_from_url.return_value = None # Simulate fetch failure
    
    process_mirrors(config)
    
    m_fetch.load_mirrorlist_from_url.assert_called_once()
    m_parse.parse_mirrorfile_content.assert_not_called() # Should not be called if fetch fails
    
    captured = capsys.readouterr()
    assert "Error: Could not fetch or read mirror list." in captured.err

pass # Final pass for the file.
