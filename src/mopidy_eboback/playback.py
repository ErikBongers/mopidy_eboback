from __future__ import annotations

from typing import TYPE_CHECKING

from mopidy import backend

from mopidy_eboback import translator

if TYPE_CHECKING:
    from mopidy.types import Uri

    from mopidy_eboback.actor import LocalBackend


class LocalPlaybackProvider(backend.PlaybackProvider):
    backend: LocalBackend

    def translate_uri(self, uri: Uri) -> Uri | None:
        return translator.local_uri_to_file_uri(
            uri,
            self.backend.config["eboback"]["media_dir"],
        )
