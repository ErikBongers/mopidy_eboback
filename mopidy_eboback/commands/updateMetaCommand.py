import logging

from mopidy import commands

from mopidy_eboback.file_scanners.audo_scanner import ProgressReporter
from mopidy_eboback.file_scanners.meta_scanner import MetaScanner
from mopidy_eboback.storage import LocalStorageProvider

logger = logging.getLogger(__name__)

class UpdateMetaCommand(commands.Command):

    help = "Update album data based on the metadata of the eboplayer.meta files that are found in the same directory."

    def __init__(self):
        super().__init__()
        self.media_dir = None
        self.storage: LocalStorageProvider | None = None
        self.warning_buffer: list[str] = []

    def run(self, args, config):
         with LocalStorageProvider(config) as storage:
            def progress(msg: str) -> None:
                logger.info(f"*** SCAN STEP: {msg}")

            def details(msg: str) -> None:
                logger.info(msg)

            def error(msg: str) -> None:
                logger.error(msg)

            reporter = ProgressReporter(progress, details, error)
            scanner = MetaScanner(config, storage, reporter)
            return scanner.run()