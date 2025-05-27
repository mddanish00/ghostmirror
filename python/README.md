# GhostMirror-Py

## Purpose

GhostMirror-Py is a Python-based tool designed to rank Arch Linux pacman mirrors. It helps users find the best performing and most up-to-date mirrors by fetching mirror lists, parsing their status, testing their speed, and comparing their package databases against a reference.

## Features

*   Fetches mirror lists from URLs or local files.
*   Parses standard pacman mirrorlist formats.
*   Filters mirrors by country and protocol type (HTTP, HTTPS).
*   Optionally processes only uncommented mirrors.
*   Fetches and parses repository database files (`.db.tar.gz`) for supported repositories (core, extra, community).
*   Builds a reference package set to determine the latest versions of packages.
*   Compares each mirror's package list against the reference to determine how up-to-date it is.
*   Performs speed tests to measure download speeds.
*   Calculates a stability score for each mirror based on status, speed, and freshness.
*   Sorts mirrors based on multiple configurable fields (e.g., stability, speed, country).
*   Outputs results in a formatted table (using Rich).
*   Generates a new pacman mirrorlist file based on the ranked and filtered mirrors.
*   Supports configurable timeouts and other operational parameters.

## Dependencies

*   `click` (for command-line interface)
*   `requests` (for network requests)
*   `rich` (for rich text and formatted table output)

## Installation & Execution

### Installation

It is recommended to install the package in editable mode from within the `python` directory of the repository:

```bash
cd /path/to/repository/python
pip install -e .
```

This will install the necessary dependencies and make the `ghostmirror` command available if your Python scripts directory is in your PATH.

### Execution

You can run GhostMirror-Py using the installed script:

```bash
ghostmirror [OPTIONS]
```

Alternatively, you can run it as a module from within the `python` directory:

```bash
cd /path/to/repository/python
python -m ghostmirror.cli [OPTIONS]
```

## Command-Line Options

```
Usage: ghostmirror [OPTIONS]

  GhostMirror: Ranks pacman mirrors.

Options:
  --version                       Show the version and exit.
  -a, --arch TEXT                 select arch, default 'x86_64'
  -m, --mirrorfile PATH           use mirror file instead of downloading
                                  mirrorlist
  -c, --country TEXT              select country from mirrorlist (can be used
                                  multiple times)
  -C, --country-list              show all possible countries
  -u, --uncommented               use only uncommented mirror
  -d, --downloads INTEGER         set numbers of parallel download  [default:
                                  4]
  -O, --timeout INTEGER           set timeout in seconds for not reply mirror
                                  [default: 8]
  -p, --progress                  show progress, default false
  -P, --progress-colors           same -p but with colors for output table
  -o, --output                    enable table output
  -s, --speed [light|normal|heavy]
                                  test speed for downloading pkg:
                                  light/normal/heavy
  -S, --sort TEXT                 sort result for any of fields, multiple
                                  fields supported (e.g.,
                                  state,outofdate,speed)
  -l, --list TEXT                 create a file with list of mirrors, 'stdout'
                                  for output here
  -L, --max-list INTEGER          set max numbers of output mirrors (default:
                                  unlimited)
  -T, --type [http|https|all]...  select mirrors type: http, https, all
                                  [default: all]
  -i, --investigate [outofdate|error|all]...
                                  investigate on mirror, mode:
                                  outofdate/error/all
  -D, --systemd                   auto manager systemd.timer
  -t, --time TEXT                 specific your preferred time in hh:mm:ss for
                                  systemd timer
  -f, --fixed-time TEXT           use fixed OnCalendar for systemd timer
  -h, --help                      Show this message and exit.
```

## Examples

1.  **List all available countries from the default Arch Linux mirror list and display them:**
    ```bash
    ghostmirror --country-list
    ```

2.  **Rank mirrors from the United States and Germany, perform a 'light' speed test, show progress, display the top 10 in a table, and save them to `/etc/pacman.d/mirrorlist.new`:**
    ```bash
    sudo ghostmirror -c USA -c Germany -s light -p -o -L 10 -l /etc/pacman.d/mirrorlist.new
    ```
    *(Note: `sudo` might be needed for writing to system directories like `/etc/pacman.d/`)*

3.  **Use a local mirror file, filter for HTTPS mirrors only, sort by stability (descending) then speed (descending), and print the resulting mirrorlist to standard output:**
    ```bash
    ghostmirror -m ./my_mirrorlist.txt -T https -S -stability_score -S -speed -l stdout
    ```

This README provides a basic overview. For more advanced usage or troubleshooting, refer to the source code and specific module documentation.
