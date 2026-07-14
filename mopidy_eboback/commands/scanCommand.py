import logging

from mopidy import commands

from mopidy_eboback.meta_scanner.scanner import Scanner, ProgressReporter
from mopidy_eboback.storage import LocalStorageProvider

MIN_DURATION_MS = 100  # Shortest length of track to include.

logger = logging.getLogger(__name__)

class ScanCommand(commands.Command):
    help = "Scan local media files and populate the eboplayer library."

    def __init__(self):
        super().__init__()
        self.excluded_exts = None
        self.included_exts = None
        self.storage: LocalStorageProvider
        self.timeout = "1000"
        self.media_dir = None
        self.add_argument(
            "--limit",
            action="store",
            type=int,
            dest="limit",
            default=None,
            help="Maximum number of tracks to scan",
        )
        self.add_argument(
            "--force",
            action="store_true",
            dest="force",
            default=False,
            help="Force rescan of all media files",
        )

    def run(self, args, config):
        def progress(msg: str) -> None:
            logger.info(f"*** SCAN STEP: {msg}")

        def details(msg: str) -> None:
            logger.info(msg)

        def error(msg: str) -> None:
            logger.error(msg)

        reporter = ProgressReporter(progress, details, error)

        scanner = Scanner(config, args.force, args.limit, reporter)
        return scanner.run()
