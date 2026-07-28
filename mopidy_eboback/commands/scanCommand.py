import logging

from mopidy_eboback.file_scanners.audo_scanner import Scanner, ProgressReporter
from mopidy_eboback.storage import LocalStorageProvider

MIN_DURATION_MS = 100  # Shortest length of track to include.

logger = logging.getLogger(__name__)

class ScanCommand:
    storage: LocalStorageProvider
    def __init__(self, force: bool = False, limit: int | None = None):
        super().__init__()
        self.storage: LocalStorageProvider
        self.force = force
        self.limit = limit

    def run(self, config):
        def progress(msg: str) -> None:
            logger.info(f"*** SCAN STEP: {msg}")

        def details(msg: str) -> None:
            logger.info(msg)

        def error(msg: str) -> None:
            logger.error(msg)

        reporter = ProgressReporter(progress, details, error)

        scanner = Scanner(config, self.force, self.limit, reporter)
        return scanner.run()
