import logging
import pathlib
import sqlite3
from typing import Optional, List

from mopidy.backend import PlaylistsProvider
from mopidy.models import Ref

from mopidy_eboback import Extension, schema
from mopidy_eboback.schema import Connection

logger = logging.getLogger(__name__)

Uri = str

class EbobackPlaylists(PlaylistsProvider):
    def __init__(self, backend, config):
        super().__init__(backend)
        self._config = ext_config = config[Extension.ext_name]
        media_dir = pathlib.Path(config["eboback"]["media_dir"]).resolve()
        self._data_dir = Extension.get_data_dir(config)
        self._dbpath = self._data_dir / "library.db"
        self._connection: Connection | None = None


    def as_list(self) -> list[Ref]:
        with self._connect() as c:
            playlists = schema.get_playlists(c)
            return list(map(lambda p: Ref.playlist(name=p["name"], uri=p["uri"]), playlists))

    def get_items(self, uri: Uri) -> Optional[List[Ref]]:
        with self._connect() as c:
            items = schema.get_playlist_refs(c, uri)
            return list(map(lambda i: Ref.track(name=i["name"], uri=i["uri"]), items))

    def _connect(self):
        if not self._connection:
            self._connection = sqlite3.connect(
                self._dbpath,
                factory=schema.Connection,
                timeout=self._config["timeout"],
                check_same_thread=False,
            )
        return self._connection

