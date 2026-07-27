import cyclopts

from mopidy_eboback.commands.scanCommand import ScanCommand

app = cyclopts.App(help="TODO: Some text that will show up in --help")

@app.command()
def scan(force: bool = False, limit: int | None = None):
    """Scan the media_dir

    Parameters
    ----------
    force: bool, optional
        Force the scan, by default False
    limit: int, optional
        Maximum number of media to scan, default value None means all media to scan
    """
    scan_command = ScanCommand(force, limit)
    scan_command.run()