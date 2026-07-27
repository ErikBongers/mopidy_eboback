import logging
from typing import ClassVar

import pykka
from mopidy import backend, core
from mopidy.audio import scan
from mopidy.ext import Extension
from mopidy.types import UriScheme

from mopidy_eboback import storage, http
from mopidy_eboback.edit_config import EboBackConfigEditor
from mopidy_eboback.library import LocalLibraryProvider
from mopidy_eboback.playback import LocalPlaybackProvider
from mopidy_eboback.playlists import EbobackPlaylists

logger = logging.getLogger(__name__)


class EbobackBackend(pykka.ThreadingActor, backend.Backend, core.CoreListener):
    uri_schemes: ClassVar[list[UriScheme]] = [UriScheme("eboback")]

    def __init__(self, config, audio):
        super().__init__()

        self.config = config

        storage.check_dirs_and_files(config)

        self.the_scanner = scan.Scanner(
            timeout="1000", proxy_config=config["proxy"]
        )

        self._http_client = http.get_httpx_client(
            proxy_config=config["proxy"],
            user_agent=(
                f"{Extension.dist_name}/{Extension.version}"
            ),
        )

        self.storage = storage.LocalStorageProvider(config)

        self.playback = LocalPlaybackProvider(audio=audio, ebo_backend=self, storage=self.storage)
        self.library = LocalLibraryProvider(backend=self, config=config)
        self.playlists = EbobackPlaylists(backend=self, config=config)


    def track_playback_started(self, tl_track):
        self.storage.insert_history_line(tl_track.track.name, tl_track.track.uri, "track")

    def adjust_album_volume_down(self, album_uri: str):
        logger.info("backend: Adjusting album volume down")
        return self.storage.adjust_album_volume(album_uri, -1)

    def adjust_album_volume_up(self, album_uri: str):
        logger.info("backend: Adjusting album volume up")
        return self.storage.adjust_album_volume(album_uri, 1)

    def set_volume_from_track(self, track_uri: str):
        self.storage.set_volume_from_track(track_uri)

    def add_excluded_file_extension(self, ext: str):
        config_editor = EboBackConfigEditor()
        with config_editor:
            config_editor.add_excluded_file_extension(ext)

