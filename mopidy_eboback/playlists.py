import logging
import pathlib

from mopidy.backend import PlaylistsProvider
from mopidy.models import Ref

logger = logging.getLogger(__name__)

class EbobackPlaylists(PlaylistsProvider):
    def __init__(self, backend, config):
        super().__init__(backend)
        media_dir = pathlib.Path(config["eboback"]["media_dir"]).resolve()


    def as_list(self) -> list[Ref]:
        just_a_ref = Ref.playlist(name="Whatever the list", uri="eboback:whatever")
        return [just_a_ref]
