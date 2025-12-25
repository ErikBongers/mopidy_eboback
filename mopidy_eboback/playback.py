from mopidy import backend

from mopidy_eboback import translator


class LocalPlaybackProvider(backend.PlaybackProvider):
    def translate_uri(self, uri):
        stream_prefix = "eboback:stream:"
        if uri.startswith(stream_prefix):
            return uri[len(stream_prefix) :]
        return translator.local_uri_to_file_uri(
            uri, self.backend.config["eboback"]["media_dir"]
        )
