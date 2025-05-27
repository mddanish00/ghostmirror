"""
Provides functions for detailed investigation of mirror states,
focusing on mirrors with errors or out-of-date/more-recent packages.
"""

from .mirror import Mirror, MirrorStatus
from .rank import compare_versions # Used for comparing versions if needed, though main comparison is done by rank.py

def investigate_mirrors(
    mirrors: list[Mirror], 
    investigation_types: list[str], 
    reference_package_set: dict[str, dict[str, str]]
) -> None:
    """
    Prints detailed information about mirrors based on specified investigation types.

    Args:
        mirrors (list[Mirror]): The list of Mirror objects to investigate.
                                These are typically already processed and sorted.
        investigation_types (list[str]): A list of strings indicating the types
                                         of issues to investigate (e.g., "error",
                                         "outofdate", "all"). Case-insensitive.
        reference_package_set (dict[str, dict[str, str]]): The reference package set
                                                           used for comparison.
    """
    # Normalize investigation types to lowercase
    norm_investigation_types = [it.lower() for it in investigation_types]

    # --- "error" mode ---
    if "error" in norm_investigation_types or "all" in norm_investigation_types:
        print("\n--- Mirrors with Errors ---")
        found_error_mirrors = False
        for m in mirrors:
            if m.status == MirrorStatus.ERROR:
                print(f"Mirror: {m.url} (Country: {m.country})")
                print(f"  Status: ERROR")
                # Optionally, could print m.www_error_code or m.processing_error_type if set
                if m.www_error_code:
                    print(f"  WWW Error Code: {m.www_error_code}")
                if m.processing_error_type:
                    print(f"  Processing Error Type: {m.processing_error_type}")
                found_error_mirrors = True
        if not found_error_mirrors:
            print("No mirrors found with ERROR status.")

    # --- "outofdate" mode (includes more recent / unique on mirror) ---
    if "outofdate" in norm_investigation_types or "all" in norm_investigation_types:
        print("\n--- Mirrors with Outdated, Missing, or More Recent Packages ---")
        found_outofdate_mirrors = False
        for m in mirrors:
            # Skip mirrors that had fundamental errors, as their package data is unreliable
            if m.status == MirrorStatus.ERROR:
                continue

            if m.outofdate > 0 or m.morerecent > 0:
                found_outofdate_mirrors = True
                print(f"\nMirror: {m.url} (Country: {m.country})")
                print(f"  Overall Stats: Outdated={m.outofdate}, Uptodate={m.uptodate}, MoreRecent={m.morerecent}, RefTotal={m.total_packages_in_reference}")

                mirror_repos_lookup = {
                    repo_name: {pkg['name']: pkg['version'] for pkg in pkg_list}
                    for repo_name, pkg_list in m.repos.items()
                }

                # Check supported repos that are in the reference set
                for repo_name in Mirror.SUPPORTED_REPOS:
                    if repo_name not in reference_package_set:
                        if repo_name in mirror_repos_lookup: # Mirror has this repo, but it's not in reference
                             print(f"  Repo: {repo_name} (Present on mirror, but not in reference_package_set used for comparison)")
                        continue # Skip if repo not in reference

                    ref_repo_pkgs = reference_package_set.get(repo_name, {})
                    mirror_repo_pkgs = mirror_repos_lookup.get(repo_name, {})
                    
                    outdated_details = []
                    morerecent_details = []
                    
                    # Packages in reference, compare with mirror
                    for pkg_name, ref_version in ref_repo_pkgs.items():
                        if pkg_name not in mirror_repo_pkgs:
                            outdated_details.append(f"    - {pkg_name}: (Mirror: MISSING, Reference: {ref_version})")
                        else:
                            mirror_version = mirror_repo_pkgs[pkg_name]
                            comparison = compare_versions(mirror_version, ref_version)
                            if comparison == -1: # Mirror older
                                outdated_details.append(f"    - {pkg_name}: (Mirror: {mirror_version}, Reference: {ref_version})")
                            elif comparison == 1: # Mirror newer
                                morerecent_details.append(f"    - {pkg_name}: (Mirror: {mirror_version}, Reference: {ref_version})")
                    
                    # Packages unique to mirror (more recent implies unique in version, but this checks for packages not in ref at all for this repo)
                    # This is slightly different from "morerecent" which are packages *also* in ref but newer.
                    # The current m.morerecent counts packages *in reference* that are newer on mirror.
                    # Here we list packages on mirror not in reference at all for this repo.
                    unique_to_mirror_details = []
                    for pkg_name, mirror_version in mirror_repo_pkgs.items():
                        if pkg_name not in ref_repo_pkgs:
                             unique_to_mirror_details.append(f"    - {pkg_name}: (Mirror: {mirror_version}, Reference: N/A - Unique to mirror for this repo)")


                    if outdated_details:
                        print(f"  Repo: {repo_name} - Outdated/Missing Packages (up to 5):")
                        for detail in outdated_details[:5]: print(detail)
                    if morerecent_details:
                        print(f"  Repo: {repo_name} - More Recent Packages on Mirror (up to 5):")
                        for detail in morerecent_details[:5]: print(detail)
                    if unique_to_mirror_details: # Packages only on this mirror for this repo
                        print(f"  Repo: {repo_name} - Unique Packages on Mirror (not in reference for this repo, up to 5):")
                        for detail in unique_to_mirror_details[:5]: print(detail)
                
                # Note repos on mirror but not in SUPPORTED_REPOS (and thus not in reference_set typically)
                for repo_name in mirror_repos_lookup:
                    if repo_name not in Mirror.SUPPORTED_REPOS:
                        print(f"  Repo: {repo_name} (Present on mirror, but not in Mirror.SUPPORTED_REPOS - not typically compared)")


        if not found_outofdate_mirrors:
            print("No mirrors found with outdated, missing, or more recent packages (excluding ERROR mirrors).")

    print("\n--- End of Investigation Mode ---", file=sys.stderr) # Footer for investigation output
```
