# This file will contain tests for the parse module.

import pytest
import io
import tarfile
import gzip

# Attempt to import from ghostmirror.parse. If ghostmirror is not directly in PYTHONPATH,
# this might require adjustment based on how pytest discovers packages.
# Assuming standard project structure where 'python' is the root for 'ghostmirror' package.
try:
    from ghostmirror import parse
except ImportError:
    # This is a fallback if the above fails, common in some pytest setups
    # or if 'python' directory itself is not added to sys.path by the test runner.
    # For a well-structured project, the first import should ideally work.
    import sys
    from pathlib import Path
    # Add the 'python' directory to sys.path to find 'ghostmirror'
    project_root = Path(__file__).parent.parent.parent / 'python'
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from ghostmirror import parse

# More specific imports if preferred, after ensuring ghostmirror.parse is found
from ghostmirror.parse import parse_mirrorfile_content, parse_database_archive

# Test for parse_mirrorfile_content
def test_empty_input():
    assert parse_mirrorfile_content("", "x86_64", False, ["all"]) == []

def test_basic_parsing():
    content = """
## United States
Server = http://mirror.us.org/archlinux/$repo/os/$arch
## Germany
#Server = https://mirror.de.org/archlinux/$repo/os/$arch
Server = http://another.de.org/archlinux/$repo/os/$arch
"""
    expected = [
        {'url': 'http://mirror.us.org/archlinux/$repo/os/$arch', 'country': 'United States', 'arch': 'x86_64'},
        {'url': 'https://mirror.de.org/archlinux/$repo/os/$arch', 'country': 'Germany', 'arch': 'x86_64'},
        {'url': 'http://another.de.org/archlinux/$repo/os/$arch', 'country': 'Germany', 'arch': 'x86_64'},
    ]
    actual = parse_mirrorfile_content(content, "x86_64", False, ["all"])
    # A more robust comparison for lists of dicts:
    assert len(actual) == len(expected)
    for act_item, exp_item in zip(sorted(actual, key=lambda x: x['url']), sorted(expected, key=lambda x: x['url'])):
        assert act_item == exp_item

def test_uncommented_only_true():
    content = """
## United States
Server = http://mirror.us.org/archlinux/$repo/os/$arch
## Germany
#Server = https://mirror.de.org/archlinux/$repo/os/$arch 
"""
    expected = [
        {'url': 'http://mirror.us.org/archlinux/$repo/os/$arch', 'country': 'United States', 'arch': 'x86_64'},
    ]
    actual = parse_mirrorfile_content(content, "x86_64", True, ["all"])
    assert actual == expected

def test_type_filters():
    content = """
Server = http://mirror.us.org/archlinux/$repo/os/$arch
Server = https://mirror.ca.org/archlinux/$repo/os/$arch
"""
    expected_http = [{'url': 'http://mirror.us.org/archlinux/$repo/os/$arch', 'country': 'Unknown', 'arch': 'x86_64'}]
    expected_https = [{'url': 'https://mirror.ca.org/archlinux/$repo/os/$arch', 'country': 'Unknown', 'arch': 'x86_64'}]
    
    assert parse_mirrorfile_content(content, "x86_64", False, ["http"]) == expected_http
    assert parse_mirrorfile_content(content, "x86_64", False, ["https"]) == expected_https
    
    all_mirrors = parse_mirrorfile_content(content, "x86_64", False, ["all"])
    # Check content of all_mirrors more robustly if necessary, e.g. by converting to set of tuples
    assert len(all_mirrors) == 2
    # Ensure both expected mirrors are in all_mirrors
    assert expected_http[0] in all_mirrors
    assert expected_https[0] in all_mirrors


def test_no_servers():
    content = "## No servers here"
    assert parse_mirrorfile_content(content, "x86_64", False, ["all"]) == []

def test_country_carry_forward():
    content = """
## Australia
Server = http://mirror.au.org/1
Server = http://mirror.au.org/2
## New Zealand
Server = http://mirror.nz.org/1
"""
    results = parse_mirrorfile_content(content, "x86_64", False, ["all"])
    assert len(results) == 3
    assert results[0]['country'] == 'Australia'
    assert results[0]['url'] == 'http://mirror.au.org/1'
    assert results[1]['country'] == 'Australia'
    assert results[1]['url'] == 'http://mirror.au.org/2'
    assert results[2]['country'] == 'New Zealand'
    assert results[2]['url'] == 'http://mirror.nz.org/1'

# Helper function for parse_database_archive tests
def create_mock_db_tar_gz(repo_name: str, package_descs: list[tuple[str, str, str]]) -> bytes:
    mem_file = io.BytesIO()
    with tarfile.open(fileobj=mem_file, mode="w:gz") as tar_archive:
        for pkg_filename_base, pkg_name, pkg_version in package_descs:
            desc_content = f"""%FILENAME%
{pkg_filename_base}-x86_64.pkg.tar.zst

%NAME%
{pkg_name}

%VERSION%
{pkg_version}
"""
            desc_bytes = desc_content.encode('utf-8')
            
            tarinfo = tarfile.TarInfo(name=f"{pkg_filename_base}/desc") # Corrected: TarInfo name should be the member name
            tarinfo.size = len(desc_bytes)
            # Optional: Set other TarInfo attributes like time, mode if they matter for parsing logic (not typical)
            # tarinfo.mtime = int(time.time()) # Example if modification time is needed
            # tarinfo.mode = 0o644
            
            tar_archive.addfile(tarinfo, io.BytesIO(desc_bytes))
            
    mem_file.seek(0) # Rewind the buffer to the beginning before reading its value
    gzipped_bytes = mem_file.getvalue()
    mem_file.close()
    return gzipped_bytes

# Test for parse_database_archive
def test_parse_db_archive_basic():
    mock_content = create_mock_db_tar_gz("core", [
        ("linux-5.0-1", "linux", "5.0-1"),
        ("pacman-6.0-1", "pacman", "6.0-1"),
    ])
    expected_pkgs = [
        {'name': 'linux', 'version': '5.0-1'},
        {'name': 'pacman', 'version': '6.0-1'},
    ]
    actual_pkgs = parse_database_archive(mock_content, "core")
    
    # Sort both lists of dictionaries by name to ensure comparison is order-independent
    # This is important because the order of members in a tar archive is not guaranteed
    # unless explicitly controlled, and parse_database_archive might not preserve it.
    actual_pkgs_sorted = sorted(actual_pkgs, key=lambda x: x['name'])
    expected_pkgs_sorted = sorted(expected_pkgs, key=lambda x: x['name'])
    
    assert actual_pkgs_sorted == expected_pkgs_sorted

def test_parse_db_archive_empty_content():
    """Test with empty byte content."""
    assert parse_database_archive(b"", "core") == []

def test_parse_db_archive_malformed_tar():
    """Test with non-tar (but gzipped) content."""
    mem_file = io.BytesIO()
    with gzip.GzipFile(fileobj=mem_file, mode='wb') as gz_file:
        gz_file.write(b"this is not a tar file")
    malformed_content = mem_file.getvalue()
    # Expecting an empty list and an error message to stderr (not captured here)
    assert parse_database_archive(malformed_content, "core") == []

def test_parse_db_archive_no_desc_files():
    """Test with a valid tar.gz but no /desc files."""
    mem_file = io.BytesIO()
    with tarfile.open(fileobj=mem_file, mode="w:gz") as tar_archive:
        # Add a dummy file
        dummy_content = b"dummy"
        tarinfo = tarfile.TarInfo(name="some_package/PKGINFO")
        tarinfo.size = len(dummy_content)
        tar_archive.addfile(tarinfo, io.BytesIO(dummy_content))
    
    no_desc_content = mem_file.getvalue()
    assert parse_database_archive(no_desc_content, "core") == []

def test_parse_db_archive_partial_desc_content():
    """Test a desc file that's missing version or name."""
    # Missing version
    mock_content_missing_version = create_mock_db_tar_gz("core", [
        ("testpkg-1.0", "testpkg", None), # Simulate pkg_version being None
    ])
    # The create_mock_db_tar_gz helper will actually skip None for version in its template.
    # Let's create a custom desc content for this.
    
    mem_file = io.BytesIO()
    with tarfile.open(fileobj=mem_file, mode="w:gz") as tar_archive:
        desc_content_v = f"%NAME%\ntestpkg\n%FILENAME%\ntestpkg-1.0-any.pkg.tar.xz"
        desc_bytes_v = desc_content_v.encode('utf-8')
        tarinfo_v = tarfile.TarInfo(name="testpkg-1.0/desc")
        tarinfo_v.size = len(desc_bytes_v)
        tar_archive.addfile(tarinfo_v, io.BytesIO(desc_bytes_v))
    
    actual_missing_version = parse_database_archive(mem_file.getvalue(), "core")
    assert actual_missing_version == [] # Should not add package if name or version is missing

    # Missing name
    mem_file_name = io.BytesIO()
    with tarfile.open(fileobj=mem_file_name, mode="w:gz") as tar_archive:
        desc_content_n = f"%VERSION%\n1.0\n%FILENAME%\ntestpkg-1.0-any.pkg.tar.xz"
        desc_bytes_n = desc_content_n.encode('utf-8')
        tarinfo_n = tarfile.TarInfo(name="testpkg-1.0/desc")
        tarinfo_n.size = len(desc_bytes_n)
        tar_archive.addfile(tarinfo_n, io.BytesIO(desc_bytes_n))

    actual_missing_name = parse_database_archive(mem_file_name.getvalue(), "core")
    assert actual_missing_name == []
pass # Final pass for the file.
