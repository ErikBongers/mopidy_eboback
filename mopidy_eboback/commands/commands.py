import cyclopts
from mopidy.config import Config

from mopidy_eboback.commands.clearCommand import ClearCommand
from mopidy_eboback.commands.scanCommand import ScanCommand
from mopidy_eboback.commands.updateMetaCommand import UpdateMetaCommand

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
    config = Config.get_global()
    scan_command.run(config)

@app.command()
def clear():
    """
    Clear the media_dir
    """
    clear_command = ClearCommand()
    config = Config.get_global()
    clear_command.run(config)

@app.command()
def update_meta():
    """
    Update meta data from .eboplayer files.
    """
    update_meta_command = UpdateMetaCommand()
    config = Config.get_global()
    update_meta_command.run(config)