import click
import os
import pathlib

def path_home():
    return pathlib.Path.home()

def path_explode(path_str):
    if not path_str:
        return None
    if path_str.startswith('~/'):
        return str(pathlib.Path.home() / path_str[2:]).replace('\\', '/')
    return str(pathlib.Path(path_str).resolve()).replace('\\', '/')

@click.group(context_settings=dict(help_option_names=['-h', '--help']))
@click.version_option(version="0.10.4", prog_name="ghostmirror")
@click.option('--arch', '-a', 'arch', type=str, default="x86_64", help="select arch, default 'x86_64'")
@click.option('--mirrorfile', '-m', 'mirrorfile', type=click.Path(exists=True, dir_okay=False, resolve_path=False), help="use mirror file instead of downloading mirrorlist")
@click.option('--country', '-c', 'country', type=str, multiple=True, help="select country from mirrorlist (can be used multiple times)")
@click.option('--country-list', '-C', 'country_list_flag', is_flag=True, help="show all possible countries")
@click.option('--uncommented', '-u', 'uncommented', is_flag=True, help="use only uncommented mirror")
@click.option('--downloads', '-d', 'downloads', type=int, default=4, show_default=True, help="set numbers of parallel download")
@click.option('--timeout', '-O', 'timeout', type=int, default=8, show_default=True, help="set timeout in seconds for not reply mirror")
@click.option('--progress', '-p', 'progress', is_flag=True, help="show progress, default false")
@click.option('--progress-colors', '-P', 'progress_colors', is_flag=True, help="same -p but with colors for output table")
@click.option('--output', '-o', 'output_table', is_flag=True, help="enable table output")
@click.option('--speed', '-s', 'speed_test_mode', type=click.Choice(['light', 'normal', 'heavy'], case_sensitive=False), help="test speed for downloading pkg: light/normal/heavy")
@click.option('--sort', '-S', 'sort_fields', type=str, multiple=True, help="sort result for any of fields, multiple fields supported (e.g., state,outofdate,speed)")
@click.option('--list', '-l', 'list_output_file', type=str, help="create a file with list of mirrors, 'stdout' for output here")
@click.option('--max-list', '-L', 'max_list_mirrors', type=int, help="set max numbers of output mirrors (default: unlimited)")
@click.option('--type', '-T', 'mirror_types', type=click.Choice(['http', 'https', 'all'], case_sensitive=False), default=['all'], multiple=True, show_default=True, help="select mirrors type: http, https, all")
@click.option('--investigate', '-i', 'investigate_mode', type=click.Choice(['outofdate', 'error', 'all'], case_sensitive=False), multiple=True, help="investigate on mirror, mode: outofdate/error/all")
@click.option('--systemd', '-D', 'systemd_manage', is_flag=True, help="auto manager systemd.timer")
@click.option('--time', '-t', 'systemd_time', type=str, help="specific your preferred time in hh:mm:ss for systemd timer")
@click.option('--fixed-time', '-f', 'systemd_fixed_time', type=str, help="use fixed OnCalendar for systemd timer")
def main(**kwargs):
    """GhostMirror: Ranks pacman mirrors."""
    config = {}
    for key, value in kwargs.items():
        config[key] = value

    if config.get("mirrorfile"):
        config["mirrorfile"] = path_explode(config["mirrorfile"])

    if config.get("list_output_file") and config["list_output_file"] != "stdout":
        config["list_output_file"] = path_explode(config["list_output_file"])

    if config.get("progress_colors"):
        config["progress"] = True

    print("Effective GhostMirror Configuration:")
    for key, value in config.items():
        print(f"  {key}: {value}")

    if config.get("country_list_flag"):
        print("\\nDisplaying country list...")
        # Future: from .country import list_countries
        # Future: list_countries(config)
        return

    # Future: from .core import process_mirrors
    # Future: process_mirrors(config)

if __name__ == '__main__':
    main()
