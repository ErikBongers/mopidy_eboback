import logging
import time
import typing
import urllib

from mopidy import backend, exceptions
from mopidy.internal import http, playlists
from mopidy.models import Track

from mopidy_eboback import translator
from mopidy_eboback.alsa_proxy import AlsaProxy
from mopidy_eboback.storage import LocalStorageProvider

logger = logging.getLogger(__name__)

type Uri = str #todo: try to get rid of this

STREAM_PREFIX = "eboback:stream:"

class LocalPlaybackProvider(backend.PlaybackProvider):

    def __init__(self, audio, ebo_backend: backend.Backend):
        from mopidy_eboback.backend import EbobackBackend
        super().__init__(audio, ebo_backend)
        self.storage: LocalStorageProvider = typing.cast(EbobackBackend, ebo_backend).storage
        self.mixer = AlsaProxy("Master") #todo: don't hard-code this mixer name.

    def translate_uri(self, uri):
        from mopidy_eboback.backend import EbobackBackend
        if uri.startswith(STREAM_PREFIX):
            stripped_uri = uri[len(STREAM_PREFIX) :]
            unwrapped_uri, _ = _unwrap_stream(
                stripped_uri,
                timeout=5000,
                scanner=typing.cast(EbobackBackend, self.backend).the_scanner,
                requests_session=typing.cast(EbobackBackend, self.backend).the_session,
            )


            return stripped_uri

        return translator.local_uri_to_file_uri(
            uri, typing.cast(EbobackBackend, self.backend).config["eboback"]["media_dir"]
        )

    def is_live(self, uri: Uri) -> bool:
        return uri.startswith(STREAM_PREFIX)

    def change_track(self, track: Track) -> bool:
        """
        Switch to provided track.

        *MAY be reimplemented by subclass.*

        It is unlikely it makes sense for any backends to override
        this. For most practical purposes it should be considered an internal
        call between backends and core that backend authors should not touch.

        The default implementation will call :meth:`translate_uri` which
        is what you want to implement.

        :param track: the track to play
        :type track: :class:`mopidy.models.Track`
        :rtype: :class:`True` if successful, else :class:`False`
        """
        live = self.is_live(track.uri)
        uri = self.translate_uri(track.uri)
        if uri != track.uri:
            logger.debug("Backend translated URI from %s to %s", track.uri, uri)
        if not uri:
            return False
        self.audio.set_source_setup_callback(self.on_source_setup).get()
        self.audio.set_uri(
            uri,
            live_stream=live,
            download=self.should_download(uri),
        ).get()
        self.adjust_volume(track.uri)
        return True

    def play(self) -> bool:
        return self.audio.start_playback().get()

    def adjust_volume(self, track_uri: Uri):
        track_volume = self.storage.get_track_volume(track_uri)
        logger.info("Setting volume to %i%% using proxy", track_volume)
        self.mixer.setvolume(track_volume)


def _unwrap_stream(uri, timeout, scanner, requests_session):
    """
    Get a stream URI from a playlist URI, ``uri``.

    Unwraps nested playlists until something that's not a playlist is found or
    the ``timeout`` is reached.
    """

    original_uri = uri
    seen_uris = set()
    deadline = time.time() + timeout

    while time.time() < deadline:
        if uri in seen_uris:
            logger.info(
                "Unwrapping stream from URI (%s) failed: "
                "playlist referenced itself",
                uri,
            )
            return None, None
        else:
            seen_uris.add(uri)

        logger.info("Unwrapping stream from URI: %s", uri)

        try:
            scan_timeout = deadline - time.time()
            if scan_timeout < 0:
                logger.info(
                    "Unwrapping stream from URI (%s) failed: "
                    "timed out in %sms",
                    uri,
                    timeout,
                )
                return None, None
            scan_result = scanner.scan(uri, timeout=scan_timeout)
        except exceptions.ScannerError as exc:
            logger.info("GStreamer failed scanning URI (%s): %s", uri, exc)
            scan_result = None

        if scan_result is not None:
            logger.info("GStreamer scan result: %s", scan_result)
            has_interesting_mime = (
                scan_result.mime is not None
                and not scan_result.mime.startswith("text/")
                and not scan_result.mime.startswith("application/")
            )
            if scan_result.playable or has_interesting_mime:
                logger.info(
                    "Unwrapped potential %s stream: %s", scan_result.mime, uri
                )
                return uri, scan_result

        download_timeout = deadline - time.time()
        if download_timeout < 0:
            logger.info(
                "Unwrapping stream from URI (%s) failed: timed out in %sms",
                uri,
                timeout,
            )
            return None, None
        content = http.download(
            requests_session, uri, timeout=download_timeout / 1000
        )

        if content is None:
            logger.info(
                "Unwrapping stream from URI (%s) failed: "
                "error downloading URI %s",
                original_uri,
                uri,
            )
            return None, None

        uris = playlists.parse(content)
        if not uris:
            logger.info(
                "Failed parsing URI (%s) as playlist; found potential stream.",
                uri,
            )
            return uri, None

        # TODO Test streams and return first that seems to be playable
        new_uri = uris[0]
        logger.info("Parsed playlist (%s) and found new URI: %s", uri, new_uri)
        uri = urllib.parse.urljoin(uri, new_uri)
