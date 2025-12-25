import logging
import pathlib
import time

from mopidy import commands
from mopidy.audio import scan, tags

from mopidy_eboback import mtimes, storage, translator

logger = logging.getLogger(__name__)

MIN_DURATION_MS = 100  # Shortest length of track to include.


class EbobackCommand(commands.Command):
    def __init__(self):
        super().__init__()
        self.add_child("scan", ScanCommand())
        self.add_child("clear", ClearCommand())
        self.add_child("update_meta", UpdateMetaCommand())


class ClearCommand(commands.Command):
    help = "Clear local media files from the eboplayer library."

    def run(self, args, config):
        library = storage.LocalStorageProvider(config)

        prompt = "Are you sure you want to clear the library? [y/N] "

        if input(prompt).lower() != "y":
            print("Clearing library aborted")
            return 0

        if library.clear():
            print("Library successfully cleared")
            return 0

        print("Unable to clear library")
        return 1


class ScanCommand(commands.Command):
    help = "Scan local media files and populate the eboplayer library."

    def __init__(self):
        super().__init__()
        self.excluded_exts = None
        self.included_exts = None
        self.library = None
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


        logger.info("Number of playlist files found:" + str(len(playlist_files)))
        for playlist_file in playlist_files:
            logger.info("playlist: " + playlist_file.as_uri())

        self.library.close()
        return 0

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
                    local_uri = translator.path_to_local_track_uri(
                        absolute_path, self.media_dir
                    )
                    mtime = file_mtimes.get(absolute_path)
                    track = tags.convert_tags_to_track(result.tags).replace(
                        uri=local_uri,
                        length=result.duration,
                        last_modified=mtime,
                    )
                    self.library.add(track, result.tags, result.duration)
                    logger.debug(f"Added {track.uri}")
            except Exception as error:
                logger.warning(f"Failed scanning {absolute_path.as_uri()}: {error}")

            if progress.increment():
                progress.log()
                if self.library.flush():
                    logger.debug("Progress flushed")

        progress.log()
        logger.info("Done scanning")


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


class UpdateMetaCommand(commands.Command):
    help = "Update album data based on the metadata of the eboplayer.meta files that are found in the same directory."

    def run(self, args, config):
        library = storage.LocalStorageProvider(config)

        prompt = "Are you sure you want to clear the library? [y/N] "
        media_dir = pathlib.Path(config["eboback"]["media_dir"]).resolve()

        if library.update_meta_data(media_dir):
            print("Meta data updated successfully.")
            return 0

        print("Unable to clear library")
        return 1

def is_playlist_file(relative_path):
    if relative_path.suffix.lower() == ".wpl":
        return True
    if relative_path.suffixes == [".eboplayer", ".playlist"]:
        return True
    return False
