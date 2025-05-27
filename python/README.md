# GhostMirror (Python Port)

This is a Python port of the original GhostMirror C application.

GhostMirror compares pacman mirror databases with the local database to rank mirrors, 
identify out-of-sync mirrors, and provide detailed analysis.

## Prerequisites

- Python 3.8+
- uv (for project management and virtual environments)

## Setup and Installation

1.  **Clone the repository (if you haven't already).**
2.  **Navigate to the Python project directory:**
    ```bash
    cd python
    ```
3.  **Create a virtual environment using uv:**
    ```bash
    uv venv
    ```
4.  **Activate the virtual environment:**
    *   On macOS and Linux:
        ```bash
        source .venv/bin/activate
        ```
    *   On Windows:
        ```bash
        .venv\Scripts\activate
        ```
5.  **Install dependencies:**
    ```bash
    uv pip install -e .
    ```

## Usage

```bash
ghostmirror --help
```

(Further usage instructions will be added as the port progresses.)

## Original Project

For information on the original C version of GhostMirror, please see the main [README.md](../README.md) in the root of this repository.
