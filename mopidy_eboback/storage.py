from datetime import datetime, timezone
import hashlib
import json
import logging
import pathlib
import shutil
import sqlite3
import struct
from pathlib import Path
from sqlite3 import Connection
from typing import TypedDict, cast, Any

import uritools
from mopidy.models import Track

from . import Extension, schema, translator
from .json_encoder import CompactJSONEncoder
from .schema import GenreDefRow, ImageDict

logger = logging.getLogger(__name__)


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

RootMetaDef = TypedDict( "RootMetaDef", {
    "//name": str,
    "name": str,
    "//streams_folder": str,
    "streams_folder": str,
    "//genre_replacements": str,
    "genre_replacements": list[GenreDefRow],
    "//saved_stream_lines": str,
    "saved_stream_lines": list[str]
    }
)

empty_root_meta: RootMetaDef = {
    "//name": "A name for this media source",
    "name": "",
    "//streams_folder": "Path to folder where stream images, etc are stored",
    "streams_folder": "",
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
        self._patterns = list(map(str, ext_config["album_art_files"]))
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
                schema.insert_image(self._connect(), track.uri, image_def["path"], image_def["width"], image_def["height"], image_def["embedded"])
        except Exception as e:
            logger.warning("Skipped %s: %s", track.uri, e)

    def add_stream_track(self, track, image: str | None, exclude_streamlines: list[str], program_titles: list[str]):
        try:
            exclude_str = "\n".join(exclude_streamlines)
            program_titles_str = "\n".join(program_titles)
            schema.insert_stream_track(self._connect(), track, exclude_str, program_titles_str)
            if image:
                new_path = self._media_dir / image

                image_def = self._get_or_create_image_file(new_path, None)
                schema.insert_image(self._connect(), track.uri, image_def["path"], image_def["width"], image_def["height"], image_def["embedded"])
        except Exception as e:
            logger.warning("Skipped %s: %s", track.uri, e)

    def remove(self, uri):
        schema.delete_track(self._connect(), uri)

    def delete_file_playlists(self):
        schema.delete_file_playlists(self._connect())

    def add_playlist(self, name: str, file_path: pathlib.Path, hash_data: str):
        digest = hashlib.md5(hash_data. encode(encoding="utf-8")).hexdigest()
        uri = "eboback:playlist:md5:"+digest
        schema.insert_playlist(self._connect(), uri, name, file_path.as_uri())
        return uri

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

    def clear(self):
        logger.info("Clearing image directory")
        try:
            shutil.rmtree(self._image_dir)
            self._image_dir.mkdir()
        except IOError as e:
            logger.warning("Error clearing image directory: %s", e)
        logger.info("Clearing SQLite database")
        try:
            schema.clear(self._connect())
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
            name = translator.local_uri_to_path(model.uri, "").name
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

    def cleanup_images(self):
        logger.info("Cleaning up image directory")
        with self._connect() as c:
            paths = set(schema.get_unreferenced_images(c))
            for image_path in paths:
                path = Path(image_path)
                try:
                    path.unlink()
                except OSError as e:
                    logger.warning("Error removing image file %s: %s", path, e)
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
        for pattern in self._patterns:
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
            image_path = self.save_image_file(data, data_source, what, height, width)

        return {"width": width, "height": height, "path": str(image_path), "embedded": path is None}

    def save_image_file(self, data: bytes, data_source: str, what: str, height: int | None, width: int | None) -> Path:
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

    def update_album_meta(self, album_uri: str, meta_data):
        schema.update_album_meta(self._connect(), album_uri, meta_data)

    def add_playlist_ref(self, playlist_uri: str, uri: str, ref_type: str, sequence: int):
        schema.add_playlist_ref(self._connect(), playlist_uri, uri, ref_type, sequence)

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
        genre_defs = schema.get_genre_defs(self._connect())
        meta_data: RootMetaDef = RootMetaDef(**empty_root_meta) # ensure a full (recent) definition.
        meta_data.name= root_meta.get("name", "Eboplayer media"),
        meta_data.streams_folder = root_meta.get("streams_folder", "/RadioStreams"),
        meta_data.genre_replacements = genre_defs,
        meta_data.saved_stream_lines =  root_meta.get("saved_stream_lines", [])
        path = pathlib.Path(self._media_dir) / "root.eboplayerx"
        text = json.dumps(meta_data, indent=4, cls=CompactJSONEncoder)
        path.write_text(text)

    def write_remember(self, remember: str):
        path = pathlib.Path(self._media_dir) / "remember.eboplayer"
        if path.exists():
            text = path.read_text()
            loaded_meta: list[str] = json.loads(text)
        else:
            loaded_meta = []
        loaded_meta.append(remember)
        text = json.dumps(loaded_meta, indent=4, cls=CompactJSONEncoder)
        path.write_text(text)

    def read_remembers(self) -> list[str]:
        path = pathlib.Path(self._media_dir) / "remember.eboplayer"
        if path.exists():
            text = path.read_text()
            return json.loads(text)
        else:
            return []

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

    def update_album_images(self):
        with self._connect() as c:
            schema.update_album_images(self._connect())

    def get_all_images(self) -> list[ImageDict]:
        with self._connect() as c:
            return schema.get_all_images(c)

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
