import hashlib
import json
import logging
import pathlib
import shutil
import sqlite3
import struct
from datetime import datetime, timezone
from pathlib import Path
from sqlite3 import Connection
from typing import TypedDict
from urllib.parse import urlparse

from mopidy.audio import tags
from mopidy.models import Track

from . import Extension, schema, translator, ImageCache
from .database import playlists_db
from .json_encoder import CompactJSONEncoder
from .schema import GenreReplacementRow, ImageDict, AlbumPathAndNameRow
from .types import AlbumMetaDict, empty_playlist_def, PlaylistDict, TrackRow, Uri

logger = logging.getLogger(__name__)

HashedRemember = TypedDict("HashedRemember", {"id": str, "text": str})

class GenreDefClass():
    __slots__ = ["genre", "replacement"]
    def __init__(self, genre: str, replacement: str):
        self.genre = genre
        self.replacement = replacement

    def toJSON(self):
        return json.dumps(
            self,
            default=lambda o: o.__dict__,
            sort_keys=True,
            indent=4)

RootMetaDef = TypedDict( "RootMetaDef", { #todo: move to types.py
    "//name": str,
    "name": str,
    "//streams_folder": str,
    "streams_folder": str,
    "//favorites_playlist": str,
    "favorites_playlist": str,
    "//genre_replacements": str,
    "genre_replacements": list[GenreReplacementRow],
    "//saved_stream_lines": str,
    "saved_stream_lines": list[str]
    }
)

empty_root_meta: RootMetaDef = {
    "//name": "A name for this media source",
    "name": "",
    "//streams_folder": "Path to folder where stream images, etc are stored",
    "streams_folder": "",
    "//favorites_playlist": "Name of the playlist where favorites are stored.",
    "favorites_playlist": "Favorites",
    "//genre_replacements": "List of genre replacements",
    "genre_replacements": [],
    "//saved_stream_lines": "List of stream info lines that are saved for later reference. These are not cleared when the stream lines history is cleared.",
    "saved_stream_lines": []
}

ImageDef = TypedDict("ImageDef", {
    "width": int | None,
    "height": int | None,
    "path": str,
    "embedded": bool
})

def check_dirs_and_files(config):
    if not pathlib.Path(config["eboback"]["media_dir"]).is_dir():
        logger.warning(
            "Eboplayer media dir %s does not exist or we lack permissions to the "
            "directory or one of its parents" % config["eboback"]["media_dir"]
        )


def get_image_size_png(data):
    return struct.unpack(">ii", data[16:24])


def get_image_size_gif(data):
    return struct.unpack("<HH", data[6:10])


def model_uri(type, model):
    if type == "album":
        # ignore num_tracks for multi-disc albums
        digest = hashlib.md5(str(model.replace(num_tracks=None)).encode())
    else:
        digest = hashlib.md5(str(model).encode())
    return "eboback:{}:md5:{}".format(type, digest.hexdigest())


def get_image_size_jpeg(data):
    # original source: http://goo.gl/6bo5Vx
    index = 0
    ftype = 0
    size = 2
    while not 0xC0 <= ftype <= 0xCF:
        index += size
        ftype = data[index]
        while ftype == 0xFF:
            index += 1
            ftype = data[index]
        index += 1
        size = struct.unpack(">H", data[index : index + 2])[0] - 2
        index += 2
    index += 1  # skip precision byte
    height, width = struct.unpack(">HH", data[index : index + 4])
    return width, height


MIN_BYTES_FOR_IMAGE_TYPE = 8
IMG_URI_PREFIX = "img"
IMG_ID_PREFIX = "image"
MEDIA_URI_PREFIX = "media"

class LocalStorageProvider:
    def __init__(self, config):
        self._config = ext_config = config[Extension.ext_name]
        self._media_dir = pathlib.Path(ext_config["media_dir"])
        logger.info(self._media_dir)
        self._data_dir = Extension.get_data_dir(config)
        self._image_dir = Extension.get_image_dir(config)
        self._base_uri = "/" + Extension.ext_name + "/" + IMG_URI_PREFIX + "/"
        self.img_file_patterns = list(map(str, ext_config["album_art_files"])) #todo: also rename the config name: it's not files but patterns.
        self._dbpath = self._data_dir / "library.db"
        self._connection: Connection | None = None

    def create_or_update_db(self) -> int | None:
        with self._connect() as connection:
            version = schema.create_or_update_db(connection)
            logger.debug("Using SQLite database schema v%s", version)
            return version

    def count_tracks(self) -> int:
        with self._connect() as connection:
            return schema.count_tracks(connection)

    def begin(self):
        return schema.tracks(self._connect())

    def add_track(self, track: Track, tags=None, duration=None):
        logger.debug("Adding track: %s", track)
        images: dict[str, ImageDef] = {}
        file_path = translator.local_uri_to_path(track.uri, self._media_dir)
        file_dir: str = str(file_path.parent)
        if track.album and track.album.name:  # FIXME: album required
            try:
                if tags is not None:
                    images = self._extract_images(track.uri, tags)
                logger.debug("%s images: %s", track.uri, images)
            except Exception as e:
                logger.warning("Error extracting images for %s: %s", file_path.as_uri(), e)
        try:
            track = self._validate_track(track)
            image_strings = set([image["path"] for image in images.values()])
            schema.insert_track(self._connect(), track, image_strings, file_dir)
            for image_def in images.values():
                image_id = schema.insert_image(self._connect(), image_def["path"], image_def["width"], image_def["height"], image_def["embedded"])
                if track.album:
                    schema.add_album_image(self._connect(), track.album.uri, image_id)
                else:
                    schema.add_track_image(self._connect(), track.uri, image_id)
        except Exception as e:
            logger.warning("Skipped %s: %s", track.uri, e)

    def update_album_images(self, album_uri: str, cache_holder: ImageCache):
        logger.info("Updating album images for %s", album_uri)
        track_uris = schema.get_album_track_uris(self._connect(), album_uri)
        track_paths = [translator.local_uri_to_path(uri, self._media_dir) for uri in track_uris]
        album_dirs = set(track_path.parent for track_path in track_paths)
        for album_dir in album_dirs:
            logger.info("Updating album images for dir %s", album_dir)
            images = self.get_image_files_from_folder(album_dir)
            for image_def in images.values():
                logger.info("Adding image %s", image_def)
                image_id = schema.insert_image(self._connect(), image_def["path"], image_def["width"], image_def["height"], False)
                logger.info("Added image %s", image_id)
                schema.add_album_image(self._connect(), album_uri, image_id)
        schema.update_all_album_min_max_images(self._connect())
        self._connect().commit()
        cache_holder["image_cache"] = None # or...add the new images in above loop.


    def add_stream_track(self, track, image: str | None, exclude_streamlines: list[str], program_titles: list[str]):
        try:
            exclude_str = "\n".join(exclude_streamlines)
            program_titles_str = "\n".join(program_titles)
            schema.insert_stream_track(self._connect(), track, exclude_str, program_titles_str)
            if image:
                new_path = self._media_dir / image

                image_def = self._get_or_create_image_file(new_path, None)
                image_id = schema.insert_image(self._connect(), image_def["path"], image_def["width"], image_def["height"], image_def["embedded"])
                schema.add_track_image(self._connect(), track.uri, image_id)
        except Exception as e:
            logger.warning("Skipped %s: %s", track.uri, e)

    def remove(self, uri):
        schema.delete_track(self._connect(), uri)

    def delete_file_playlists(self):
        playlists_db.delete_file_playlists(self._connect())

    def add_playlist(self, name: str, file_path: pathlib.Path):
        return playlists_db.insert_playlist(self._connect(), name, file_path)

    def flush(self):
        if not self._connection:
            return False
        self._connection.commit()
        return True

    def close(self):
        if self._connection:
            schema.cleanup(self._connection)
            self._connection.commit()
            self._connection.close()
            self._connection = None
        else:
            logger.error("Attempting to close while not connected")

    def clear_except_history(self):
        logger.info("Clearing image directory")
        try:
            shutil.rmtree(self._image_dir)
            self._image_dir.mkdir()
        except IOError as e:
            logger.warning("Error clearing image directory: %s", e)
        logger.info("Clearing SQLite database")
        try:
            schema.clear_except_history(self._connect())
            return True
        except sqlite3.Error as e:
            logger.error("Error clearing SQLite database: %s", e)
            return False

    def _connect(self) -> Connection:
        if not self._connection:
            self._connection = sqlite3.connect(
                self._dbpath,
                factory=schema.Connection,
                timeout=self._config["timeout"],
                check_same_thread=False,
            )
        return self._connection

    def _validate_artist(self, model):
        if not model.name:
            raise ValueError("Empty artist name")
        if not model.uri:
            model = model.replace(uri=model_uri("artist", model))
        return model

    def _validate_album(self, model):
        if not model.name:
            raise ValueError("Empty album name")
        if not model.uri:
            model = model.replace(uri=model_uri("album", model))
        return model.replace(
            artists=list(map(self._validate_artist, model.artists))
        )

    def _validate_track(self, model):
        if not model.uri:
            raise ValueError("Empty track URI")
        if model.name:
            name = model.name
        else:
            name = translator.local_uri_to_path(model.uri, "").name #todo: is this a problem?
        if model.album and model.album.name:
            album = self._validate_album(model.album)
        else:
            album = None
        return model.replace(
            name=name,
            album=album,
            artists=list(map(self._validate_artist, model.artists)),
            composers=list(map(self._validate_artist, model.composers)),
            performers=list(map(self._validate_artist, model.performers)),
        )

    def get_images_to_cleanup(self) -> set[str]:
        logger.info("Cleaning up image directory")
        with self._connect() as c:
            paths = set(schema.get_unreferenced_images(c))
            return paths

    def cleanup_images(self, paths: set[str]):
        for image_path in paths:
            path = Path(image_path)
            try:
                path.unlink()
            except OSError as e:
                logger.warning("Error removing image file %s: %s", path, e)
        with self._connect() as c:
            schema.delete_unreferenced_images(c)

    def _extract_images(self, uri, tags) -> dict[str, ImageDef]:
        images: dict[str, ImageDef] = {}  # filter duplicate images, e.g. embedded/external
        for image in tags.get("image", []) + tags.get("preview-image", []):
            try:
                # FIXME: gst.Buffer or plain str/bytes type?
                data = getattr(image, "data", image)
                image_def = self._get_or_create_image_file(None, data)
                images[image_def["path"]] = image_def
            except Exception as e:
                logger.warning("Error extracting images for %r: %r", uri, e)
        # look for external album art
        track_path: pathlib.Path = translator.local_uri_to_path(uri, self._media_dir)
        dir_path = track_path.parent
        extenal_images = self.get_image_files_from_folder(dir_path)
        images.update(extenal_images)
        return images

    def get_image_files_from_folder(self, dir_path: pathlib.Path) -> dict[str, ImageDef]:
        images: dict[str, ImageDef] = {}
        for pattern in self.img_file_patterns:
            for match_path in dir_path.glob(pattern):
                try:
                    image_def = self._get_or_create_image_file(match_path)
                    images[image_def["path"]] = image_def
                except Exception as e:
                    logger.warning(
                        f"Cannot read image file {match_path.as_uri()}: {e!r}"
                    )
        return images

    def _get_or_create_image_file(self, path: pathlib.Path | None, data=None) -> ImageDef:
        if not data:
            with open(path, "rb") as f:
                data = f.read()
            data_source = path.as_uri()
        else:
            data_source = "embedded image"
        what = get_image_type(data, path)
        width, height = get_image_size(data, what, data_source)
        if path:
            image_path = path
        else:
            image_path = self.write_image_file(data, data_source, what, height, width)

        return {"width": width, "height": height, "path": str(image_path), "embedded": path is None}

    def write_image_file(self, data: bytes, data_source: str, what: str, height: int | None, width: int | None) -> Path:
        digest = hashlib.md5(data).hexdigest()
        if width and height:
            name = "%s-%dx%d.%s" % (digest, width, height, what)
        else:
            name = f"{digest}.{what}"
        image_path = self._image_dir / name
        if not image_path.is_file():
            logger.info(
                f"Creating file {image_path.as_uri()} from {data_source}"
            )
            image_path.write_bytes(data)
        return image_path

    def get_album_path_and_path_counts(self):
        return schema.get_album_paths_and_path_counts(self._connect())

    def update_album_meta(self, album_uri: str, meta_data: AlbumMetaDict):
        with self._connect() as c:
            if meta_data.get("albumTitle"):
                schema.update_album_alt_name(self._connect(), album_uri, meta_data["albumTitle"])
            if meta_data.get("genre"):
                schema.update_album_genre(self._connect(), album_uri, meta_data["genre"])

    def add_playlist_ref(self, playlist_uri: str, uri: str, ref_type: str, sequence: int):
        playlists_db.add_playlist_ref(self._connect(), playlist_uri, uri, ref_type, sequence)

    def add_genre_replacement(self, org_name, new_name):
        schema.insert_genre_replacement(self._connect(), org_name, new_name)

    def get_root_meta(self) -> RootMetaDef:
        path = pathlib.Path(self._media_dir) / "root.eboplayer"
        if path.exists():
            text = path.read_text()
            loaded_meta = json.loads(text)
            full_meta = RootMetaDef(**empty_root_meta) # ensure a full (recent) definition.
            full_meta.update(loaded_meta)
            return full_meta
        return empty_root_meta.copy()

    def write_root_meta(self):
        root_meta = self.get_root_meta()
        genre_defs = schema.get_genre_replacements(self._connect())
        meta_data: RootMetaDef = RootMetaDef(**empty_root_meta) # ensure a full (recent) definition.
        meta_data.name= root_meta.get("name", "Eboplayer media"),
        meta_data.streams_folder = root_meta.get("streams_folder", "/RadioStreams"),
        meta_data.genre_replacements = genre_defs,
        meta_data.saved_stream_lines =  root_meta.get("saved_stream_lines", [])
        path = pathlib.Path(self._media_dir) / "root.eboplayerx"
        text = json.dumps(meta_data, indent=4, cls=CompactJSONEncoder)
        path.write_text(text)

    def write_remember(self, remember: str):
        remembers = self.read_remember_strings()
        remembers.append(remember)
        self.write_remembers(remembers)

    def write_remembers(self, remembers: list[str]):
        path = pathlib.Path(self._media_dir) / "remember.eboplayer"
        text = json.dumps(remembers, indent=4, cls=CompactJSONEncoder)
        path.write_text(text)

    def delete_remember(self, r_id: str):
        remembers = self.read_remembers()
        remember_strings = [r["text"] for r in remembers if r["id"] != r_id]
        self.write_remembers(remember_strings)

    def read_remembers(self) -> list[HashedRemember]:
        path = pathlib.Path(self._media_dir) / "remember.eboplayer"
        remembers = []
        if path.exists():
            text = path.read_text()
            remembers =  json.loads(text)
        hashed_remembers: list[HashedRemember] = [{"id":hashlib.md5(r.encode()).hexdigest(), "text":r} for r in remembers]
        return hashed_remembers

    def read_remember_strings(self) -> list[str]:
        remembers = self.read_remembers()
        return [r["text"] for r in remembers]

    def insert_history_line(self, name: str, uri: str, ref_type: str):
        with self._connect() as c:
            moment = int(datetime.now(timezone.utc).timestamp())
            schema.insert_history_line(c, moment, name, uri, ref_type)

    def get_history(self, limit: int, offset: int):
        with self._connect() as c:
            return schema.get_history(c, limit, offset)

    def update_album_dates(self):
        with self._connect() as c:
            schema.update_album_dates(c)

    def get_all_refs(self):
        with self._connect() as c:
            return schema.get_all_refs(c)

    def update_all_album_images(self):
        with self._connect() as c:
            schema.update_all_album_min_max_images(self._connect())

    def get_all_images(self) -> list[ImageDict]:
        with self._connect() as c:
            return schema.get_all_images(c)


    def get_album_path_and_name(self, album_uri: str) -> AlbumPathAndNameRow:
        with self._connect() as c:
            return schema.get_album_path_and_name(c, album_uri)

    def create_playlist(self, playlist_name: str):
        filename = playlist_name + ".eboplayer.playlist"
        path = pathlib.Path(self._media_dir) / filename
        with self._connect() as c:
            playlist_uri = playlists_db.insert_playlist(c, playlist_name, path)
            with open(path, "w") as f:
                new_playlist_def: PlaylistDict = empty_playlist_def.copy()
                new_playlist_def["name"] = playlist_name
                f.write(json.dumps(new_playlist_def, indent=4, cls=CompactJSONEncoder))
                return playlist_uri

    def read_playlist_file(self, playlist_uri: str) -> PlaylistDict:
        playlist_row = playlists_db.read_playlist(self._connect(), playlist_uri)
        file_path_uri = playlist_row["file_path"]
        file_path = Path(urlparse(file_path_uri).path)
        playlist_def: PlaylistDict = empty_playlist_def.copy()
        playlist_def.update(json.loads(file_path.read_text()))
        return playlist_def

    def write_playlist_file(self, playlist_uri: str, playlist_def: PlaylistDict):
        playlist_row = playlists_db.read_playlist(self._connect(), playlist_uri)
        file_path_uri = playlist_row["file_path"]
        file_path = Path(urlparse(file_path_uri).path)
        with open(file_path, "w") as f:
            f.write(json.dumps(playlist_def, indent=4, cls=CompactJSONEncoder))

    def get_track(self, uri: str):
        track_row: TrackRow = schema.get_track_row(self._connect(), uri)
        path = translator.local_uri_to_path(uri, self._media_dir)

    def get_file_path_for_uri(self, file_uri) -> Path | None:
        if not file_uri.startswith("eboback:track:"): #todo: check if this track is really a file!
            return None
        return translator.local_uri_to_path(file_uri, self._media_dir)

    def save_playlist_file_in_db(self, playlist_file: pathlib.Path):
        playlist_text = playlist_file.read_text()
        playlist: PlaylistDict = json.loads(playlist_text)
        self.save_playlist_dict_in_db(playlist, playlist_file)

    def save_playlist_dict_in_db(self, playlist: PlaylistDict, playlist_file: pathlib.Path):
        name: str = playlist['name']
        items = playlist['items']
        with self._connect() as c:
            playlist_uri = playlists_db.insert_playlist(c, name, playlist_file)
            playlists_db.delete_playlist_items(c, playlist_uri)
            for idx, item in enumerate(items):
                if type(item) is str:
                    # file path or stream url
                    playlists_db.add_playlist_file(c, playlist_uri, item)
                elif item['type'] == 'stream':
                    track = tags.convert_tags_to_track({}).replace(
                        name=item['name'],
                        uri="eboback:stream:" + item['uri'],
                        genre=item['genre']
                    )
                    self.add_stream_track(track, item["image"], item['exclude_streamlines'], item["program_titles"])  # todo: this may already exist. Ok to overwrite?
                    self.add_playlist_ref(playlist_uri, track.uri, "track", idx)  # todo: streams are saved as tracks...

    def toggle_favorite(self, item_uri: Uri) -> bool:
        favorites_name = "Favorites" #todo: defined in settings.
        item_path_or_url = translator.track_or_stream_uri_to_path_or_url(item_uri, self._media_dir)
        logger.info(f"Toggle favorite for item {item_uri} ({item_path_or_url})")
        with self._connect() as c:
            playlist_row = playlists_db.get_playlist_by_name(c, favorites_name)
            if playlist_row is None:
                playlist_path: Path = self._media_dir / (favorites_name + ".eboplayer.playlist")
                playlist_uri: Uri = playlists_db.insert_playlist(c, favorites_name, playlist_path)
                playlist_def: PlaylistDict = empty_playlist_def.copy()
                playlist_def["name"] = favorites_name
            else:
                playlist_path = Path(playlist_row["file_path"])
                playlist_uri = playlist_row["uri"]
                playlist_def = self.read_playlist_file(playlist_uri)
            # toggle item (str) in favorites playlist
            if item_path_or_url in playlist_def["items"]:
                playlist_def["items"].remove(item_path_or_url)
                is_favorite = False
            else:
                playlist_def["items"].append(item_path_or_url)
                is_favorite = True
            self.write_playlist_file(playlist_uri, playlist_def)
            # update db
            logger.info(f"saving playlist {str(playlist_path)} to db")
            self.save_playlist_dict_in_db(playlist_def, playlist_path)
            return is_favorite

    def get_favorite_uris(self):
        playlist_name = "Favorites"  # todo: get from settings.
        items = playlists_db.get_playlist_items_by_name(self._connect(), playlist_name)
        def to_url(item) -> str:
            return translator.path_to_track_or_stream_uri(item, self._media_dir)
        item_urls = list(map(to_url, items))
        return item_urls


def get_image_size(data: bytes, ext: str, data_source: str):
    width: int | None = None
    height: int | None = None
    try:
        if ext == "png":
            width, height = get_image_size_png(data)
        elif ext == "gif":
            width, height = get_image_size_gif(data)
        elif ext == "jpeg":
            width, height = get_image_size_jpeg(data)
        elif ext == "svg":
            width, height = 9999, 9999
    except Exception as e:
        logger.error("Error getting image size for %r: %r", data_source, e)
    return width, height

def get_image_type(data: bytes, path: pathlib.Path) -> str:
    # original source: https://github.com/sphinx-doc/sphinx/commit/a502e7
    if path:
        file_ext = path.suffix.lower()
        if file_ext == ".svg":
            return "svg"

    if len(data) < MIN_BYTES_FOR_IMAGE_TYPE:
        raise ValueError("Unknown image type")

    if data.startswith(b"\x89PNG\r\n\x1A\n"):
        return "png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if data.startswith(b"\xFF\xD8"):
        return "jpeg"

    raise ValueError("Unknown image type")

