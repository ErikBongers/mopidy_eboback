import logging

import pykka

from mopidy import backend

from mopidy_eboback import storage
from mopidy_eboback.library import LocalLibraryProvider
from mopidy_eboback.playback import LocalPlaybackProvider

logger = logging.getLogger(__name__)


class EbobackBackend(pykka.ThreadingActor, backend.Backend):
    uri_schemes = ["eboback"]

    def __init__(self, config, audio):
        super().__init__()

        self.config = config

        storage.check_dirs_and_files(config)

        self.playback = LocalPlaybackProvider(audio=audio, backend=self)
        self.library = LocalLibraryProvider(backend=self, config=config)
