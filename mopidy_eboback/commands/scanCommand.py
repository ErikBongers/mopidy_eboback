import logging

from mopidy_eboback.file_scanners.audio_scanner import Scanner, ProgressReporter
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
        reporter = ProgressReporter(progress, details, error, debug)

        scanner = Scanner(config, self.force, self.limit, reporter)
        logging.info("WTF???")
        return scanner.run()

def progress(msg: str) -> None:
    loggerx = logging.getLogger(__name__)
    loggerx.info(f"*** SCAN STEP: {msg}")
    print(f"*** SCAN STEP: {msg}")

def details(msg: str) -> None:
    loggerx = logging.getLogger(__name__)
    loggerx.info(msg)
    print(msg)

def debug(msg: str) -> None:
    loggerx = logging.getLogger(__name__)
    loggerx.info(f"DEBUG:{msg}")
    print(f"DEBUG:{msg}")

def error(msg: str) -> None:
    loggerx = logging.getLogger(__name__)
    loggerx.error(msg)
    print(msg)

