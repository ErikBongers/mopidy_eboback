import json
import logging
import pathlib
import sqlite3
import typing

import tornado.web
from mopidy.models import Ref
from mopidy.types import Uri

from mopidy_eboback import Extension, ImageCache
from mopidy_eboback import schema
from mopidy_eboback.database import playlists_db
from mopidy_eboback.schema import AlbumKeyInfoRow
from mopidy_eboback.storage import LocalStorageProvider
from mopidy_eboback.types import PlaylistDict, GenreReplacementRow

logger = logging.getLogger(__name__)

class DataHandler(tornado.web.RequestHandler):
    # noinspection PyAttributeOutsideInit
    def initialize(self, data_dir, config, image_cache_holder: ImageCache):
        self._dbpath = data_dir / "library.db"
        self._connection = None
        self._config = config[Extension.ext_name]
        self.storage = LocalStorageProvider(config)
        self.cache_holder: ImageCache = image_cache_holder

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*") #todo: use allowed origins from config.
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.set_header("Cache-Control", "no-cache, no-store, must-revalidate")

    def options(self, *args):
        self.set_status(204)
        self.finish()

    def get(self, data_path: str):
        if data_path in ["get_album_meta", "get_genre_replacements", "write_root_meta", "get_excluded_streamlines",
                         "get_program_titles", "get_remembers", "get_history", "get_all_refs", "update_album_data",
                         "upload_album_image", "get_genre_defs", "set_album_genre", "create_playlist",
                         "add_playlist_file", "toggle_favorite", "get_favorite_uris", "get_favorites_playlist_name"]:
            func = getattr(self, data_path)
            func()
            return

        cnt = schema.count_rows(self._connect(), "album")
        self.write("Oops...no valid data request: " + data_path)
        self.write("" + str(cnt))

    def post(self, data_path):
        if data_path in ["add_ref_to_playlist", "save_remember", "delete_remember", "get_album_metas"]:
            func = getattr(self, data_path)
            func()
            return

        self.write("Oops...no valid data request: " + data_path)

    def get_genre_defs(self):
        with self._connect() as c:
            genre_defs = schema.get_genres(c)
            self.set_header("Content-Type", 'application/json')
            self.write(json.dumps(genre_defs))

    def get_album_meta(self):
        uri = self.get_argument("uri", "nada...")
        meta_file_path = self.storage.uri_to_meta_path(uri)
        self.set_header("Content-Type", 'application/json')
        if meta_file_path.exists():
            self.write(meta_file_path.read_text())

    def get_album_metas(self):
        uris_comma_string = self.get_argument("uris", "nada...")
        uris: list[str] = uris_comma_string.split(",")
        metas: dict[str, dict] = {}
        for uri in uris:
            meta_file_path = self.storage.uri_to_meta_path(uri)
            if meta_file_path.exists(): #todo: cache the meta in the db
                try:
                    metas[uri] = json.loads(meta_file_path.read_text()) #todo: don't first decode json to encode it again below.
                except Exception as e:
                    logger.error(f"Cannot parse meta file {meta_file_path}: {e}")

        self.set_header("Content-Type", 'application/json')
        self.write(json.dumps(metas))

    def set_album_genre(self):
        self.set_album_meta_field_from_params("genre")
        self.write(json.dumps({
            "status": "ok"
        }))

    def set_album_meta_field_from_params(self, field_name):
        value = self.get_argument(field_name, "nada...")
        album_uri = self.get_argument("album_uri", "nada...")
        self.storage.set_album_meta_field(album_uri, field_name, value)

    def _connect(self):
        if not self._connection:
            self._connection = sqlite3.connect(
                self._dbpath,
                factory=schema.Connection,
                timeout=self._config["timeout"],
                check_same_thread=False,
            )
        return typing.cast(sqlite3.Connection, self._connection)

    def add_ref_to_playlist(self):
        logger.info("add_ref_to_playlist")
        logger.info(self.get_argument("item_uri"))
        logger.info(self.get_argument("playlist_uri"))
        logger.info(self.get_argument("ref_type"))
        logger.info(self.get_argument("sequence"))
        with self._connect() as c:
            playlists_db.add_playlist_ref(
                c,
                self.get_argument("playlist_uri"),
                self.get_argument("item_uri"),
                self.get_argument("ref_type"),
                int(self.get_argument("sequence"))
            )
        self.write(json.dumps({
            "status": "ok"
        }))

    def get_genre_replacements(self):
        with self._connect() as c:
            genres: list[GenreReplacementRow] = schema.get_active_genres(c)
            # add uri
            genre_defs = []
            for genre in genres:
                uri = "eboback:directory?genre=" + genre['genre']
                ref = Ref.directory(name=genre['genre'], uri=uri)
                name = genre['genre']
                if name == "null":
                    name = "-- no genre --"
                genre_def = {
                    'ref': {
                        'name': name,
                        'uri': ref.uri,
                        'type': ref.type
                    },
                    'replacement': genre['replacement']
                }
                genre_defs.append(genre_def)
            self.set_header("Content-Type", 'application/json')
            self.write(json.dumps(genre_defs))

    def write_root_meta(self):
        self.storage.write_root_meta()

    def get_excluded_streamlines(self):
        uri = self.get_argument("uri", "nada...")
        with self._connect() as c:
            lines = schema.get_excluded_streamlines(c, uri)
            self.write(lines)

    def get_program_titles(self):
        uri = self.get_argument("uri", "nada...")
        with self._connect() as c:
            lines = schema.get_program_titles(c, uri)
            self.write(lines)

    def save_remember(self):
        self.storage.write_remember(self.request.body.decode("utf-8"))
        self.write(json.dumps({"status": "ok"}))

    def delete_remember(self):
        self.storage.delete_remember(self.request.body.decode("utf-8"))
        self.write(json.dumps({"status": "ok"}))

    def get_remembers(self):
        lines = self.storage.read_remembers()
        self.set_header("Content-Type", 'application/json')
        self.write(json.dumps(lines))

    def get_history(self):
        limit = int(self.get_argument("limit", "99999"))
        offset = int(self.get_argument("offset", "0"))
        history = self.storage.get_history(limit, offset)
        self.set_header("Content-Type", 'application/json')
        self.write(json.dumps(history))

    def get_all_refs(self):
        refs = self.storage.get_all_refs()
        self.set_header("Content-Type", 'application/json')
        self.write(json.dumps(refs))

    def update_album_data(self):
        album_uri = self.get_argument("album_uri")
        self.storage.update_album_images(album_uri, self.cache_holder)
        #todo: update from meta files, if any.

    def upload_album_image(self):
        album_uri = self.get_argument("album_uri")
        image_url = self.get_argument("image_url")

        album_path_and_name: AlbumKeyInfoRow = self.storage.get_album_path_and_name(album_uri)
        logger.info(f'Uploading image for album {album_path_and_name["name"]} to {album_path_and_name["path"]}')

        path = pathlib.Path(album_path_and_name["path"])
        path = path / f"{album_path_and_name["name"]} cover.jpg" #todo: not always a jpeg!!!!
        file_no = 1
        while path.exists():
            path = path.with_name(f"{album_path_and_name['name']} cover ({file_no}).jpg")
        import requests
        headers = {"User-Agent": "Eboplayer/1.0 (erik.bongers@outlook.com)"} # required by wikipedia
        img_data = requests.get(image_url, headers=headers).content
        with open(path, 'wb') as handler:
            handler.write(img_data)
        self.storage.update_album_images(album_uri, self.cache_holder)

    def create_playlist(self):
        playlist_name = self.get_argument("playlist_name")
        playlist_uri = self.storage.create_playlist(playlist_name)
        self.write({"status": "ok", "playlist_uri": playlist_uri})

    def add_playlist_file(self):
        playlist_def: PlaylistDict = self.storage.read_playlist_file(self.get_argument("playlist_uri"))
        file_uri = self.get_argument("file_uri")
        file_path = self.storage.get_file_path_for_uri(file_uri)
        if file_path is None:
            raise ValueError(f"Not a valid file uri {file_uri}")
        playlist_def["items"].append(str(file_path))
        self.storage.write_playlist_file(self.get_argument("playlist_uri"), playlist_def)
        self.storage.save_playlist_dict_in_db(playlist_def, file_path)

    def toggle_favorite(self):
        uri: Uri = self.get_argument("uri")
        is_favorite = self.storage.toggle_favorite(uri)
        self.write(json.dumps({"status": "ok", "is_favorite": is_favorite}))

    def get_favorite_uris(self):
        favorite_uris = self.storage.get_favorite_uris()
        self.set_header("Content-Type", 'application/json')
        self.write(json.dumps(favorite_uris))

    def get_favorites_playlist_name(self):
        self.set_header("Content-Type", 'text/plain')
        self.write(self.storage.get_root_meta()["favorites_playlist"])