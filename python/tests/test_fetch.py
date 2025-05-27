# This file will contain tests for the fetch module.

import pytest
from unittest.mock import patch, mock_open, Mock
import sys # Required for capsys and potentially sys.path manipulation
import time # Required for time.monotonic tests

# Attempt to import from ghostmirror. If ghostmirror is not directly in PYTHONPATH,
# this might require adjustment based on how pytest discovers packages.
try:
    from ghostmirror import fetch
    import requests # For requests.RequestException
except ImportError:
    from pathlib import Path
    # Add the 'python' directory to sys.path to find 'ghostmirror'
    project_root = Path(__file__).parent.parent.parent / 'python'
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from ghostmirror import fetch
    import requests # For requests.RequestException


# Tests for load_mirrorlist_from_url
@patch('ghostmirror.fetch.requests.get')
def test_load_url_success(mock_get, capsys):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = "mirrorlist content"
    mock_get.return_value = mock_response
    
    content = fetch.load_mirrorlist_from_url("http://example.com/mirrorlist", 5)
    assert content == "mirrorlist content"
    mock_get.assert_called_once_with("http://example.com/mirrorlist", timeout=5)
    
    # Check no error output to stderr
    captured = capsys.readouterr()
    assert captured.err == ""

@patch('ghostmirror.fetch.requests.get')
def test_load_url_http_error(mock_get, capsys):
    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"
    mock_get.return_value = mock_response
    
    content = fetch.load_mirrorlist_from_url("http://example.com/mirrorlist", 5)
    assert content is None
    
    captured = capsys.readouterr()
    assert "Error: Failed to fetch mirrorlist from http://example.com/mirrorlist. Status code: 404" in captured.err

@patch('ghostmirror.fetch.requests.get')
def test_load_url_request_exception(mock_get, capsys):
    mock_get.side_effect = requests.RequestException("Connection error")
    
    content = fetch.load_mirrorlist_from_url("http://example.com/mirrorlist", 5)
    assert content is None
    
    captured = capsys.readouterr()
    assert "Error: Failed to fetch mirrorlist from http://example.com/mirrorlist. Exception: Connection error" in captured.err

# Tests for load_mirrorlist_from_file
@patch('builtins.open', new_callable=mock_open, read_data="file content")
def test_load_file_success(mock_file_open, capsys):
    content = fetch.load_mirrorlist_from_file("/path/to/mirrorlist")
    assert content == "file content"
    mock_file_open.assert_called_once_with("/path/to/mirrorlist", 'r')
    
    captured = capsys.readouterr()
    assert captured.err == ""

@patch('builtins.open', side_effect=IOError("File not found"))
def test_load_file_io_error(mock_file_open, capsys):
    content = fetch.load_mirrorlist_from_file("/path/to/mirrorlist")
    assert content is None
    
    captured = capsys.readouterr()
    assert "Error: Failed to read mirrorlist from /path/to/mirrorlist. Exception: File not found" in captured.err

# Tests for fetch_database_archive
@patch('ghostmirror.fetch.requests.get')
def test_fetch_db_success(mock_get, capsys):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b"db content"
    mock_get.return_value = mock_response
    
    content = fetch.fetch_database_archive("http://mirror.com/$repo/os/$arch", "core", "x86_64", 5)
    assert content == b"db content"
    mock_get.assert_called_once_with("http://mirror.com/core/os/x86_64/core.db.tar.gz", timeout=5, stream=True)

    captured = capsys.readouterr()
    assert captured.err == ""

@patch('ghostmirror.fetch.requests.get')
def test_fetch_db_http_error(mock_get, capsys):
    mock_response = Mock()
    mock_response.status_code = 500
    mock_get.return_value = mock_response
    
    content = fetch.fetch_database_archive("http://mirror.com/$repo/os/$arch", "core", "x86_64", 5)
    assert content is None
    
    captured = capsys.readouterr()
    assert "Error: Failed to fetch database from http://mirror.com/core/os/x86_64/core.db.tar.gz. Status code: 500" in captured.err

@patch('ghostmirror.fetch.requests.get')
def test_fetch_db_request_exception(mock_get, capsys):
    mock_get.side_effect = requests.RequestException("Network issue")
    
    content = fetch.fetch_database_archive("http://mirror.com/$repo/os/$arch", "core", "x86_64", 5)
    assert content is None
    
    captured = capsys.readouterr()
    assert "Error: Failed to fetch database from http://mirror.com/core/os/x86_64/core.db.tar.gz. Exception: Network issue" in captured.err

@patch('ghostmirror.fetch.requests.get')
def test_fetch_db_url_construction(mock_get):
    mock_response = Mock() # Dummy response
    mock_response.status_code = 200
    mock_response.content = b"db"
    mock_get.return_value = mock_response

    # Scenario 1: URL needs trailing slash
    fetch.fetch_database_archive("http://mirror.com/archlinux/$repo/os/$arch", "extra", "i686", 5)
    mock_get.assert_called_with("http://mirror.com/archlinux/extra/os/i686/extra.db.tar.gz", timeout=5, stream=True)

    # Scenario 2: URL already has trailing slash
    fetch.fetch_database_archive("http://another.org/stuff/$repo/os/$arch/", "community", "x86_64", 5)
    mock_get.assert_called_with("http://another.org/stuff/community/os/x86_64/community.db.tar.gz", timeout=5, stream=True)
    
    # Scenario 3: URL with no $repo but $arch
    fetch.fetch_database_archive("http://static.repo.com/core/os/$arch/", "core", "x86_64", 5)
    mock_get.assert_called_with("http://static.repo.com/core/os/x86_64/core.db.tar.gz", timeout=5, stream=True)


# Tests for perform_speed_test
@patch('ghostmirror.fetch.requests.get')
@patch('ghostmirror.fetch.time.monotonic')
def test_perform_speed_success(mock_time_monotonic, mock_requests_get, capsys):
    # Setup mock for requests.get
    mock_response = Mock()
    mock_response.status_code = 200
    # Simulate iter_content chunks
    chunks = [b'a' * 8192, b'b' * 8192, b'c' * 2048] # Total 18432 bytes
    mock_response.iter_content.return_value = chunks
    mock_requests_get.return_value = mock_response
    
    # Setup mock for time.monotonic
    mock_time_monotonic.side_effect = [1000.0, 1002.0] # Start time, End time
    
    result = fetch.perform_speed_test("http://speedtest.com/file.dat", 10)
    
    assert result is not None
    bytes_downloaded, duration_seconds = result
    assert bytes_downloaded == 18432
    assert duration_seconds == pytest.approx(2.0)
    
    mock_requests_get.assert_called_once_with("http://speedtest.com/file.dat", stream=True, timeout=10)
    mock_response.raise_for_status.assert_called_once()
    mock_response.iter_content.assert_called_once_with(chunk_size=8192)
    
    captured = capsys.readouterr()
    assert captured.err == ""


@patch('ghostmirror.fetch.requests.get')
@patch('ghostmirror.fetch.time.monotonic') # Added monotonic mock for consistency, though not strictly used if get fails first
def test_perform_speed_http_error(mock_time_monotonic, mock_requests_get, capsys):
    mock_response = Mock()
    mock_response.status_code = 404
    # Configure raise_for_status to raise an HTTPError for 404
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Client Error")
    mock_requests_get.return_value = mock_response
    
    # time.monotonic won't be called if raise_for_status fails before iter_content
    mock_time_monotonic.return_value = 1000.0 # Only start time might be called

    result = fetch.perform_speed_test("http://speedtest.com/notfound.dat", 10)
    assert result is None
    
    captured = capsys.readouterr()
    assert "Speed test failed for http://speedtest.com/notfound.dat: 404 Client Error" in captured.err

@patch('ghostmirror.fetch.requests.get')
@patch('ghostmirror.fetch.time.monotonic')
def test_perform_speed_zero_bytes(mock_time_monotonic, mock_requests_get, capsys):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.iter_content.return_value = [] # No chunks
    mock_requests_get.return_value = mock_response
    
    mock_time_monotonic.side_effect = [1000.0, 1001.0] # Start and end time

    result = fetch.perform_speed_test("http://speedtest.com/emptyfile.dat", 10)
    assert result is None # Should return None as per function logic
    
    captured = capsys.readouterr()
    assert "Warning: Speed test for http://speedtest.com/emptyfile.dat resulted in 0 bytes downloaded." in captured.err

@patch('ghostmirror.fetch.requests.get')
@patch('ghostmirror.fetch.time.monotonic')
def test_perform_speed_zero_duration(mock_time_monotonic, mock_requests_get, capsys):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.iter_content.return_value = [b'a' * 100] # Some bytes
    mock_requests_get.return_value = mock_response
    
    mock_time_monotonic.side_effect = [1000.0, 1000.0] # Start and end time are the same

    result = fetch.perform_speed_test("http://speedtest.com/fastfile.dat", 10)
    assert result is not None
    bytes_downloaded, duration_seconds = result
    assert bytes_downloaded == 100
    assert duration_seconds == 1e-6 # Should be adjusted from 0.0

    captured = capsys.readouterr()
    assert captured.err == ""

pass # Final pass for the file.
