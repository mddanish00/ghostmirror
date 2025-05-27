# This file will contain tests for the output module.

import pytest
import datetime
from unittest.mock import patch, MagicMock, call # Added call

# Attempt to import from ghostmirror. If ghostmirror is not directly in PYTHONPATH,
# this might require adjustment based on how pytest discovers packages.
try:
    from ghostmirror import output
    from ghostmirror.mirror import Mirror, MirrorStatus
except ImportError:
    from pathlib import Path
    import sys
    project_root = Path(__file__).parent.parent.parent / 'python'
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from ghostmirror import output
    from ghostmirror.mirror import Mirror, MirrorStatus

# Helper function for creating Mirror objects for output tests
def create_test_mirror_for_output(
    country: str, 
    url: str, 
    status: int, 
    outofdate: int = 0, 
    uptodate: int = 0, 
    morerecent: int = 0, 
    total_packages_in_reference: int = 0, 
    speed: float = 0.0, 
    ping: float = -1.0, 
    stability_score: float = 0.0,
    arch: str = "x86_64" # Added arch as it's a required param for Mirror
) -> Mirror:
    m = Mirror(url=url, country=country, arch=arch)
    m.status = status
    m.outofdate = outofdate
    m.uptodate = uptodate
    m.morerecent = morerecent
    m.total_packages_in_reference = total_packages_in_reference
    m.speed = speed
    m.ping = ping
    m.stability_score = stability_score
    return m

# Tests for generate_table_output
@patch('ghostmirror.output.Console')
def test_table_output_basic_structure(MockConsole):
    mock_console_instance = MockConsole.return_value # Get the instance
    
    m1 = create_test_mirror_for_output("USA", "http://m1.com", MirrorStatus.SUCCESS, uptodate=10, total_packages_in_reference=10)
    m2 = create_test_mirror_for_output("Canada", "http://m2.com", MirrorStatus.ERROR)
    mirrors = [m1, m2]
    
    output.generate_table_output(mirrors, use_colors=False, max_mirrors_to_display=None)
    
    mock_console_instance.print.assert_called_once()
    table_arg = mock_console_instance.print.call_args[0][0]
    
    assert len(table_arg.rows) == 2
    assert len(table_arg.columns) == 8 # Country, URL, Status, Outdated%, Uptodate%, Speed, Ping, Stability
    assert table_arg.columns[0].header == "Country"
    assert table_arg.columns[1].header == "Mirror URL"
    assert table_arg.columns[2].header == "Status"
    assert table_arg.columns[3].header == "Outdated %"
    assert table_arg.columns[4].header == "Uptodate %"
    assert table_arg.columns[5].header == "Speed MiB/s"
    assert table_arg.columns[6].header == "Ping ms"
    assert table_arg.columns[7].header == "Stability"


@patch('ghostmirror.output.Console')
def test_table_output_empty_list(MockConsole):
    mock_console_instance = MockConsole.return_value
    output.generate_table_output([], use_colors=False, max_mirrors_to_display=None)
    
    mock_console_instance.print.assert_called_once()
    table_arg = mock_console_instance.print.call_args[0][0]
    assert len(table_arg.rows) == 0

@patch('ghostmirror.output.Console')
def test_table_output_max_mirrors_limit(MockConsole):
    mock_console_instance = MockConsole.return_value
    mirrors = [
        create_test_mirror_for_output(f"Country{i}", f"http://m{i}.com", MirrorStatus.SUCCESS)
        for i in range(5)
    ]
    output.generate_table_output(mirrors, use_colors=False, max_mirrors_to_display=2)
    
    mock_console_instance.print.assert_called_once()
    table_arg = mock_console_instance.print.call_args[0][0]
    assert len(table_arg.rows) == 2

@patch('ghostmirror.output.Console')
def test_table_output_data_formatting(MockConsole, capsys):
    # This test is simplified due to Rich's rendering complexity.
    # We'll check that the function runs and rely on visual inspection or more
    # complex output capturing for exact cell content if needed later.
    # For now, checking row/column counts and basic values.
    mock_console_instance = MockConsole.return_value

    # Mirror with N/A values and specific percentages
    m_specific = create_test_mirror_for_output(
        "TestLand", "http://specific.com", MirrorStatus.SUCCESS,
        outofdate=10, uptodate=80, total_packages_in_reference=100, # 10% out, 80% up
        speed=0.0, # Should be N/A
        ping=-1.0, # Should be N/A
        stability_score=1.25
    )
    # Mirror with all data
    m_full = create_test_mirror_for_output(
        "FullLand", "http://full.com", MirrorStatus.ERROR, # Error status
        outofdate=5, uptodate=5, total_packages_in_reference=20, # 25% out, 25% up
        speed=12.345, ping=123.4, stability_score=0.5
    )
    
    mirrors = [m_specific, m_full]
    output.generate_table_output(mirrors, use_colors=False, max_mirrors_to_display=None)
    
    mock_console_instance.print.assert_called_once()
    table_arg = mock_console_instance.print.call_args[0][0]
    assert len(table_arg.rows) == 2

    # To check rendered content, you'd typically capture stdout with capsys
    # and assert strings. Rich's Table object itself doesn't easily expose
    # "rendered cells" before actual printing.
    # For example, if you wanted to check "N/A" for m_specific's speed:
    # (This requires printing to a string buffer or capturing stdout)
    #
    # from rich.console import Console as RichConsole # Avoid conflict with MockConsole
    # from io import StringIO
    # string_io = StringIO()
    # rich_console = RichConsole(file=string_io, width=120) # Set width to avoid unexpected wrapping
    # rich_console.print(table_arg)
    # output_str = string_io.getvalue()
    # assert "TestLand" in output_str
    # assert "N/A" in output_str # This would be a basic check for N/A presence

    # For now, this test primarily ensures the function runs with varied data
    # and the table structure (rows/cols) is as expected.
    # Deeper data validation for Rich tables often involves snapshot testing or more
    # integrated tests that capture final output.

# Tests for generate_mirrorlist_file_content
def test_mirrorlist_content_basic():
    m_success = create_test_mirror_for_output("USA", "http://m_success.com", MirrorStatus.SUCCESS, stability_score=2.0)
    m_error = create_test_mirror_for_output("Canada", "http://m_error.com", MirrorStatus.ERROR)
    mirrors = [m_success, m_error]
    
    content = output.generate_mirrorlist_file_content(mirrors, max_list_mirrors=None)
    
    assert "Server = http://m_success.com" in content
    assert "Server = http://m_error.com" not in content
    assert "# Generated by GhostMirror-Py" in content.splitlines()[0]
    
    expected_stats_comment = (f"# USA, http://m_success.com, Success, 0, 0, 0, 0, 0.00, N/A, 2.00")
    assert expected_stats_comment in content

def test_mirrorlist_content_max_mirrors():
    m1 = create_test_mirror_for_output("USA", "http://m1.com", MirrorStatus.SUCCESS)
    m2 = create_test_mirror_for_output("Canada", "http://m2.com", MirrorStatus.SUCCESS)
    m3 = create_test_mirror_for_output("Germany", "http://m3.com", MirrorStatus.SUCCESS)
    mirrors = [m1, m2, m3] # Assuming they are pre-sorted
    
    content = output.generate_mirrorlist_file_content(mirrors, max_list_mirrors=1)
    assert "Server = http://m1.com" in content
    assert "Server = http://m2.com" not in content
    assert "Server = http://m3.com" not in content

def test_mirrorlist_content_empty_list():
    content = output.generate_mirrorlist_file_content([], max_list_mirrors=None)
    assert "# Generated by GhostMirror-Py" in content
    assert "Server =" not in content

def test_mirrorlist_content_all_error_mirrors():
    m_error = create_test_mirror_for_output("USA", "http://m_error.com", MirrorStatus.ERROR)
    m_unknown = create_test_mirror_for_output("Canada", "http://m_unknown.com", MirrorStatus.UNKNOWN)
    mirrors = [m_error, m_unknown]
    
    content = output.generate_mirrorlist_file_content(mirrors, max_list_mirrors=None)
    assert "Server =" not in content

def test_mirrorlist_ping_na_format():
    m_success_ping_na = create_test_mirror_for_output(
        "TestLand", "http://pingna.com", MirrorStatus.SUCCESS, ping=-1.0
    )
    content = output.generate_mirrorlist_file_content([m_success_ping_na], None)
    
    # Check for "N/A" in the ping field of the stats comment
    # Fields: Country, URL, Status, Outdated, Uptodate, Morerecent, TotalRef, Speed, Ping, Stability
    #                                                                                  ^ N/A here
    expected_stats_comment_fragment = "0.00, N/A, 0.00" 
    # More precise: f"..., {m_success_ping_na.speed:.2f}, N/A, {m_success_ping_na.stability_score:.2f}"
    full_expected_comment = (f"# TestLand, http://pingna.com, Success, 0, 0, 0, 0, "
                             f"{m_success_ping_na.speed:.2f}, N/A, {m_success_ping_na.stability_score:.2f}")
    assert full_expected_comment in content

pass # Final pass for the file.
