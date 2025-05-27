"""
This module provides functions for parsing raw mirror list content and
repository database archives ('.db.tar.gz' files). It extracts structured
information such as mirror URLs, countries, and package details (name, version).
"""
import re
import io
import tarfile
import gzip
import sys

def parse_mirrorfile_content(
    mirrorfile_content: str, 
    target_arch: str, 
    uncommented_only: bool, 
    mirror_types: list[str]
) -> list[dict]:
    """
    Parses the raw string content of a mirror list (typically from a pacman mirrorlist file).
    It extracts server URLs, associated countries, and applies specified filters.

    The function processes the file line by line. Country declarations (e.g., "## Germany")
    are noted and applied to subsequent server lines until a new country is declared.
    Server lines (e.g., "Server = http://mirror.example.com/$repo/os/$arch") are parsed
    for their URL. Filtering based on whether mirrors are commented out and by protocol
    (HTTP, HTTPS) is supported.

    Args:
        mirrorfile_content (str): The raw string content of the mirror list.
        target_arch (str): The architecture string (e.g., "x86_64") to be associated
                           with each parsed mirror. This is stored in the output dicts.
        uncommented_only (bool): If `True`, only processes active (uncommented) `Server = ...`
                                 lines. If `False`, processes both active and commented
                                 (e.g., `#Server = ...`, `##Server = ...`) lines,
                                 stripping leading '#' characters from server definitions.
        mirror_types (list[str]): A list of strings specifying the desired mirror protocols.
                                  Valid types are 'http', 'https', or 'all'. If the list
                                  is empty or contains 'all', all mirror types matching
                                  the commenting criteria are considered. Otherwise, only
                                  mirrors matching one of the specified protocols are included.
                                  Comparison is case-insensitive.

    Returns:
        list[dict]: A list of dictionaries, where each dictionary represents a parsed mirror.
                    Each dictionary contains the following keys:
                    - 'url' (str): The URL of the mirror.
                    - 'country' (str): The country associated with the mirror. Defaults to
                                       "Unknown" if no country is specified before a server line.
                    - 'arch' (str): The `target_arch` value passed to the function.
                    Returns an empty list if no servers are found or if input is empty.
    """
    parsed_mirrors = []
    current_country = "Unknown" # Default country if a server is listed before any country comment

    # Determine effective mirror types for filtering
    if not mirror_types: # Default to 'all' if no types are specified
        effective_types = ['all']
    else:
        effective_types = [mt.lower() for mt in mirror_types] # Normalize to lowercase

    select_all = 'all' in effective_types
    select_http = 'http' in effective_types
    select_https = 'https' in effective_types

    lines = mirrorfile_content.splitlines()

    for line in lines:
        stripped_line = line.strip()

        # Regex for country detection: matches lines like "## Country Name"
        # It ensures that the line starts with "## " followed by a non-"#" and non-whitespace character,
        # to avoid matching "### Sub-comment" or "##Server = ..." as a country.
        country_match = re.match(r"^##\s+([^#\s].*)$", stripped_line)
        if country_match:
            # Further check to ensure it's not a commented server line that happens to fit the regex pattern
            if "Server =" not in stripped_line:
                current_country = country_match.group(1).strip()
                continue # Processed country line, move to the next line

        # Server Line Detection
        server_line_candidate = stripped_line
        if not uncommented_only:
            # If processing commented servers, remove all leading '#' characters
            # e.g., "###Server = ..." becomes "Server = ..."
            server_line_candidate = re.sub(r"^#+", "", stripped_line)
        
        if server_line_candidate.startswith("Server = "):
            # Extract URL part after "Server = "
            url = server_line_candidate.split("=", 1)[1].strip()

            # URL Filtering by Type (protocol)
            if not select_all: # Only apply protocol filters if 'all' is not specified
                url_lower = url.lower()
                is_http_url = url_lower.startswith("http://")
                is_https_url = url_lower.startswith("https://")

                # Determine if the current URL matches the selected protocol types
                passes_filter = False
                if select_http and select_https: # Both http and https are allowed
                    if is_http_url or is_https_url:
                        passes_filter = True
                elif select_http: # Only http is allowed
                    if is_http_url:
                        passes_filter = True
                elif select_https: # Only https is allowed
                    if is_https_url:
                        passes_filter = True
                # If neither select_http nor select_https is true (e.g., mirror_types was ['ftp']),
                # then http/https URLs should not pass. (Implicitly handled as passes_filter remains False)

                if not passes_filter:
                    continue # Skip this URL as it doesn't match the protocol filter

            parsed_mirrors.append({
                'url': url,
                'country': current_country,
                'arch': target_arch
            })

    return parsed_mirrors

def parse_database_archive(archive_content: bytes, repo_name: str) -> list[dict]:
    """
    Parses a gzipped tar archive (`.db.tar.gz`) containing repository package information.
    It extracts package names and versions from 'desc' files within the archive.

    Each package in an Arch Linux repository database archive is represented by a directory
    (e.g., "linux-5.10.0-1/"), which contains metadata files. This function specifically
    looks for the 'desc' file in each such directory to extract package details.

    Args:
        archive_content (bytes): The byte string content of the `.db.tar.gz` file.
        repo_name (str): The name of the repository (e.g., "core", "extra"). Used primarily
                         for context in error messages.

    Returns:
        list[dict]: A list of dictionaries, where each dictionary represents a package
                    and contains 'name' (str) and 'version' (str) keys.
                    Returns an empty list if the archive cannot be parsed, contains no
                    valid 'desc' files, or if `archive_content` is empty.
                    Error details during parsing are printed to `sys.stderr`.
    """
    packages = []
    
    if not archive_content: # Handle empty input gracefully
        print(f"Error: No archive content provided for repo '{repo_name}'.", file=sys.stderr)
        return packages

    try:
        # Use io.BytesIO to treat the byte string as a file-like object
        bytes_io = io.BytesIO(archive_content)
        # Open the archive for reading with gzip compression
        with tarfile.open(fileobj=bytes_io, mode="r:gz") as tar_archive:
            for member in tar_archive.getmembers():
                # We are interested in files named 'desc' located in package-specific directories
                if member.name.endswith("/desc") and member.isfile():
                    extracted_file = tar_archive.extractfile(member)
                    if extracted_file: # Ensure file extraction was successful
                        try:
                            # Decode file content, replacing errors to avoid crashes on malformed UTF-8
                            desc_content = extracted_file.read().decode('utf-8', errors='replace')
                        except Exception as e: # Catch potential decoding errors
                            print(f"Error decoding desc file {member.name} in repo '{repo_name}': {e}", file=sys.stderr)
                            continue # Skip this problematic desc file

                        pkg_name = None
                        pkg_version = None
                        
                        lines = desc_content.splitlines()
                        # Parse the desc file content:
                        # %NAME% is followed by the package name on the next line.
                        # %VERSION% is followed by the package version on the next line.
                        i = 0
                        while i < len(lines):
                            line = lines[i].strip()
                            if line == "%NAME%":
                                if i + 1 < len(lines): # Check if next line exists
                                    pkg_name = lines[i+1].strip()
                                    i += 1 # Consume the value line
                            elif line == "%VERSION%":
                                if i + 1 < len(lines): # Check if next line exists
                                    pkg_version = lines[i+1].strip()
                                    i += 1 # Consume the value line
                            
                            # Optimization: if both name and version are found, stop parsing this file
                            if pkg_name and pkg_version:
                                break
                            i += 1
                            
                        if pkg_name and pkg_version:
                            packages.append({'name': pkg_name, 'version': pkg_version})
                        # else:
                            # Optional: Log if a desc file was parsed but didn't yield both name and version.
                            # print(f"Warning: Could not extract full package details from {member.name} in {repo_name}", file=sys.stderr)
                            
    except tarfile.TarError as e: # Errors related to tar file format
        print(f"Error: Failed to open or read tar archive for repo '{repo_name}'. TarError: {e}", file=sys.stderr)
        return [] 
    except gzip.BadGzipFile as e: # Errors related to gzip decompression
        print(f"Error: Failed to decompress gzip archive for repo '{repo_name}'. BadGzipFile: {e}", file=sys.stderr)
        return []
    except Exception as e: # Catch any other unexpected errors during processing
        print(f"Error: An unexpected error occurred while parsing archive for repo '{repo_name}': {e}", file=sys.stderr)
        return []

    return packages
```
