import datetime

# Enum-like structure for mirror status, similar to C version
class MirrorStatus:
    UNKNOWN = 0
    COMPARE = 1  # Indicates this is the reference mirror for comparison
    SUCCESS = 2  # Successfully processed
    ERROR = 3    # An error occurred during processing

class Mirror:
    def __init__(self, url: str, country: str, arch: str):
        self.url: str = url
        self.country: str = country
        self.arch: str = arch
        
        self.status: int = MirrorStatus.UNKNOWN
        self.is_proxy: bool = False
        
        self.outofdate: int = 0
        self.uptodate: int = 0
        self.morerecent: int = 0
        self.total_packages: int = 0 # Corresponds to 'total' in C struct for a single mirror's db
        
        self.retry_count: int = 0 # Corresponds to 'retry' in C struct
        self.speed: float = 0.0  # MiB/s
        self.ping: float = -1.0  # ms, -1 if error or not tested
        self.stability: float = 0.0 # Calculated weight
        self.extimated_days: int = 0 # Corresponds to 'extimated' in C struct (days)
        
        # For storing parsed package databases (e.g., {repo_name: [pkg_desc_list]})
        # pkg_desc could be a simple dict: {'name': 'pkgname', 'version': '1.2.3'}
        self.repos: dict[str, list[dict[str, str]]] = {} 
        
        self.last_sync_datetime: datetime.datetime | None = None # For list output
        self.www_error_code: int | None = None # For www errors, e.g., HTTP status or curl error
        self.processing_error_type: str | None = None # e.g., GZIP_ERROR, TAR_ERROR

    def __repr__(self):
        return (f"<Mirror(url='{self.url}', country='{self.country}', status={self.status}, "
                f"speed={self.speed:.2f} MiB/s, ping={self.ping:.1f} ms)>")

    def get_package_count_for_repo(self, repo_name: str) -> int:
        return len(self.repos.get(repo_name, []))

    def get_total_package_count(self) -> int:
        count = 0
        for repo_name in self.repos:
            count += len(self.repos[repo_name])
        return count

# Placeholder for other functions that will be added to this file:
# def mirror_loading(...)
# def mirrors_country(...)
# def server_unique(...)

if __name__ == '__main__':
    # Example Usage (for testing purposes)
    m = Mirror(url="http://example.com/archlinux/$repo/os/$arch", country="Testland", arch="x86_64")
    m.status = MirrorStatus.SUCCESS
    m.speed = 10.555
    m.ping = 123.456
    m.repos["core"] = [
        {"name": "linux", "version": "5.10.0-1"},
        {"name": "pacman", "version": "6.0.0-1"}
    ]
    m.repos["extra"] = [{"name": "firefox", "version": "90.0-1"}]
    
    print(m)
    print(f"Total packages in core: {m.get_package_count_for_repo('core')}")
    print(f"Total packages overall: {m.get_total_package_count()}")
    m.total_packages = m.get_total_package_count() # Update based on parsed repos
    print(f"Mirror's internal total_packages: {m.total_packages}")
