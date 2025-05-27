"""
This module provides functions for fetching data over the network or from local files.
It includes utilities for downloading mirror lists, repository database archives,
and performing speed tests against mirror URLs.
"""
import sys
import requests
import time

def load_mirrorlist_from_url(url: str, timeout: int) -> str | None:
    """
    Fetches the raw text content of a mirror list from a given URL.

    Args:
        url (str): The URL from which to fetch the mirror list.
        timeout (int): The maximum time (in seconds) to wait for a response from the server.

    Returns:
        str | None: The mirror list content as a string if the fetch is successful (HTTP 200).
                    Returns `None` if an HTTP error occurs (non-200 status) or if a
                    `requests.RequestException` (e.g., network error, timeout) is raised.
                    Error details are printed to `sys.stderr`.
    """
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200:
            return response.text
        else:
            # Log HTTP errors for non-200 responses
            print(f"Error: Failed to fetch mirrorlist from {url}. Status code: {response.status_code}", file=sys.stderr)
            return None
    except requests.RequestException as e:
        # Log network-related errors (e.g., DNS failure, connection refused, timeout)
        print(f"Error: Failed to fetch mirrorlist from {url}. Exception: {e}", file=sys.stderr)
        return None

def load_mirrorlist_from_file(filepath: str) -> str | None:
    """
    Loads the raw text content of a mirror list from a local file.

    Args:
        filepath (str): The path to the local file containing the mirror list.

    Returns:
        str | None: The mirror list content as a string if the file is read successfully.
                    Returns `None` if an `IOError` (e.g., file not found, permission denied)
                    occurs during file reading. Error details are printed to `sys.stderr`.
    """
    try:
        # Explicitly use 'f_handle' for file handle to avoid confusion if 'f' is used for content later
        with open(filepath, 'r', encoding='utf-8') as f_handle: # Added encoding for robustness
            return f_handle.read()
    except IOError as e:
        # Log file I/O errors
        print(f"Error: Failed to read mirrorlist from {filepath}. Exception: {e}", file=sys.stderr)
        return None

def fetch_database_archive(mirror_url: str, repo_name: str, arch: str, timeout: int) -> bytes | None:
    """
    Fetches a repository database archive file (e.g., `core.db.tar.gz`) from a mirror.
    The mirror URL can contain placeholders `$repo` and `$arch` which will be replaced.

    Args:
        mirror_url (str): The base URL of the mirror. It may include placeholders
                          `$repo` for the repository name and `$arch` for the architecture.
        repo_name (str): The name of the repository (e.g., "core", "extra").
        arch (str): The architecture string (e.g., "x86_64").
        timeout (int): The maximum time (in seconds) to wait for a response.

    Returns:
        bytes | None: The content of the database archive as a byte string if successful (HTTP 200).
                      Returns `None` if an HTTP error occurs or a `requests.RequestException` is raised.
                      Error details are printed to `sys.stderr`.
    """
    # Substitute placeholders in the URL template
    processed_url = mirror_url.replace("$repo", repo_name).replace("$arch", arch)

    # Ensure the URL path ends with a slash before appending the filename
    if not processed_url.endswith("/"):
        processed_url += "/"
    
    # Construct the full URL for the database file
    # Example: http://mirror.host.com/archlinux/core/os/x86_64/core.db.tar.gz
    full_url = processed_url + repo_name + ".db.tar.gz"

    try:
        # stream=True defers downloading the response body.
        # response.content will then download the entire body.
        # This is useful if headers need to be checked before committing to download,
        # or if iter_content() is used for chunked processing.
        response = requests.get(full_url, timeout=timeout, stream=True) 
        if response.status_code == 200:
            # response.content loads the entire response body into memory.
            # For very large files, consider response.iter_content() for chunked processing.
            return response.content
        else:
            print(f"Error: Failed to fetch database from {full_url}. Status code: {response.status_code}", file=sys.stderr)
            return None
    except requests.RequestException as e:
        print(f"Error: Failed to fetch database from {full_url}. Exception: {e}", file=sys.stderr)
        return None

def perform_speed_test(download_url: str, timeout: int) -> tuple[float, float] | None:
    """
    Performs a speed test by downloading a file from the given URL and measuring
    the time taken and bytes downloaded.

    Args:
        download_url (str): The full URL of the file to download for the speed test.
        timeout (int): The maximum time (in seconds) to wait for the download to complete.

    Returns:
        tuple[float, float] | None: A tuple `(bytes_downloaded, duration_seconds)` if the
                                    download is successful and at least one byte is received.
                                    `bytes_downloaded` is a float.
                                    `duration_seconds` is a float; if the original duration was zero
                                    (e.g., due to timer precision or extremely fast download), it's
                                    adjusted to a very small positive value (1e-6) to avoid
                                    division by zero in speed calculations.
                                    Returns `None` if any error occurs (e.g., HTTP error,
                                    network exception, or zero bytes downloaded).
                                    Error/warning details are printed to `sys.stderr`.
    """
    start_time = time.monotonic()  # Use monotonic clock for measuring duration
    total_bytes_downloaded = 0.0

    try:
        response = requests.get(download_url, stream=True, timeout=timeout)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

        # Iterate over the response data in chunks to simulate downloading
        for chunk in response.iter_content(chunk_size=8192): # 8KB chunk size
            total_bytes_downloaded += len(chunk)
        
        end_time = time.monotonic()
        duration_seconds = end_time - start_time

        # Check if any data was actually downloaded
        if total_bytes_downloaded == 0:
            print(f"Warning: Speed test for {download_url} resulted in 0 bytes downloaded.", file=sys.stderr)
            return None # Considered a failed/uninformative test

        # Handle cases where duration might be zero (e.g., very fast local server or low timer resolution)
        if duration_seconds == 0:
            duration_seconds = 1e-6  # Assign a very small duration to avoid division by zero
            
        return (total_bytes_downloaded, duration_seconds)

    except requests.RequestException as e:
        # Handles network errors, timeouts, and HTTP errors from raise_for_status()
        print(f"Speed test failed for {download_url}: {e}", file=sys.stderr)
        return None
    except Exception as e: # Catch any other unexpected errors during the process
        print(f"An unexpected error occurred during speed test for {download_url}: {e}", file=sys.stderr)
        return None
```
