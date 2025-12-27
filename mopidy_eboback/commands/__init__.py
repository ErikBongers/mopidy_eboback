from mopidy import commands

from mopidy_eboback.commands.clearCommand import ClearCommand
from mopidy_eboback.commands.scanCommand import ScanCommand
from mopidy_eboback.commands.updateMetaCommand import UpdateMetaCommand


class EbobackCommand(commands.Command):
    def __init__(self):
        super().__init__()
        self.add_child("scan", ScanCommand())
        self.add_child("clear", ClearCommand())
        self.add_child("update_meta", UpdateMetaCommand())


