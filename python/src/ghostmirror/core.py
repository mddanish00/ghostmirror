"""
This module contains the core orchestration logic for the GhostMirror tool.
It integrates functionalities from other modules (fetch, parse, country, rank, output)
to process mirror lists, evaluate mirrors, and generate results based on user
configuration.
"""

from . import fetch, parse, country, rank, output, investigation, systemd # Added systemd import
from .mirror import Mirror, MirrorStatus
import sys

def process_mirrors(config: dict) -> None:
    """
    Core function to fetch, parse, rank, and output mirror information based on
    the provided configuration.

    This function acts as the main orchestrator for GhostMirror's operations.
    It sequentially handles:
    1. Fetching the initial mirror list (from URL or local file).
    2. Parsing this list into `Mirror` objects.
    3. Handling special modes like `--country-list`.
    4. Filtering mirrors by country if specified.
    5. Processing each mirror to fetch and parse its repository databases.
    6. Building a reference package set from all successful mirrors.
    7. Comparing each mirror against this reference set.
    8. Performing speed tests if requested.
    9. Calculating stability scores.
    10. Sorting the mirrors based on specified criteria.
    11. Generating output (console table and/or mirrorlist file).

    Args:
        config (dict): A dictionary containing the application's configuration,
                       typically derived from command-line arguments. Expected keys include:
            - "mirrorfile" (str | None): Path to a local mirrorlist file. If provided,
                                         this is used instead of fetching from a URL.
            - "mirrorlist_url" (str): URL to fetch the mirrorlist from if "mirrorfile" is not set.
                                      Defaults to Arch Linux official mirrorlist.
            - "timeout" (int): Timeout in seconds for network requests. Default: 8.
            - "arch" (str): Target architecture (e.g., "x86_64"). Default: "x86_64".
            - "uncommented_only" (bool): If True, parse only uncommented server lines. Default: False.
            - "mirror_types" (list[str]): List of mirror protocols to filter by (e.g., ["http", "https"]).
                                          Default: ["all"].
            - "country_list_flag" (bool): If True, display a list of available countries and exit.
                                          Default: False.
            - "country_filter" (list[str] | None): List of countries to filter mirrors by.
                                                   Default: None (no filtering).
            - "progress" (bool): If True, print progress messages to stderr. Default: False.
            - "speed_test_mode" (str | None): Mode for speed testing ("light", "normal", "heavy", "none").
                                              Default: None (no speed test if key missing or "none").
            - "sort_fields" (list[str]): List of fields to sort mirrors by.
                                         Default: ["-stability_score", "-speed"].
            - "output_table" (bool): If True, generate and print a Rich table of results. Default: False.
            - "progress_colors" (bool): If True, use colors in the Rich table output (implies progress=True).
                                        Default: False.
            - "max_list" (int | None): Maximum number of mirrors to include in table and file outputs.
                                       Default: None (unlimited).
            - "list_output_file" (str | None): Path to save the generated mirrorlist file.
                                               "stdout" prints to console. Default: None.
    
    Side Effects:
        - Prints information, progress, warnings, and errors to `sys.stderr` or `sys.stdout`.
        - May call functions from `fetch`, `parse`, `country`, `rank`, and `output` modules,
          which can have their own side effects (e.g., network requests, file I/O).
        - Modifies `Mirror` objects in place with status and ranking data.
        - If `config["list_output_file"]` is set, writes a mirrorlist file.
    """
    # Default URL for the Arch Linux mirror list
    arch_mirror_list_url = "https://archlinux.org/mirrorlist/all/"
    raw_mirror_list_content: str | None = None

    # Step 1: Initial Mirror List Fetching
    # Decide whether to load from a local file or a URL based on config.
    if config.get("mirrorfile"):
        if config.get("progress", False): print("Info: Loading mirror list from local file...", file=sys.stderr)
        raw_mirror_list_content = fetch.load_mirrorlist_from_file(config["mirrorfile"])
    else:
        mirrorlist_url_to_use = config.get("mirrorlist_url", arch_mirror_list_url)
        if config.get("progress", False): print(f"Info: Fetching mirror list from {mirrorlist_url_to_use}...", file=sys.stderr)
        raw_mirror_list_content = fetch.load_mirrorlist_from_url(
            mirrorlist_url_to_use, 
            config.get("timeout", 8) # Default timeout if not specified
        )

    if raw_mirror_list_content is None:
        print("Error: Could not fetch or read initial mirror list. Exiting.", file=sys.stderr)
        return

    # Step 2: Parsing of Initial Mirror Data into Mirror Objects
    if config.get("progress", False): print("Info: Parsing initial mirror data...", file=sys.stderr)
    parsed_data_list = parse.parse_mirrorfile_content(
        raw_mirror_list_content,
        config.get("arch", "x86_64"), # Default architecture
        config.get("uncommented_only", False),
        config.get("mirror_types", ["all"]) # Default mirror types
    )

    if not parsed_data_list:
        print("Error: No mirrors found after parsing initial list. Check filters or input file. Exiting.", file=sys.stderr)
        return

    # Convert parsed dictionaries to Mirror objects
    mirrors: list[Mirror] = [
        Mirror(url=m_data['url'], country=m_data['country'], arch=m_data['arch'])
        for m_data in parsed_data_list if m_data.get('url') # Ensure URL exists
    ]

    if not mirrors:
        print("Error: No valid mirror objects created (URLs might be missing in parsed data). Exiting.", file=sys.stderr)
        return

    # Step 3: Handle Country List Option (if requested, display list and exit)
    if config.get("country_list_flag"):
        if config.get("progress", False): print("Info: Displaying country list as requested.", file=sys.stderr)
        all_countries = country.get_country_list(mirrors) # Uses adapted country.py function
        print("\n".join(sorted(all_countries))) # Print sorted list of countries to stdout
        return # Exit after displaying country list

    # Step 4: Filter by Country (if specified)
    country_filters = config.get("country_filter")
    if country_filters: # country_filter is expected to be a list of strings
        original_mirror_count = len(mirrors)
        mirrors = country.filter_mirrors_by_country(mirrors, country_filters) # Uses adapted country.py
        if config.get("progress", False):
            print(f"Info: Filtered by countries {country_filters}. Mirrors reduced from {original_mirror_count} to {len(mirrors)}.", file=sys.stderr)

    if not mirrors: # Check if any mirrors remain after filtering
        print("Error: No mirrors left after country filtering. Exiting.", file=sys.stderr)
        return

    # Step 5: Main Processing Loop - Fetch and Parse Repository Databases for each Mirror
    if config.get("progress", False): print(f"Info: Starting database processing for {len(mirrors)} mirrors...", file=sys.stderr)
    for m_obj in mirrors:
        if config.get("progress", False):
            print(f"Processing mirror: {m_obj.url} ({m_obj.country})...", file=sys.stderr)
        
        m_obj.status = MirrorStatus.UNKNOWN # Initialize/reset status for this processing run
        has_successful_repo_download_and_parse = False
        
        for repo_name in Mirror.SUPPORTED_REPOS: # Iterate through core, extra, community, etc.
            if config.get("progress", False): print(f"  Fetching {repo_name}.db.tar.gz...", file=sys.stderr)
            db_content = fetch.fetch_database_archive(m_obj.url, repo_name, m_obj.arch, config.get("timeout", 8))
            
            if db_content:
                if config.get("progress", False): print(f"  Parsing {repo_name} database...", file=sys.stderr)
                packages = parse.parse_database_archive(db_content, repo_name)
                if packages:
                    m_obj.repos[repo_name] = packages
                    has_successful_repo_download_and_parse = True
                else:
                    if config.get("progress", False): print(f"  Failed to parse {repo_name} for {m_obj.url}", file=sys.stderr)
            else:
                if config.get("progress", False): print(f"  Failed to download {repo_name} for {m_obj.url}", file=sys.stderr)
        
        # Update mirror status based on whether any repo was successfully processed
        if has_successful_repo_download_and_parse and m_obj.repos:
            m_obj.status = MirrorStatus.SUCCESS
            m_obj.total_packages = m_obj.get_total_package_count() # Store total packages found on this mirror
        else:
            m_obj.status = MirrorStatus.ERROR
            
    # Step 6: Filter out Mirrors that Errored During Database Processing
    active_mirrors = [m for m in mirrors if m.status != MirrorStatus.ERROR]
    if not active_mirrors:
        print("Error: No mirrors successfully processed (all failed fetching/parsing databases). Exiting.", file=sys.stderr)
        return
    if config.get("progress", False): print(f"Info: {len(active_mirrors)} mirrors successfully processed for databases.", file=sys.stderr)

    # Step 7: Build Reference Package Set and Compare Mirrors
    if config.get("progress", False): print("Info: Building reference package set...", file=sys.stderr)
    reference_set = rank.build_reference_package_set(active_mirrors)
    if not reference_set or not any(reference_set.values()): # Check if reference_set is effectively empty
        print("Warning: Could not build a valid reference package set. All active mirrors might be empty, incompatible, or lack supported repos. Freshness stats may be affected.", file=sys.stderr)
        # Proceeding as per plan, allowing speed tests and output even if reference is weak.

    if config.get("progress", False): print("Info: Comparing mirrors to reference set...", file=sys.stderr)
    for m_obj in active_mirrors:
        rank.compare_mirror_to_reference(m_obj, reference_set)

    # Step 8: Perform Speed Tests (if mode is not "none")
    speed_test_mode_value = config.get("speed_test_mode")
    if speed_test_mode_value and speed_test_mode_value.lower() != "none":
        if config.get("progress", False): print(f"Info: Performing speed tests (mode: {speed_test_mode_value})...", file=sys.stderr)
        for m_obj in active_mirrors:
            # Progress for individual speed test is printed by test_mirror_speed if progress is on
            rank.test_mirror_speed(m_obj, speed_test_mode_value, m_obj.arch, config.get("timeout", 8))

    # Step 9: Calculate Stability Scores
    if config.get("progress", False): print("Info: Calculating stability scores...", file=sys.stderr)
    for m_obj in active_mirrors:
        rank.calculate_mirror_stability(m_obj)

    # Step 10: Sort Mirrors
    default_sort_fields = ["-stability_score", "-speed"] # Default sort order
    sort_key_list = config.get("sort_fields", default_sort_fields)
    if not isinstance(sort_key_list, list): # Click can pass tuples for multiple options
        sort_key_list = list(sort_key_list)
    if config.get("progress", False): print(f"Info: Sorting mirrors by {sort_key_list}...", file=sys.stderr)
    sorted_mirrors = rank.sort_mirrors(active_mirrors, sort_key_list)
    
    # Step 11: Generate Output (Table and/or Mirrorlist File)
    if config.get("progress", False): print("Info: Generating output...", file=sys.stderr)
    if config.get("output_table", False):
        # Use 'progress_colors' from config for table color, default to False if not present
        output.generate_table_output(sorted_mirrors, config.get("progress_colors", False), config.get("max_list"))

    list_output_file_path = config.get("list_output_file")
    if list_output_file_path:
        file_content = output.generate_mirrorlist_file_content(sorted_mirrors, config.get("max_list"))
        if list_output_file_path.lower() == "stdout":
            print(file_content) # Print to standard output
        else:
            # Write to the specified file
            try:
                with open(list_output_file_path, "w", encoding="utf-8") as f:
                    f.write(file_content)
                if config.get("progress", False):
                    print(f"Info: Mirror list successfully written to {list_output_file_path}", file=sys.stderr)
            except IOError as e:
                print(f"Error: Could not write mirror list to file {list_output_file_path}: {e}", file=sys.stderr)

    if config.get("progress", False): print("Info: GhostMirror processing complete.", file=sys.stderr)

    # Step 12: Investigation Mode (after sorting, before final output)
    # CLI option is 'investigate_mode', ensure this key is used from config.
    investigation_cli_option = config.get("investigate_mode", []) 
    if isinstance(investigation_cli_option, tuple): # Click passes multiple options as a tuple
        investigation_cli_option = list(investigation_cli_option)
    
    if investigation_cli_option: # If the list is not empty (i.e., --investigate was used)
        if config.get("progress", False): # Optional: print only if progress is on
            print("\n--- Investigation Mode ---", file=sys.stderr) # Overall header for investigation output
        
        # reference_set was built using active_mirrors.
        # sorted_mirrors is a sorted list of active_mirrors.
        # It's consistent to investigate sorted_mirrors against that same reference_set.
        investigation.investigate_mirrors(sorted_mirrors, investigation_cli_option, reference_set)
        # The investigation.investigate_mirrors function itself prints a footer.

    # Step 13: Systemd Timer Setup (if requested and list was written to a file)
    if config.get("systemd_manage") and list_output_file_path and list_output_file_path.lower() != "stdout":
        if config.get("progress", False): 
            print(f"Info: Attempting to set up systemd timer for {list_output_file_path}...", file=sys.stderr)
        
        # Reconstruct essential CLI arguments for the service
        reconstructed_args = []
        if config.get("mirrorfile"): # If original run used a local mirrorfile
            reconstructed_args.extend(["-m", config["mirrorfile"]])
        # No need to add mirrorlist_url, as the default will be used by the service if -m is not set.

        if config.get("arch"): reconstructed_args.extend(["-a", config["arch"]])
        if config.get("uncommented_only"): reconstructed_args.append("-u")
        if config.get("mirror_types") and config["mirror_types"] != ["all"]: # Only add if not default
            for mt in config["mirror_types"]: reconstructed_args.extend(["-T", mt])

        if config.get("country_filter"):
            for c_filter in config["country_filter"]: reconstructed_args.extend(["-c", c_filter])
        
        if config.get("speed_test_mode") and config["speed_test_mode"].lower() != "none":
             reconstructed_args.extend(["-s", config["speed_test_mode"]])
        
        if config.get("sort_fields"): # Always include sort fields if specified, even if default
            for sf in config["sort_fields"]: reconstructed_args.extend(["-S", sf])

        # Crucially, the output file for the service
        reconstructed_args.extend(["-l", list_output_file_path])
        if config.get("max_list") is not None:
             reconstructed_args.extend(["-L", str(config["max_list"])])

        # Add timeout if not default
        if config.get("timeout", 8) != 8:
            reconstructed_args.extend(["-O", str(config.get("timeout"))])

        # Do not include --progress, --progress-colors, --output-table, --investigate for the service
        # --systemd-manage itself should not be included for the service's own run.
        # --systemd-time and --systemd-fixed-time are for setting up the timer, not for the service execution.

        if config.get("progress", False):
            print(f"Info: Reconstructed CLI args for systemd service: {' '.join(reconstructed_args)}", file=sys.stderr)

        if not systemd.setup_systemd_timer(config, reconstructed_args):
            print("Warning: Systemd timer setup failed. Please check logs above.", file=sys.stderr)
        # Else: setup_systemd_timer already prints success messages.
```
