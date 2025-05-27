"""
This module provides functions for generating user-facing output, including
formatted console tables using the Rich library and pacman-compatible
mirrorlist files.
"""

from rich.table import Table
from rich.text import Text
from rich.console import Console
import datetime

from .mirror import Mirror, MirrorStatus

def generate_table_output(mirrors: list[Mirror], use_colors: bool, max_mirrors_to_display: int | None) -> None:
    """
    Generates and prints a table of mirror results to the console using Rich.

    The table displays key attributes and performance metrics for each mirror,
    such as country, URL, status, package freshness percentages, speed, ping,
    and stability score.

    Args:
        mirrors (list[Mirror]): A list of `Mirror` objects, typically pre-sorted,
                                to be displayed in the table.
        use_colors (bool): If `True`, applies colors to status text (e.g., green for
                           "Success", red for "Error") for better visual distinction.
        max_mirrors_to_display (int | None): An optional integer to limit the number
                                             of mirrors shown in the table. If `None` or
                                             less than or equal to 0, all mirrors in the
                                             list are displayed.
    
    Side Effects:
        Prints the formatted table directly to the standard output using a Rich `Console`.
    """
    console = Console() # Rich console object for printing
    table = Table(title="GhostMirror Results")

    # Define table columns with headers, styles, and justification
    table.add_column("Country", style="cyan", no_wrap=True)
    table.add_column("Mirror URL", style="magenta", overflow="fold", max_width=50) # Fold long URLs
    table.add_column("Status", justify="center")
    table.add_column("Outdated %", justify="right")
    table.add_column("Uptodate %", justify="right")
    # Future consideration: table.add_column("Morerecent %", justify="right")
    table.add_column("Speed MiB/s", justify="right")
    table.add_column("Ping ms", justify="right")
    table.add_column("Stability", justify="right")

    # Determine which mirrors to display based on the limit
    mirrors_to_show = mirrors
    if max_mirrors_to_display is not None and max_mirrors_to_display > 0:
        mirrors_to_show = mirrors[:max_mirrors_to_display]

    for mirror in mirrors_to_show:
        # Determine status text and style based on mirror.status
        status_text = ""
        style = "" # Default style (no color)
        if mirror.status == MirrorStatus.SUCCESS:
            status_text = "Success"
            if use_colors: style = "green"
        elif mirror.status == MirrorStatus.ERROR:
            status_text = "Error"
            if use_colors: style = "red"
        elif mirror.status == MirrorStatus.UNKNOWN:
            status_text = "Unknown"
            if use_colors: style = "yellow"
        elif mirror.status == MirrorStatus.COMPARE: # Typically not set for final output mirrors
            status_text = "Compare" 
            if use_colors: style = "blue"
        else:
            status_text = str(mirror.status) # Fallback for any other undefined status
        
        status_display = Text(status_text, style=style) # Use Rich Text for styling

        # Calculate and format package freshness percentages
        outdated_percent_str = "N/A"
        uptodate_percent_str = "N/A"
        if mirror.total_packages_in_reference > 0: # Avoid division by zero
            out_pct = (mirror.outofdate / mirror.total_packages_in_reference) * 100
            up_pct = (mirror.uptodate / mirror.total_packages_in_reference) * 100
            outdated_percent_str = f"{out_pct:.2f}%"
            uptodate_percent_str = f"{up_pct:.2f}%"

        # Format speed and ping values, showing "N/A" if data is unavailable
        speed_str = f"{mirror.speed:.2f}" if mirror.speed > 0 else "N/A"
        ping_str = f"{mirror.ping:.1f}" if mirror.ping >= 0 else "N/A" # Ping is -1.0 if error/untested

        # Format stability score
        stability_str = f"{mirror.stability_score:.2f}"

        # Add a row to the table with the processed data for the current mirror
        table.add_row(
            mirror.country,
            mirror.url,
            status_display,
            outdated_percent_str,
            uptodate_percent_str,
            speed_str,
            ping_str,
            stability_str
        )

    console.print(table) # Print the complete table

def generate_mirrorlist_file_content(mirrors: list[Mirror], max_list_mirrors: int | None) -> str:
    """
    Generates the content for a pacman-compatible mirrorlist file from a list of mirrors.

    Only mirrors with a status of `MirrorStatus.SUCCESS` are included in the output.
    Each mirror entry includes a comment line with detailed statistics, followed by
    the `Server = mirror_url` line. A blank line is added for readability.
    The file content includes a header with generation timestamp and field descriptions.

    Args:
        mirrors (list[Mirror]): A list of `Mirror` objects, typically pre-sorted
                                according to desired ranking.
        max_list_mirrors (int | None): An optional integer to limit the number of
                                       `Server` entries in the output file. If `None` or
                                       negative, all successful mirrors are included.

    Returns:
        str: A string formatted for a pacman mirrorlist file. This string includes
             headers, commented stats for each server, and `Server` entries.
             It is guaranteed to end with a newline character.
    """
    output_lines = []

    # Add header comments to the mirrorlist file
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    output_lines.append(f"# Generated by GhostMirror-Py on {current_time}")
    output_lines.append("# Fields in comments: Country, URL, Status, OutdatedPkgs, UptodatePkgs, MorerecentPkgs, TotalPkgsInRef, Speed MiB/s, Ping ms, StabilityScore")

    # Determine the subset of mirrors to include based on the limit
    mirrors_to_include = mirrors
    if max_list_mirrors is not None and max_list_mirrors >= 0: # max_list_mirrors=0 means no servers
        mirrors_to_include = mirrors[:max_list_mirrors]

    for mirror in mirrors_to_include:
        # Only include mirrors that were successfully processed
        if mirror.status == MirrorStatus.SUCCESS:
            # Map status code to a human-readable string
            status_str_map = {
                MirrorStatus.SUCCESS: "Success",
                MirrorStatus.ERROR: "Error", # Should not happen due to filter, but good for map completeness
                MirrorStatus.UNKNOWN: "Unknown",
                MirrorStatus.COMPARE: "Compare"
            }
            status_str = status_str_map.get(mirror.status, str(mirror.status))

            # Format ping: display "N/A" if value is -1.0 (error/untested)
            ping_display = f"{mirror.ping:.1f}" if mirror.ping >= 0 else "N/A"

            # Construct the comment line with mirror statistics
            line_comment = (
                f"# {mirror.country}, {mirror.url}, {status_str}, "
                f"{mirror.outofdate}, {mirror.uptodate}, {mirror.morerecent}, "
                f"{mirror.total_packages_in_reference}, {mirror.speed:.2f}, "
                f"{ping_display}, {mirror.stability_score:.2f}"
            )
            output_lines.append(line_comment)

            # Add the actual server line for pacman
            line_server = f"Server = {mirror.url}"
            output_lines.append(line_server)
            output_lines.append("") # Add a blank line for readability between entries

    # Join all lines into a single string.
    # The header comments ensure output_lines is never empty.
    # Always add a trailing newline for POSIX compatibility and typical mirrorlist format.
    final_content = "\n".join(output_lines) + "\n"
        
    return final_content
```
