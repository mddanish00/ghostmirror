"""
This module provides functions for evaluating and ranking Arch Linux mirrors.
It includes functionalities for:
- Comparing package versions.
- Building a reference set of the latest package versions from multiple mirrors.
- Comparing individual mirrors against this reference set to determine freshness.
- Testing mirror download speeds.
- Calculating a stability score for mirrors.
- Sorting mirrors based on various criteria.
"""
import sys
from .mirror import Mirror, MirrorStatus
from . import fetch # Used by test_mirror_speed

# TODO: Replace this with a more robust version comparison logic,
# potentially using a library like 'packaging.version' to correctly
# handle epochs, version parts, and release strings as per Arch Linux
# package versioning (e.g., "1:2.0.1-3" vs "2.0.1-3").
def compare_versions(version1: str, version2: str) -> int:
    """
    Compares two package version strings using simple lexicographical comparison.

    Note: This is a simplistic comparison. For full Arch Linux package version
    compatibility (including epochs, release numbers, etc.), a more sophisticated
    parser like `packaging.version.parse` should be used.

    Args:
        version1 (str): The first version string.
        version2 (str): The second version string.

    Returns:
        int:
            -  0 if `version1` is considered equal to `version2`.
            - -1 if `version1` is considered older than `version2`.
            -  1 if `version1` is considered newer than `version2`.
    """
    if version1 == version2:
        return 0
    elif version1 < version2: # Lexicographical comparison
        return -1
    else:
        return 1

def build_reference_package_set(mirrors: list[Mirror]) -> dict[str, dict[str, str]]:
    """
    Builds a reference set of the latest known versions for each package
    across all usable (non-error) mirrors.

    This function iterates through all provided mirrors, and for each package
    in each repository (e.g., 'core', 'extra'), it determines the most recent
    version available. Mirrors with a status of `MirrorStatus.ERROR` are excluded.

    Args:
        mirrors (list[Mirror]): A list of `Mirror` objects. Each mirror should have
                                its `repos` attribute populated with package data
                                and its `status` attribute set.

    Returns:
        dict[str, dict[str, str]]: A dictionary representing the reference set.
            The outer keys are repository names (str, e.g., "core").
            The inner keys are package names (str, e.g., "linux").
            The values are the latest version strings (str, e.g., "5.10.0-1") found
            for that package in that repository across all valid mirrors.
            Example: `{"core": {"linux": "5.10.0-1", "pacman": "6.0.0-1"}}`
    """
    reference_set: dict[str, dict[str, str]] = {}

    for mirror in mirrors:
        # Only consider mirrors that have been successfully processed and are not in an error state.
        if mirror.status == MirrorStatus.ERROR:
            continue # Skip mirrors that had processing errors

        for repo_name, packages_list in mirror.repos.items():
            if repo_name not in reference_set:
                reference_set[repo_name] = {} # Initialize repo if not seen before
            
            for package_data in packages_list:
                pkg_name = package_data.get('name')
                pkg_version = package_data.get('version')

                if not pkg_name or not pkg_version: # Ensure basic package data integrity
                    continue

                # If package is new to the reference set for this repo, add it.
                if pkg_name not in reference_set[repo_name]:
                    reference_set[repo_name][pkg_name] = pkg_version
                else:
                    # If package exists, compare versions and update if current mirror has a newer one.
                    current_ref_version = reference_set[repo_name][pkg_name]
                    if compare_versions(pkg_version, current_ref_version) == 1: # pkg_version is newer
                        reference_set[repo_name][pkg_name] = pkg_version
    
    return reference_set

def compare_mirror_to_reference(mirror: Mirror, reference_package_set: dict[str, dict[str, str]]):
    """
    Compares a single mirror's package versions against a pre-built reference set.
    This function updates the mirror's comparison attributes (`outofdate`, `uptodate`,
    `morerecent`, `total_packages_in_reference`) in-place.

    The comparison is done for repositories defined in `Mirror.SUPPORTED_REPOS`.
    For each such repository present in the `reference_package_set`:
    - Packages in the reference but missing on the mirror are counted as `outofdate`.
    - Packages present on both are version-compared:
        - Equal versions increment `uptodate`.
        - Mirror version older increments `outofdate`.
        - Mirror version newer increments `morerecent`.
    - If a supported repository from the reference is entirely missing on the mirror,
      all its packages are counted towards `outofdate`.

    Args:
        mirror (Mirror): The `Mirror` object to evaluate and update. Its `repos`
                         attribute (package data) and `status` are used.
                         Its `outofdate`, `uptodate`, `morerecent`, and
                         `total_packages_in_reference` attributes are modified.
        reference_package_set (dict[str, dict[str, str]]): The reference set of packages,
            as generated by `build_reference_package_set`.
    """
    # Reset comparison attributes for the mirror
    mirror.outofdate = 0
    mirror.uptodate = 0
    mirror.morerecent = 0
    mirror.total_packages_in_reference = 0 # This will be the sum of packages in relevant reference repos

    # Calculate total_packages_in_reference: sum of package counts in SUPPORTED_REPOS
    # that are actually present in the reference_package_set.
    for repo_name in Mirror.SUPPORTED_REPOS:
        if repo_name in reference_package_set:
            mirror.total_packages_in_reference += len(reference_package_set[repo_name])

    # If mirror is in an error state or has no repository data,
    # it's considered out of date for all packages it should have.
    if mirror.status == MirrorStatus.ERROR or not mirror.repos:
        mirror.outofdate = mirror.total_packages_in_reference
        return # No further comparison possible

    # Compare packages for each repository present on the mirror
    for repo_name, packages_on_mirror_list in mirror.repos.items():
        if repo_name not in Mirror.SUPPORTED_REPOS: # Only compare supported repositories
            continue

        if repo_name in reference_package_set:
            reference_repo_pkgs_dict = reference_package_set[repo_name]
            
            # Create a lookup for faster access to mirror's packages
            mirror_repo_pkgs_lookup = {
                p['name']: p['version'] 
                for p in packages_on_mirror_list 
                if p.get('name') and p.get('version') # Ensure valid package entries
            }

            # Compare each package in the reference set for this repository
            for pkg_name, ref_version in reference_repo_pkgs_dict.items():
                if pkg_name not in mirror_repo_pkgs_lookup:
                    mirror.outofdate += 1 # Package missing on mirror
                else:
                    mirror_version = mirror_repo_pkgs_lookup[pkg_name]
                    comparison_result = compare_versions(mirror_version, ref_version)
                    if comparison_result == 0:
                        mirror.uptodate += 1
                    elif comparison_result == -1: # Mirror version is older
                        mirror.outofdate += 1
                    elif comparison_result == 1: # Mirror version is newer
                        mirror.morerecent += 1
        # If repo_name (from mirror.repos) is a supported repo but NOT in reference_package_set,
        # it implies the reference set might be incomplete for this supported repo.
        # These "extra" packages on the mirror don't count towards stats against the reference.
        # This situation is typically avoided if reference_set is built from a comprehensive set of mirrors.

    # Account for whole repositories that are in SUPPORTED_REPOS and reference_package_set,
    # but are entirely missing from this mirror's `mirror.repos`.
    for repo_name_ref in Mirror.SUPPORTED_REPOS:
        if repo_name_ref in reference_package_set and repo_name_ref not in mirror.repos:
            # All packages in this reference repository are considered outofdate for this mirror
            mirror.outofdate += len(reference_package_set[repo_name_ref])
            # total_packages_in_reference for this repo was already added in the initial loop.

def test_mirror_speed(mirror: Mirror, speed_test_mode: str, arch: str, timeout: int):
    """
    Tests the download speed of a mirror by fetching a test file (typically a database archive).
    Updates the mirror's `speed` (in MiB/s) and `ping` (download duration in ms) attributes in-place.

    The specific file used for the speed test depends on `speed_test_mode`, though
    currently, all modes use the "core" repository's database file.
    The mirror's URL template is used, replacing `$repo` and `$arch`.

    Args:
        mirror (Mirror): The `Mirror` object to test. Its `url` attribute is used,
                         and `speed` and `ping` attributes are updated.
        speed_test_mode (str): Determines the file/repo to use for testing.
                               Expected values: "light", "normal", "heavy".
                               (Currently, all map to "core" repo).
        arch (str): Architecture string (e.g., "x86_64") for URL construction.
        timeout (int): Timeout in seconds for the download request.
    """
    mirror.speed = 0.0  # Default to 0.0 MiB/s
    mirror.ping = -1.0  # Default to -1.0 ms (indicating error or not tested)

    # Determine repository and file for the speed test
    # TODO: Implement differentiated file selection for "normal" and "heavy" modes.
    #       This could involve larger files or multiple files from different repos.
    if speed_test_mode in ("light", "normal", "heavy"): # Current simplification
        repo_to_test = "core"
    else: # Default for unknown modes
        repo_to_test = "core" 
        print(f"Warning: Unknown speed_test_mode '{speed_test_mode}'. Defaulting to 'light' (using {repo_to_test}.db).", file=sys.stderr)

    file_to_download = repo_to_test + ".db.tar.gz" # Standard database archive name

    # Construct Download URL from mirror's template
    base_url_template = mirror.url
    
    # Basic validation of URL template (should ideally be validated earlier)
    if "$repo" not in base_url_template or "$arch" not in base_url_template:
        print(f"Error: Mirror URL '{mirror.url}' for {mirror.country} does not appear to be a valid template. Skipping speed test.", file=sys.stderr)
        return # speed and ping remain at default error values

    processed_base_url = base_url_template.replace("$repo", repo_to_test).replace("$arch", arch)

    if not processed_base_url.endswith("/"):
        processed_base_url += "/"
    
    download_url = processed_base_url + file_to_download

    # Perform the actual download and timing using fetch.perform_speed_test
    result = fetch.perform_speed_test(download_url, timeout)

    if result is not None:
        bytes_downloaded, duration_seconds = result
        
        if duration_seconds > 0 and bytes_downloaded > 0:
            # Calculate speed in MiB/s (Megabytes per second)
            mirror.speed = (bytes_downloaded / (1024 * 1024)) / duration_seconds
        # else: speed remains 0.0 if no bytes or zero duration (after adjustment in perform_speed_test)
        
        # Note: 'ping' here is the total time taken for the test file download, not an ICMP ping.
        mirror.ping = duration_seconds * 1000  # Convert duration to milliseconds
    else:
        # fetch.perform_speed_test returned None, indicating failure.
        # mirror.speed and mirror.ping retain their default error values (0.0 and -1.0).
        # fetch.perform_speed_test already prints detailed error/warning to stderr.
        print(f"Info: Speed test failed for mirror {mirror.url} (used URL: {download_url}). Speed/ping will use default error values.", file=sys.stderr)
        # Optionally, mirror.status could be updated to ERROR here or some other flag set.

# Heuristic for stability. Can be refined.
def calculate_mirror_stability(mirror: Mirror):
    """
    Calculates a stability score for a mirror based on its processing status,
    speed test results, and package freshness.
    Updates `mirror.stability_score` in-place.

    The heuristic is as follows:
    - Base score: 0.0 if `mirror.status` is `MirrorStatus.ERROR`.
                  1.0 if the mirror was processed without fundamental errors.
    - Speed bonus: +0.5 if `mirror.speed > 0` (i.e., speed test was successful).
    - Freshness bonus: `uptodate / total_packages_in_reference` (max +1.0).
                       This ratio is added if `total_packages_in_reference > 0`.

    Args:
        mirror (Mirror): The `Mirror` object to evaluate. Its `status`, `speed`,
                         `uptodate`, and `total_packages_in_reference` attributes
                         are used. `mirror.stability_score` is updated.
    """
    mirror.stability_score = 0.0 # Initialize/reset

    if mirror.status == MirrorStatus.ERROR:
        # Mirrors that failed basic processing (e.g., couldn't fetch any db) get no score.
        return 

    # Base score for being parseable/contactable without fundamental errors.
    mirror.stability_score = 1.0 

    # Add bonus if speed test was successful (speed > 0)
    if mirror.speed > 0:
        mirror.stability_score += 0.5

    # Add bonus proportional to up-to-dateness (freshness)
    if mirror.total_packages_in_reference > 0:
        freshness_ratio = mirror.uptodate / mirror.total_packages_in_reference
        mirror.stability_score += freshness_ratio
    # If total_packages_in_reference is 0, no freshness bonus can be calculated.
    # This can happen if the reference set is empty or if the mirror's repos
    # don't align with any supported repos in the reference.
    # The base score (and potential speed bonus) will still apply.

def sort_mirrors(mirrors: list[Mirror], sort_fields: list[str]) -> list[Mirror]:
    """
    Sorts a list of Mirror objects based on specified fields and directions.

    The sorting is stable, meaning that if multiple mirrors have the same value
    for a sort key, their relative order from previous sort operations (or their
    original order if it's the first sort key) is preserved.

    Sorting is performed by applying each sort field criterion in reverse order
    of `sort_fields` list, as Python's `list.sort()` is stable.

    Args:
        mirrors (list[Mirror]): The list of `Mirror` objects to be sorted.
        sort_fields (list[str]): A list of strings, where each string is an attribute
                                 name of the `Mirror` class. Prefixing the attribute
                                 name with "-" indicates descending order.
                                 Example: `["country", "-speed"]` sorts by country
                                 ascending, then by speed descending.

    Returns:
        list[Mirror]: A new list containing the `Mirror` objects sorted according
                      to the criteria in `sort_fields`.
    """
    sorted_mirrors = list(mirrors) # Create a shallow copy to sort, preserving the original list

    # Define valid sortable attributes and their default values for handling Nones or missing attributes.
    # The default values are chosen to place "worst" or "undefined" values appropriately
    # (e.g., -infinity for speed if higher is better, +infinity for ping if lower is better).
    # Tuple: (is_numeric_type_for_potential_future_use, default_value_for_getattr)
    valid_sort_attributes = {
        "url": (False, ""),
        "country": (False, ""),
        "status": (True, MirrorStatus.ERROR), # Lower status values (like UNKNOWN=0) are "worse"
        "outofdate": (True, float('inf')),    # More outofdate packages is worse
        "uptodate": (True, float('-inf')),    # More uptodate packages is better
        "morerecent": (True, float('-inf')),  # More recent packages is better
        "speed": (True, float('-inf')),       # Higher speed is better
        "ping": (True, float('inf')),         # Lower ping is better
        "stability_score": (True, float('-inf')), # Higher stability score is better
    }

    # Iterate through sort_fields in reverse order for stable multi-key sort
    for field_specifier in reversed(sort_fields):
        is_descending = field_specifier.startswith("-")
        field_name = field_specifier[1:] if is_descending else field_specifier

        if field_name not in valid_sort_attributes:
            print(f"Warning: Unknown sort field '{field_name}'. Skipping this sort key.", file=sys.stderr)
            continue

        _is_numeric, default_val = valid_sort_attributes[field_name]

        # The key function uses getattr to fetch the sort attribute.
        # If the attribute is missing (should not happen for well-formed Mirror objects)
        # or if it's None (can happen for attributes like ping if test failed),
        # default_val is used. This ensures consistent sorting.
        sorted_mirrors.sort(key=lambda m: getattr(m, field_name, default_val), reverse=is_descending)
        
    return sorted_mirrors
```
