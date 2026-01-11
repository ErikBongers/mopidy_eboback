import logging
import json
import pathlib
import string
import time
from typing import Any
import mutagen

from mopidy import commands
from mopidy.audio import tags, scan
from mopidy.models import Track, Artist, Album
from mutagen import FileType
from wavinfo import WavInfoReader

from mopidy_eboback import storage, mtimes, translator
from mopidy_eboback.storage import LocalStorageProvider
from mopidy_eboback.translator import path_to_track_uri

MIN_DURATION_MS = 100  # Shortest length of track to include.

logger = logging.getLogger(__name__)

class WplItem:
    path: str
    item_type: str

class Wpl:
    name: str
    items: list[WplItem]

class ScanCommand(commands.Command):
    help = "Scan local media files and populate the eboplayer library."

    def __init__(self):
        super().__init__()
        self.excluded_exts = None
        self.included_exts = None
        self.library: LocalStorageProvider
        self.timeout = "1000"
        self.media_dir = None
        self.add_argument(
            "--limit",
            action="store",
            type=int,
            dest="limit",
            default=None,
            help="Maximum number of tracks to scan",
        )
        self.add_argument(
            "--force",
            action="store_true",
            dest="force",
            default=False,
            help="Force rescan of all media files",
        )

    def run(self, args, config):
        self.media_dir = pathlib.Path(config["eboback"]["media_dir"]).resolve()
        self.timeout = config["eboback"]["scan_timeout"]

        self.library = storage.LocalStorageProvider(config)
        file_mtimes = self._find_files(follow_symlinks=config["eboback"]["scan_follow_symlinks"])
        files_to_update, files_in_library = self._check_tracks_in_library( file_mtimes=file_mtimes, force_rescan=args.force)

        self.included_exts = [ext.lower() for ext in config["eboback"]["included_file_extensions"]]
        self.excluded_exts = [ext.lower() for ext in config["eboback"]["excluded_file_extensions"]]
        files_to_scan, playlist_files = self._find_files_to_scan(file_mtimes=file_mtimes, files_in_library=files_in_library)
        files_to_update.update(files_to_scan)

        self._scan_metadata(
            file_mtimes=file_mtimes,
            files=files_to_update,
            flush_threshold=config["eboback"]["scan_flush_threshold"],
            limit=args.limit,
        )

        self.update_playlists(args, config, file_mtimes, playlist_files)
        self.library.cleanup_images()
        self.library.close()

        mutagen_tags = mutagen.File("/media/DATA1/Music/Gidon Kremer/Hommage À Piazzolla/07 Soledad.wav")
        print(mutagen_tags)

        wav_tags = WavInfoReader("/media/DATA1/Music/Gidon Kremer/Hommage À Piazzolla/07 Soledad.wav")
        print(wav_tags)
        info_metadata = wav_tags.info
        print(info_metadata)

        return 0

    def fix_encoding(self, title: str) -> str:
        try:
            title = title.encode('latin1').decode('utf-8')
        except UnicodeDecodeError:
            # encoding probably isn't latin1 but windows-1252
            # # Source - https://stackoverflow.com/a/33579343
            title = title.encode('latin1').decode('windows-1252')
        return title



    def update_playlists(self, args: tuple[str, ...], config, file_mtimes: dict[Any, int], playlist_files: set[pathlib.Path]):
        from mopidy_eboback.lib import text_scanner_py

        self.library.delete_file_playlists()
        logger.info("Number of playlist files found:" + str(len(playlist_files)))
        for playlist_file in playlist_files:
            playlist_text = playlist_file.read_text()
            if playlist_file.suffixes == [".eboplayer", ".playlist"]:
                playlist = json.loads(playlist_text)
                name: str = playlist['name']
                items: list[dict[str, str]] = playlist['items']
                hashdata: str = playlist_text
                playlist_uri = self.library.add_playlist(name, playlist_file, hashdata)
                for idx, item in enumerate(items):
                    if item['type'] == 'stream':
                        track = tags.convert_tags_to_track({}).replace(
                            name=item['name'],
                            uri="eboback:stream:" + item['uri'],
                            genre=item['genre']
                        )
                        self.library.add_stream_track(track, item['image']) #todo: this may already exist. Ok to overwrite?
                        self.library.add_playlist_ref(playlist_uri, track.uri, "track", idx) #todo: streams are saved as tracks...

            else:
                if playlist_file.suffix == ".wpl":
                    full_path = playlist_file.resolve().as_posix()
                    logger.info("Parsing playlist file: " + full_path)
                    wpl: Wpl = text_scanner_py.scan_wpl(full_path)
                    name: str = wpl.name
                    items2 = wpl.items
                    hashdata: str = full_path
                    playlist_uri = self.library.add_playlist(name, playlist_file, hashdata)
                    for idx, line in enumerate(items2):
                        uri = path_to_track_uri(line.path, self.media_dir)
                        # Assuming the track will already be added during the scan, so just add the playlist ref.
                        self.library.add_playlist_ref(playlist_uri, uri, "track", idx)



    def _find_files(self, *, follow_symlinks):
        logger.info(f"Finding files in {self.media_dir.as_uri()} ...")
        file_mtimes, file_errors = mtimes.find_mtimes(
            self.media_dir, follow=follow_symlinks
        )
        logger.info(f"Found {len(file_mtimes)} files in {self.media_dir.as_uri()}")

        if file_errors:
            logger.warning(
                f"Encountered {len(file_errors)} errors "
                f"while finding files in {self.media_dir.as_uri()}"
            )
        for path in file_errors:
            logger.warning(f"Error for {path.as_uri()}: {file_errors[path]}")

        return file_mtimes

    def _check_tracks_in_library(self, *, file_mtimes, force_rescan):
        num_tracks = self.library.load()
        logger.info(f"Checking {num_tracks} tracks from library")

        uris_to_remove = set()
        files_to_update = set()
        files_in_library = set()

        for track in self.library.begin():
            if track.uri.startswith("eboback:stream:"):
                pass #todo?
            else:
                absolute_path = translator.local_uri_to_path(track.uri, self.media_dir)
                mtime = file_mtimes.get(absolute_path)
                if mtime is None:
                    logger.debug(f"Removing {track.uri}: File not found")
                    uris_to_remove.add(track.uri)
                elif mtime > track.last_modified or force_rescan:
                    files_to_update.add(absolute_path)
                files_in_library.add(absolute_path)

        logger.info(f"Removing {len(uris_to_remove)} missing tracks")
        for local_uri in uris_to_remove:
            self.library.remove(local_uri)

        return files_to_update, files_in_library

    def _find_files_to_scan(
        self,
        *,
        file_mtimes,
        files_in_library,
    ) -> tuple[set[pathlib.Path], set[pathlib.Path]]:
        files_to_update = set()
        meta_files = set()

        def _is_hidden_file(rel_path):
            return any(p.startswith(".") for p in rel_path.parts)

        def match_filters(rel_path):
            if self.included_exts:
                return rel_path.suffix.lower() in self.included_exts
            else:
                return not (rel_path.suffix.lower() in self.excluded_exts)

        for absolute_path in file_mtimes:
            relative_path = absolute_path.relative_to(self.media_dir)

            if is_playlist_file(relative_path):
                meta_files.add(absolute_path)
                continue

            if (
                not _is_hidden_file(relative_path)
                and match_filters(relative_path)
                and absolute_path not in files_in_library
            ):
                files_to_update.add(absolute_path)

        logger.info(
            f"Found {len(files_to_update)} tracks which need to be updated"
        )
        return files_to_update, meta_files

    def _scan_metadata(
        self,
        *,
        file_mtimes,
        files,
        flush_threshold,
        limit,
    ):
        logger.info("Scanning...")

        files = sorted(files)[:limit]

        logger.info(f"Timeoout: {self.timeout} ")
        scanner = scan.Scanner(self.timeout)
        progress = _ScanProgress(batch_size=flush_threshold, total=len(files))

        for absolute_path in files:
            try:
                file_uri = absolute_path.as_uri()
                result = scanner.scan(file_uri)

                if not result.playable:
                    logger.warning(
                        f"Failed scanning {file_uri}: No audio found in file"
                    )
                elif result.duration is None:
                    logger.warning(
                        f"Failed scanning {file_uri}: "
                        "No duration information found in file"
                    )
                elif result.duration < MIN_DURATION_MS:
                    logger.warning(
                        f"Failed scanning {file_uri}: "
                        f"Track shorter than {MIN_DURATION_MS}ms"
                    )
                else:
                    local_uri = translator.path_to_track_uri(absolute_path, self.media_dir)
                    mtime = file_mtimes.get(absolute_path)
                    track: Track = tags.convert_tags_to_track(result.tags).replace(
                        uri=local_uri,
                        length=result.duration,
                        last_modified=mtime,
                    )
                    if absolute_path.suffix.lower() == ".wma":
                        track = self.scan_mutagen_meta(absolute_path, track)

                    name = self.fix_encoding(track.name)
                    track = track.replace(name=name)

                    self.library.add(track, result.tags, result.duration)
                    logger.debug(f"Added {track.uri}")
            except Exception as error:
                try:
                    mtime = file_mtimes.get(absolute_path)
                    local_uri = translator.path_to_track_uri(absolute_path, self.media_dir)
                    track = self.scan_mutagen_full(absolute_path, track=Track(uri=local_uri, last_modified=mtime))
                    self.library.add(track, None, None) # todo: pass a results.image, so add() can extract the images from the tags. Different extensions have different image tag names.
                    logger.debug(f"Added {track.uri}")
                except Exception as error:
                    if absolute_path.suffix.lower() == ".wav":
                        track = self.scan_wavinfo(absolute_path)
                        if track:
                            mtime = file_mtimes.get(absolute_path)
                            local_uri = translator.path_to_track_uri(absolute_path, self.media_dir)
                            track = self.scan_mutagen_full(absolute_path, track=Track(uri=local_uri, last_modified=mtime))
                            self.library.add(track, None, None)
                            logger.debug(f"Added {track.uri}")
                    else:
                        logger.warning(f"Failed scanning {absolute_path.as_uri()}: {error}")

            if progress.increment():
                progress.log()
                if self.library.flush():
                    logger.debug("Progress flushed")

        progress.log()
        logger.info("Done scanning")

    @staticmethod
    def scan_wavinfo(absolute_path: pathlib.Path):
        wav_tags = WavInfoReader(absolute_path)
        if wav_tags.info:
            name = ""
            artist = None
            genre = ""
            encoding = ""
            album = None
            if wav_tags.info.title:
                name = wav_tags.info.title
            if wav_tags.info.artist:
                artist = wav_tags.info.artist
                if artist:
                    artist = Artist(name=artist)
            if wav_tags.info.genre:
                genre = wav_tags.info.genre
            if wav_tags.info.album:
                album = wav_tags.info.album
                if album:
                    album = Album(name=album, artists=[artist])

            # todo: re-encode everything to utf-8?
            # if wav_tags.info.encoding:
            #     encoding = wav_tags.info.encoding
            return Track(name=name, artists=[artist], genre=genre, album=album)
        else:
            return None

    @staticmethod
    def scan_mutagen_full(absolute_path: pathlib.Path, track: Track) -> Track:
        mutagen_tags = mutagen.File(absolute_path)

        if not mutagen_tags:
            return track

        names = mutagen_tags.get("TIT2") # todo: only works for mp3 !!! wma has a different tag name for the track title.
        if names:
            names = [str(name) for name in names]
            name = "; ".join(names)
            track = track.replace(name=name)

        return ScanCommand.scan_mutagen_extra(mutagen_tags, track)


    @staticmethod
    def scan_mutagen_meta(absolute_path: pathlib.Path, track: Track) -> Track:
        mutagen_tags = mutagen.File(absolute_path)
        return ScanCommand.scan_mutagen_extra(mutagen_tags, track)

    @staticmethod
    def scan_mutagen_extra(mutagen_tags: FileType, track: Track) -> Track:
        def not_empty(s: str) -> bool:
            return s and s.strip() != ""
        genres = mutagen_tags.get("WM/Genre")
        if genres:
            genres = [str(genre) for genre in genres]
            genre = "; ".join(genres)
            track = track.replace(genre=genre)

        artists = mutagen_tags.get("WM/AlbumArtist")
        if artists:
            if len(artists) > 0:
                artists = [str(artist) for artist in artists]
                artists = filter(not_empty, artists)
                artists = [Artist(name=str(artist)) for artist in artists]
                track = track.replace(artists=artists)

        composers = mutagen_tags.get("WM/Composer")
        if composers:
            if len(composers) > 0:
                composers = [str(composer) for composer in composers]
                composers = filter(not_empty, composers)
                composers = [Artist(name=str(composer)) for composer in composers]
                track = track.replace(composers=composers)

        track_numbers = mutagen_tags.get("WM/TrackNumber")
        if track_numbers:
            track_numbers = [str(track_no) for track_no in track_numbers]
            if len(track_numbers) > 0:
                track = track.replace(track_no=int(track_numbers[0]))

        years = mutagen_tags.get("WM/Year")
        if years:
            years = [str(artist) for artist in years]
            if len(years) > 0:
                track = track.replace(date=years[0])
        return track

class _ScanProgress:
    def __init__(self, *, batch_size, total):
        self.count = 0
        self.batch_size = batch_size
        self.total = total
        self.start = time.time()

    def increment(self):
        self.count += 1
        return self.batch_size and self.count % self.batch_size == 0

    def log(self):
        duration = time.time() - self.start
        if self.count >= self.total or not self.count:
            logger.info(
                f"Scanned {self.count} of {self.total} files in {duration:.3f}s."
            )
        else:
            remainder = duration / self.count * (self.total - self.count)
            logger.info(
                f"Scanned {self.count} of {self.total} files "
                f"in {duration:.3f}s, ~{remainder:.0f}s left"
            )


def is_playlist_file(relative_path):
    if relative_path.suffix.lower() == ".wpl":
        return True
    if relative_path.suffixes == [".eboplayer", ".playlist"]:
        return True
    return False
