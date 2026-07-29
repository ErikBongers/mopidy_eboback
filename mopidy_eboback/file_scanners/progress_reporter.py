from typing import Callable


class ProgressReporter:
    def __init__(self, report_progress: Callable[[str], None], report_details: Callable[[str], None], report_error: Callable[[str], None], report_debug: Callable[[str], None]):
        self.progress = report_progress
        self.details = report_details
        self.error = report_error
        self.debug = report_debug
