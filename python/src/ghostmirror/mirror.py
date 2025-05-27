"""
This module defines the `Mirror` class, representing an Arch Linux repository mirror,
and the `MirrorStatus` class, which enumerates possible states of a mirror during processing.
"""
import datetime

class MirrorStatus:
    """
    Enumerates the possible states of a mirror during the fetching, parsing,
    and ranking process. This provides a clear and consistent way to refer
    to the status of a mirror throughout the application.
    """
    UNKNOWN = 0     # Status has not yet been determined.
    COMPARE = 1     # Mirror is used as a reference for comparison (not typically set in current logic).
    SUCCESS = 2     # Mirror has been successfully processed (e.g., databases fetched and parsed).
    ERROR = 3       # An error occurred during the processing of this mirror.

class Mirror:
    """
    Represents an Arch Linux repository mirror and stores its attributes and state.

    This class encapsulates all information related to a single mirror, including its
    URL, geographical location, supported architecture, and various metrics derived
    from testing and comparison, such as speed, package freshness, and stability.

    Attributes:
        url (str): The base URL of the mirror, may contain placeholders like $repo and $arch.
        country (str): The country where the mirror is located.
        arch (str): The architecture supported by the mirror (e.g., "x86_64").
        status (int): The current processing status of the mirror, using values from `MirrorStatus`.
                      Defaults to `MirrorStatus.UNKNOWN`.
        is_proxy (bool): Flag indicating if the mirror is a known proxy (not currently used).
                         Defaults to `False`.
        outofdate (int): Count of packages on this mirror that are older than the reference versions.
                         Defaults to `0`.
        uptodate (int): Count of packages on this mirror that are the same version as the reference.
                        Defaults to `0`.
        morerecent (int): Count of packages on this mirror that are newer than the reference versions.
                          Defaults to `0`.
        total_packages (int): Total number of packages found in this mirror's databases for supported repos.
                              Corresponds to 'total' in the C version's struct for a single mirror's db.
                              Defaults to `0`.
        total_packages_in_reference (int): Total number of packages in the reference set for the
                                           repositories this mirror is compared against. Used as the
                                           denominator for freshness calculations. Defaults to `0`.
        retry_count (int): Number of retries attempted for this mirror (not currently used).
                           Corresponds to 'retry' in C struct. Defaults to `0`.
        speed (float): Download speed measured in MiB/s (Megabytes per second).
                       Defaults to `0.0`.
        ping (float): Time taken for the speed test download, in milliseconds.
                      A value of -1.0 indicates an error or that the test was not performed.
                      Defaults to `-1.0`.
        stability (float): Original stability weight from C version (not currently used in Python version's core logic).
                           Defaults to `0.0`.
        stability_score (float): A calculated score representing the mirror's reliability and freshness.
                                 Higher is better. Defaults to `0.0`.
        extimated_days (int): Estimated days since last sync (not currently used).
                              Corresponds to 'extimated' in C struct. Defaults to `0`.
        repos (dict[str, list[dict[str, str]]]): A dictionary where keys are repository names (e.g., "core")
                                                 and values are lists of package dictionaries. Each package
                                                 dictionary contains 'name' and 'version'.
                                                 Example: `{"core": [{"name": "linux", "version": "5.0-1"}]}`.
                                                 Defaults to an empty dict.
        last_sync_datetime (datetime.datetime | None): The last synchronization time reported by the mirror,
                                                      if available (not currently parsed or used).
                                                      Defaults to `None`.
        www_error_code (int | None): HTTP status code or other network error code if an issue occurred
                                     during network operations related to this mirror.
                                     Defaults to `None`.
        processing_error_type (str | None): A string indicating the type of error during data processing,
                                            such as "GZIP_ERROR" or "TAR_ERROR".
                                            Defaults to `None`.
    """
    SUPPORTED_REPOS: list[str] = ["core", "extra", "community"] # List of official repositories to consider.

    def __init__(self, url: str, country: str, arch: str):
        """
        Initializes a Mirror object with essential information.

        Args:
            url (str): The base URL of the mirror.
            country (str): The country where the mirror is located.
            arch (str): The architecture supported by the mirror (e.g., "x86_64").
        """
        self.url: str = url
        self.country: str = country
        self.arch: str = arch
        
        self.status: int = MirrorStatus.UNKNOWN
        self.is_proxy: bool = False # Not actively used in current Python logic
        
        # Package comparison statistics
        self.outofdate: int = 0
        self.uptodate: int = 0
        self.morerecent: int = 0
        self.total_packages: int = 0 # Total packages found on this specific mirror for its repos
        self.total_packages_in_reference: int = 0 # Denominator for freshness, based on reference set
        
        # Performance and stability metrics
        self.retry_count: int = 0 # Not actively used
        self.speed: float = 0.0  # MiB/s
        self.ping: float = -1.0  # ms, -1.0 if error/untested
        self.stability: float = 0.0 # Original C struct field, not primary in Python logic
        self.stability_score: float = 0.0 # Calculated score: higher is better
        self.extimated_days: int = 0 # Not actively used
        
        # Package data storage
        # Example: {"core": [{"name": "linux", "version": "5.0-1"}, ...], "extra": [...]}
        self.repos: dict[str, list[dict[str, str]]] = {} 
        
        # Additional metadata (mostly for future use or more detailed error reporting)
        self.last_sync_datetime: datetime.datetime | None = None # From mirror's lastsync file, if parsed
        self.www_error_code: int | None = None # e.g., HTTP status code from a failed download
        self.processing_error_type: str | None = None # e.g., GZIP_ERROR, TAR_ERROR if db parsing fails

    def __repr__(self) -> str:
        """
        Provides an unambiguous string representation of the Mirror object,
        useful for debugging and logging.

        Returns:
            str: A string representation of the mirror, including URL, country,
                 status, speed, and ping.
        """
        return (f"<Mirror(url='{self.url}', country='{self.country}', status={self.status}, "
                f"speed={self.speed:.2f} MiB/s, ping={self.ping:.1f} ms)>")

    def get_package_count_for_repo(self, repo_name: str) -> int:
        """
        Gets the number of packages parsed for a specific repository on this mirror.

        Args:
            repo_name (str): The name of the repository (e.g., "core").

        Returns:
            int: The number of packages in the specified repository for this mirror.
                 Returns 0 if the repository is not found or has no packages.
        """
        return len(self.repos.get(repo_name, []))

    def get_total_package_count(self) -> int:
        """
        Calculates the total number of packages across all repositories parsed for this mirror.
        This count is stored in `self.total_packages` after processing.

        Returns:
            int: The total count of all packages from all repositories on this mirror.
        """
        count = 0
        for repo_name in self.repos:
            count += len(self.repos[repo_name])
        return count

# Placeholder for other functions that might have been in the C version's mirror.c
# These are not part of the Mirror class itself but might be related utility functions.
# e.g., functions for loading mirrors from a specific format, managing a list of mirrors, etc.
# For this Python project, such logic is generally in core.py, parse.py, or fetch.py.

if __name__ == '__main__':
    # Example Usage (for testing or direct script interaction)
    m = Mirror(url="http://example.com/archlinux/$repo/os/$arch", country="Testland", arch="x86_64")
    m.status = MirrorStatus.SUCCESS
    m.speed = 10.555
    m.ping = 123.456
    m.repos["core"] = [
        {"name": "linux", "version": "5.10.0-1"},
        {"name": "pacman", "version": "6.0.0-1"}
    ]
    m.repos["extra"] = [{"name": "firefox", "version": "90.0-1"}]
    m.total_packages = m.get_total_package_count() # Update based on parsed repos
    
    print(m)
    print(f"Total packages in core: {m.get_package_count_for_repo('core')}")
    print(f"Total packages overall on this mirror: {m.total_packages}")

    # Example of setting comparison stats
    m.total_packages_in_reference = 200 
    m.uptodate = 190
    m.outofdate = 5
    m.morerecent = 5
    m.stability_score = 2.5
    print(f"Reference package count for comparison: {m.total_packages_in_reference}")
    print(f"Uptodate: {m.uptodate}, Outdated: {m.outofdate}, More Recent: {m.morerecent}")
    print(f"Stability Score: {m.stability_score}")
```
