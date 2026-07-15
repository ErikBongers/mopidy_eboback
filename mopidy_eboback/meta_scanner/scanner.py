import time
from pathlib import Path
from typing import Callable

from mopidy.audio import scan, tags
from mopidy.models import Track

from mopidy_eboback import storage, mtimes, translator
from mopidy_eboback.meta_scanner.mutagen_and_wav import scan_mutagen_meta, scan_wavinfo, scan_mutagen_full
from mopidy_eboback.types import Uri

MIN_DURATION_MS = 100  # Shortest length of track to include.

class WplItem:
    path: str
    item_type: str

class Wpl:
    name: str
    items: list[WplItem]

class ProgressReporter:
    def __init__(self, report_progress: Callable[[str], None], report_details: Callable[[str], None], report_error: Callable[[str], None]):
        self.progress = report_progress
        self.details = report_details
        self.error = report_error

class Scanner:
    def __init__(self, config, force: bool, limit: int | None, reporter: ProgressReporter):
        self.config = config
        self.force = force
        self.limit = limit
        self.reporter = reporter
        self.media_dir = Path(config["eboback"]["media_dir"]).resolve()
        self.timeout = config["eboback"]["scan_timeout"]
        self.flush_threshold=config["eboback"]["scan_flush_threshold"]
        self.storage = storage.LocalStorageProvider(config)
        self.included_exts = [ext.lower() for ext in self.config["eboback"]["included_file_extensions"]]
        self.excluded_exts = [ext.lower() for ext in self.config["eboback"]["excluded_file_extensions"]]

    def run(self):
        upgraded_to_version = self.storage.create_or_update_db()
        if upgraded_to_version:
            self.reporter.progress(f"Upgraded SQLite database schema to version {upgraded_to_version}")

        self.reporter.progress(f"Finding files...")
        files = self.get_files()
        self.reporter.progress(f"Comparing {len(files)} files to library...")

        changed_files, files_in_library, uris_of_removed_files = self.compare_files_to_library(files)

        self.remove_tracks(uris_of_removed_files)

        self.reporter.progress("Filtering files...")
        files_to_scan, playlist_files = self.get_and_filter_new_files(files, files_in_library)

        file_extensions = {path.suffix.lower() for path in files_to_scan}
        self.reporter.progress(f"Found {len(files_to_scan)} new tracks of types {file_extensions}") # report as progress because this is usefull info. Some extensions may need to be excluded by user.
        files_to_update = changed_files | files_to_scan

        self.reporter.progress("Scanning metadata in files...")
        self.scan_metadata(files_to_update, files)

        image_paths = self.storage.get_images_to_cleanup()
        if len(image_paths) > 0:
            self.reporter.progress(f"Cleaning up {len(image_paths)} images...")
            self.storage.cleanup_images(image_paths)

        self.reporter.progress(f"Scanning {len(playlist_files)} .eboplayer.playlist files...")
        self.scan_eboplayer_files(playlist_files)

        self.reporter.progress("Updating database...")
        self.storage.update_album_dates()
        self.storage.update_all_album_images()

        self.reporter.progress("Scanning .eboplayer files...")
        self.run_update_meta_cmd()

        self.storage.close()

        return 0

    def run_update_meta_cmd(self):
        from mopidy_eboback.commands import UpdateMetaCommand

        update_meta_command = UpdateMetaCommand()
        update_meta_command.just_run_it_with_storage(self.config, self.storage) #todo: move this function outside of UpdateMetaCommand()

    def get_and_filter_new_files(self, files: dict[Path, int], files_in_library) -> tuple[set[Path], set[Path]]:
        new_files = set()
        playlist_files = set()

        def _is_hidden_file(rel_path):
            return any(p.startswith(".") for p in rel_path.parts)

        def match_filters(rel_path):
            if self.included_exts:
                return rel_path.suffix.lower() in self.included_exts
            else:
                return not (rel_path.suffix.lower() in self.excluded_exts)

        for absolute_path in files:
            relative_path = absolute_path.relative_to(self.media_dir)

            if is_playlist_file(relative_path):
                playlist_files.add(absolute_path)
                continue

            if (
                not _is_hidden_file(relative_path)
                and match_filters(relative_path)
                and absolute_path not in files_in_library
            ):
                new_files.add(absolute_path)

        self.reporter.details(
            f"Found {len(new_files)} tracks which need to be updated"
        )
        return new_files, playlist_files

    def remove_tracks(self, uris_to_remove: set[str]):
        if len(uris_to_remove) == 0:
            return
        self.reporter.progress(f"Removing {len(uris_to_remove)} tracks for missing files...")
        for uri in uris_to_remove:
            self.storage.remove(uri)

    def compare_files_to_library(self, files: dict[Path, int]) -> tuple[set[Path], set[Path], set[Uri]]:
        num_tracks = self.storage.count_tracks()
        self.reporter.details(f"Checking {num_tracks} tracks from library")

        uris_of_removed_files: set[Uri] = set()
        changed_files = set()
        all_library_files = set()

        for track in self.storage.begin():
            if track.uri.startswith("eboback:stream:"):
                continue

            absolute_path = translator.local_uri_to_path(track.uri, self.media_dir)
            mtime = files.get(absolute_path)
            if mtime is None:
                self.reporter.details(f"Removing {track.uri}: File not found")
                uris_of_removed_files.add(track.uri)
            elif mtime > track.last_modified or self.force:
                changed_files.add(absolute_path)
            all_library_files.add(absolute_path)

        return changed_files, all_library_files, uris_of_removed_files


    def get_files(self):
        self.reporter.details(f"Finding files in {self.media_dir.as_uri()} ...")
        files, file_errors = mtimes.get_files_modtimes(
            self.media_dir, follow=self.config["eboback"]["scan_follow_symlinks"]
        )

        if file_errors:
            self.reporter.error(f"Encountered {len(file_errors)} errors while finding files in {self.media_dir.as_uri()}")
        for path in file_errors:
            self.reporter.error(f"Error for {path.as_uri()}: {file_errors[path]}")

        return files

    def scan_metadata(self, files_to_scan: set[Path], file_mtimes: dict[Path, int]):
        files = sorted(files_to_scan)[:self.limit]

        self.reporter.details(f"Timeout: {self.timeout} ")
        scanner = scan.Scanner(self.timeout)
        progress = _ScanProgress(self.flush_threshold, len(files), self.reporter)

        for absolute_path in files:
            try:
                file_uri = absolute_path.as_uri()
                result = scanner.scan(file_uri)

                if not result.playable:
                    self.reporter.error(f"Failed scanning {file_uri}: No audio found in file")
                elif result.duration is None:
                    self.reporter.error(f"Failed scanning {file_uri}: No duration information found in file")
                elif result.duration < MIN_DURATION_MS:
                    self.reporter.error(f"Failed scanning {file_uri}: Track shorter than {MIN_DURATION_MS}ms")
                else:
                    local_uri = self.storage.playlist_item_to_uri(absolute_path)
                    mtime = file_mtimes.get(absolute_path)
                    track: Track = tags.convert_tags_to_track(result.tags).replace(
                        uri=local_uri,
                        length=result.duration,
                        last_modified=mtime,
                    )
                    if absolute_path.suffix.lower() == ".wma":
                        track = scan_mutagen_meta(absolute_path, track)

                    name = fix_encoding(track.name)
                    track = track.replace(name=name)

                    self.storage.add_track(track, result.tags, result.duration)
                    self.reporter.details(f"Added {track.uri}")
            except Exception as error:
                original_error = error
                try:
                    if absolute_path.suffix.lower() == ".wav":
                        track = scan_wavinfo(absolute_path)
                        if track:
                            mtime = file_mtimes.get(absolute_path)
                            local_uri = self.storage.playlist_item_to_uri(absolute_path)
                            track = track.replace(uri=local_uri)
                            track = track.replace(last_modified=mtime)
                            self.storage.add_track(track, None, None)
                            self.reporter.details(f"Added {track.uri}")
                    else:
                        mtime = file_mtimes.get(absolute_path)
                        local_uri = self.storage.playlist_item_to_uri(absolute_path)
                        mutagen_track = scan_mutagen_full(absolute_path, track=Track(uri=local_uri, last_modified=mtime))
                        if mutagen_track:
                            self.storage.add_track(mutagen_track, None, None) # todo: pass a results.image, so add() can extract the images from the tags. Different extensions have different image tag names.
                            self.reporter.details(f"Added {mutagen_track.uri}")
                except Exception as error:
                    self.reporter.error(f"Failed scanning {absolute_path.as_uri()}: {original_error}\n{error}")

            if progress.increment():
                progress.log()
                if self.storage.flush():
                    self.reporter.details("Progress flushed")

        progress.log()
        self.reporter.details("Done scanning")


    def scan_eboplayer_files(self, playlist_files: set[Path]):
        from mopidy_eboback.lib import text_scanner_py

        self.storage.delete_file_playlists()
        self.reporter.details("Number of playlist files found:" + str(len(playlist_files)))
        for playlist_file in playlist_files:
            full_path = playlist_file.resolve().as_posix()
            self.reporter.details("Parsing playlist file: " + full_path)
            if playlist_file.suffixes == [".eboplayer", ".playlist"]:
                self.storage.save_playlist_file_in_db(playlist_file)
            else:
                if playlist_file.suffix == ".wpl":
                    wpl: Wpl = text_scanner_py.scan_wpl(full_path)
                    items2 = wpl.items
                    playlist_uri = self.storage.add_playlist(wpl.name, playlist_file)
                    for idx, line in enumerate(items2):
                        uri = self.storage.playlist_item_to_uri(line.path)
                        # Assuming the track will already be added during the scan, so just add the playlist ref.
                        self.storage.add_playlist_ref(playlist_uri, uri, "track", idx)


def is_playlist_file(relative_path):
    if relative_path.suffix.lower() == ".wpl":
        return True
    if relative_path.suffixes == [".eboplayer", ".playlist"]:
        return True
    return False

def fix_encoding(title: str) -> str:
    try:
        title = title.encode('latin1').decode('utf-8')
    except UnicodeDecodeError:
        # encoding probably isn't latin1 but windows-1252
        # # Source - https://stackoverflow.com/a/33579343
        title = title.encode('latin1').decode('windows-1252')
    return title

class _ScanProgress:
    def __init__(self, batch_size, total, reporter: ProgressReporter):
        self.count = 0
        self.batch_size = batch_size
        self.total = total
        self.start = time.time()
        self.reporter = reporter

    def increment(self):
        self.count += 1
        return self.batch_size and self.count % self.batch_size == 0

    def log(self):
        duration = time.time() - self.start
        if self.count >= self.total or not self.count:
            self.reporter.details(f"Scanned {self.count} of {self.total} files in {duration:.3f}s.")
        else:
            remainder = duration / self.count * (self.total - self.count)
            self.reporter.details(f"Scanned {self.count} of {self.total} files in {duration:.3f}s, ~{remainder:.0f}s left")
