import json
from pathlib import Path

from mopidy_eboback.file_scanners.progress_reporter import ProgressReporter
from mopidy_eboback.storage import LocalStorageProvider


class MetaScanner:
    def __init__(self, config, storage: LocalStorageProvider, reporter: ProgressReporter):
        self.config = config
        self.storage = storage
        self.media_dir = Path(config["eboback"]["media_dir"]).resolve()
        self.reporter = reporter
        self.warning_buffer: list[str] = []

    def run(self):
        self.reporter.progress("Scanning meta files...")
        self.load_root_meta()

        if self.update_albums_meta_data():
            self.reporter.details("Meta data updated successfully.")
            return 0

        self.reporter.error("Unable to update meta data")
        return 1

    def update_albums_meta_data(self):
        paths = self.storage.get_album_path_and_path_counts() #todo: try to use a class as a type annotation, even though Row isn't of that type...the Row class could be used as a base class though...
        for album in paths:
            meta_file_used: Path | None = None
            path = Path(album.path)

            meta_file_path = path / (album.name + ".eboplayer")
            if self.try_update_album_meta_from(album, meta_file_path, meta_file_used, file_is_for_named_album=True):
                meta_file_used = Path(meta_file_path)
            meta_file_path = path / "meta.eboplayer"
            if self.try_update_album_meta_from(album, meta_file_path, meta_file_used, file_is_for_named_album=False):
                meta_file_used = Path(meta_file_path)
            meta_file_path = path / ".eboplayer"
            self.try_update_album_meta_from(album, meta_file_path, meta_file_used, file_is_for_named_album=False)

        unique_warnings = set(self.warning_buffer)
        self.reporter.details("\n".join(unique_warnings))
        return True

    def try_update_album_meta_from(self, album, meta_file_path: Path, already_used_file: Path | None, file_is_for_named_album: bool):
        if meta_file_path.exists():
            if already_used_file is not None:
                self.warning_buffer.append(f'Meta file "{str(meta_file_path.relative_to(self.media_dir))}" found for album "{album.name}" but already using "{str(already_used_file.relative_to(self.media_dir))}".')
                return False

            if not file_is_for_named_album and album.albums_in_dir > 1:
                self.warning_buffer.append(f'Meta file "{str(meta_file_path.relative_to(self.media_dir))}" found but directory contains multiple albums.')
                return False

            self.reporter.details(f'Updating meta data from "{str(meta_file_path.relative_to(self.media_dir))}"')
            text = meta_file_path.read_text()
            meta_data = json.loads(text)
            self.storage.update_album_meta_in_db(album.uri, meta_data)
            return True
        return False

    def load_root_meta(self):
        root_meta = self.storage.get_root_meta()
        if root_meta.get("genre_replacements") is None:
            return
        for replacement in root_meta["genre_replacements"]:
            self.storage.add_genre_replacement(replacement["genre"], replacement["replacement"])

