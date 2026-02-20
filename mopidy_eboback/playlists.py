import hashlib
import logging
import pathlib
import sqlite3
from typing import Optional, List
from mopidy.backend import PlaylistsProvider
from mopidy.models import Ref, Playlist
from mopidy_eboback import Extension, schema, storage
from mopidy_eboback.database import playlists_db
from mopidy_eboback.schema import Connection
from datetime import datetime

from mopidy_eboback.storage import LocalStorageProvider

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
        self.storage = LocalStorageProvider(config)


    def as_list(self) -> list[Ref]:
        with self._connect() as c:
            playlists = playlists_db.get_playlists(c)
            return list(map(lambda p: Ref.playlist(name=p["name"], uri=p["uri"]), playlists))

    def get_items(self, uri: Uri) -> Optional[List[Ref]]:
        with self._connect() as c:
            refs = playlists_db.get_playlist_tracks(c, uri)
            item_uris = self.storage.get_playlist_item_uris(uri)
            logger.info(item_uris)
            for item_uri in item_uris:
                if item_uri.startswith("eboback:track"):
                    refs.append(Ref.track(uri=item_uri))
                elif item_uri.startswith("eboback:stream"):
                    refs.append(Ref.track(uri=item_uri))
                elif item_uri.startswith("eboback:album"):
                    refs.append(Ref.album(uri=item_uri))
            return refs

    def _connect(self):
        if not self._connection:
            self._connection = sqlite3.connect(
                self._dbpath,
                factory=schema.Connection,
                timeout=self._config["timeout"],
                check_same_thread=False,
            )
        return self._connection
