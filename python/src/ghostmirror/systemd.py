"""
Provides functions for setting up and managing systemd user timers
for automatically updating the pacman mirrorlist using GhostMirror.
"""

import os
import pathlib
import subprocess
import sys
import shutil # For finding executable path, though sys.executable is more direct for python scripts

USER_SYSTEMD_PATH = pathlib.Path.home() / ".config/systemd/user"
SERVICE_NAME = "ghostmirror.service"
TIMER_NAME = "ghostmirror.timer"

def generate_service_file_content(executable_path: str, cli_args: list[str]) -> str:
    """
    Generates the content for the systemd service file (ghostmirror.service).

    Args:
        executable_path (str): Full path to the executable to be run.
                               For GhostMirror-Py, this is typically the Python interpreter.
        cli_args (list[str]): A list of command-line arguments to pass to the executable.
                              If `executable_path` is Python, this should include
                              "-m", "ghostmirror.cli" followed by GhostMirror-Py's arguments.
                              Example: ["-m", "ghostmirror.cli", "-l", "/path/to/mirrorlist", "-c", "US"]

    Returns:
        str: The content of the .service file as a string.
    """
    # Ensure arguments are properly quoted if they contain spaces, though Click usually handles this.
    # For ExecStart, it's generally safer if arguments are passed one by one,
    # but systemd's ExecStart handles string parsing. Here, we join them.
    # A more robust way for complex args in systemd is to use a wrapper script or pass them separately.
    # However, for typical ghostmirror args, simple join should be fine.
    
    # Correctly format ExecStart: path and then each argument separately
    # Systemd prefers arguments to be passed individually rather than as one giant string if they were to be parsed by a shell.
    # However, if the string is directly executed (Type=oneshot often does this), it's fine.
    # Let's construct it carefully.
    
    # executable_path should be the first element, followed by cli_args.
    # If executable_path is python, and cli_args starts with -m, that's standard.
    
    # For systemd, if ExecStart has multiple items, the first is the command, rest are args.
    # So, if cli_args = ["-m", "ghostmirror.cli", "--option", "value"],
    # and executable_path = "/usr/bin/python3",
    # ExecStart should look like: /usr/bin/python3 -m ghostmirror.cli --option value
    
    exec_start_parts = [executable_path] + cli_args
    exec_start_string = " ".join(exec_start_parts) # Simple space joining

    content = f"""\
[Unit]
Description=GhostMirror Pacman mirror list update service
After=network-online.target
Documentation=https://github.com/maxrd2/ghostmirror-py (Replace with actual URL if available)

[Service]
Type=oneshot
ExecStart={exec_start_string}
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"""
    # Note: [Install] section in a .service run by a timer is not strictly necessary
    # as the service isn't typically enabled directly, but doesn't hurt.
    return content

def generate_timer_file_content(on_calendar_event: str) -> str:
    """
    Generates the content for the systemd timer file (ghostmirror.timer).

    Args:
        on_calendar_event (str): The calendar event string for the OnCalendar directive
                                 (e.g., "daily", "weekly", "YYYY-MM-DD HH:MM:SS").

    Returns:
        str: The content of the .timer file as a string.
    """
    content = f"""\
[Unit]
Description=Timer for GhostMirror Pacman mirror list update
Documentation=https://github.com/maxrd2/ghostmirror-py (Replace with actual URL if available)

[Timer]
OnCalendar={on_calendar_event}
Persistent=true
Unit={SERVICE_NAME}

[Install]
WantedBy=timers.target
"""
    return content

def systemctl_cmd(*args: str) -> bool:
    """
    Helper function to run systemctl --user commands.

    Args:
        *args: Arguments to pass to systemctl (e.g., "daemon-reload").

    Returns:
        bool: True if the command was successful, False otherwise.
    """
    command = ["systemctl", "--user"] + list(args)
    try:
        # Using capture_output=True to get stdout/stderr if needed for debugging
        # Using text=True to decode stdout/stderr as strings
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error running systemctl command: {' '.join(command)}", file=sys.stderr)
            print(f"  Return code: {result.returncode}", file=sys.stderr)
            if result.stdout:
                print(f"  Stdout: {result.stdout.strip()}", file=sys.stderr)
            if result.stderr:
                print(f"  Stderr: {result.stderr.strip()}", file=sys.stderr)
            return False
        return True
    except FileNotFoundError:
        print("Error: systemctl command not found. Is systemd installed and in PATH?", file=sys.stderr)
        return False
    except Exception as e:
        print(f"An unexpected error occurred while running systemctl: {e}", file=sys.stderr)
        return False

def setup_systemd_timer(config: dict, last_used_cli_args: list[str]) -> bool:
    """
    Sets up and enables a systemd user timer for GhostMirror.

    This involves:
    1. Checking if the system is Linux.
    2. Determining the calendar event for the timer.
    3. Constructing the service and timer file contents.
    4. Writing these files to the user's systemd directory.
    5. Reloading the systemd daemon and enabling/starting the timer.

    Args:
        config (dict): The application configuration dictionary.
                       Expected keys: "systemd_fixed_time", "systemd_time".
        last_used_cli_args (list[str]): A list of CLI arguments that were used
                                        to generate the current successful mirrorlist.
                                        These will be used in the ExecStart of the service.

    Returns:
        bool: True if the timer was set up successfully, False otherwise.
    """
    if not sys.platform.startswith("linux"):
        print("Warning: Systemd timer setup is only supported on Linux. Skipping.", file=sys.stderr)
        return False

    # Determine OnCalendar event
    on_calendar_event = "daily" # Default
    if config.get("systemd_fixed_time"):
        on_calendar_event = config["systemd_fixed_time"]
    elif config.get("systemd_time"): # This was hh:mm:ss in C, systemd OnCalendar is more flexible.
                                     # For simplicity, we'll assume systemd_time is a valid OnCalendar string if provided.
                                     # Or we could format it: e.g., f"*-*-* {config['systemd_time']}"
        on_calendar_event = config["systemd_time"] 
        # A simple hh:mm:ss could be made daily by prepending '*-*-* '
        # However, the original C code seems to imply systemd_time itself is the OnCalendar string,
        # or it constructs a simple daily one. Let's assume systemd_time is a full OnCalendar string if provided.
        # If it's just "hh:mm:ss", user should specify "*-*-* hh:mm:ss" for systemd_time.

    # Determine executable path and adjust cli_args for the service
    # sys.executable is the path to the current Python interpreter
    executable_path = sys.executable
    # The service will run: /usr/bin/python3 -m ghostmirror.cli <args>
    service_cli_args = ["-m", "ghostmirror.cli"] + last_used_cli_args
    
    service_content = generate_service_file_content(executable_path, service_cli_args)
    timer_content = generate_timer_file_content(on_calendar_event)

    try:
        USER_SYSTEMD_PATH.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error: Could not create systemd user directory {USER_SYSTEMD_PATH}: {e}", file=sys.stderr)
        return False

    service_file_path = USER_SYSTEMD_PATH / SERVICE_NAME
    timer_file_path = USER_SYSTEMD_PATH / TIMER_NAME

    try:
        with open(service_file_path, "w", encoding="utf-8") as f:
            f.write(service_content)
        if config.get("progress", False): print(f"Info: Wrote systemd service file to {service_file_path}", file=sys.stderr)
        
        with open(timer_file_path, "w", encoding="utf-8") as f:
            f.write(timer_content)
        if config.get("progress", False): print(f"Info: Wrote systemd timer file to {timer_file_path}", file=sys.stderr)

    except IOError as e:
        print(f"Error: Could not write systemd files: {e}", file=sys.stderr)
        return False

    # Reload systemd daemon, then enable and start the timer
    if not systemctl_cmd("daemon-reload"):
        print("Error: Failed to reload systemd user daemon.", file=sys.stderr)
        return False
    
    # --now enables the timer and starts it immediately if its OnCalendar condition would have triggered.
    if not systemctl_cmd("enable", "--now", TIMER_NAME):
        print(f"Error: Failed to enable and start systemd timer {TIMER_NAME}.", file=sys.stderr)
        # Attempt to disable if enable failed, to clean up potentially partially enabled timer
        systemctl_cmd("disable", TIMER_NAME) 
        return False

    print(f"Info: Systemd timer '{TIMER_NAME}' successfully set up and enabled/started.", file=sys.stderr)
    print(f"  Service file: {service_file_path}")
    print(f"  Timer file: {timer_file_path}")
    print(f"  To check timer status: systemctl --user status {TIMER_NAME}")
    print(f"  To check service logs: journalctl --user -u {SERVICE_NAME}")
    return True
```
