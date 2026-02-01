import logging
import pykka
from mopidy import backend, exceptions, stream, core

from mopidy_eboback import storage, schema
from mopidy_eboback.library import LocalLibraryProvider
from mopidy_eboback.playback import LocalPlaybackProvider
from mopidy_eboback.playlists import EbobackPlaylists
from mopidy.internal import http
from mopidy.audio import scan

logger = logging.getLogger(__name__)


class EbobackBackend(pykka.ThreadingActor, backend.Backend, core.CoreListener):
    uri_schemes = ["eboback"]

    def __init__(self, config, audio):
        super().__init__()

        self.config = config

        storage.check_dirs_and_files(config)

        self._scanner = scan.Scanner(
            timeout="1000", proxy_config=config["proxy"]
        )

        self._session = http.get_requests_session(
            proxy_config=config["proxy"],
            user_agent=(
                f"{stream.Extension.dist_name}/{stream.Extension.version}"
            ),
        )

        self.playback = LocalPlaybackProvider(audio=audio, backend=self)
        self.library = LocalLibraryProvider(backend=self, config=config)
        self.playlists = EbobackPlaylists(backend=self, config=config)

        self.storage = storage.LocalStorageProvider(config)

    def track_playback_started(self, tl_track):
        self.storage.insert_history_line(tl_track.track.name, tl_track.track.uri, "track")