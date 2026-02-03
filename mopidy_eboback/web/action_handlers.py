import json
import logging
import pathlib
import sqlite3
import urllib

import tornado.web
from mopidy.models import Ref

from mopidy_eboback import Extension, ImageCache
from mopidy_eboback import schema
from mopidy_eboback.schema import GenreDefRow
from mopidy_eboback.storage import LocalStorageProvider

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

    def options(self, *args):
        self.set_status(204)
        self.finish()

    def get(self, data_path: str):
        if data_path in ["get_album_meta", "get_genres", "write_root_meta", "get_excluded_streamlines", "get_program_titles", "get_remembers", "get_history", "get_all_refs", "update_album_images"]:
            func = getattr(self, data_path)
            func()
            return

        cnt = schema.count_albums(self._connect())
        self.write("Oops...no valid data request: " + data_path)
        self.write("" + str(cnt))

    def post(self, data_path):
        if data_path == "set_album_meta":
            self.set_album_meta()
            return
        if data_path == "add_ref_to_playlist": #todo: wrap in function without params, so we can use a path list like with GET.
            self.add_ref_to_playlist()
            self.write(json.dumps({
                "status": "ok"
            }))
            return
        if data_path == "save_remember":
            self.save_remember()
            self.write(json.dumps({"status": "ok"}))
            return
        if data_path == "get_album_metas":
            self.get_album_metas()
            return

        self.write("Oops...no valid data request: " + data_path)

    def get_album_meta(self):
        uri = self.get_argument("uri", "nada...")
        meta_file_path = self.uri_to_meta_path(uri)
        self.set_header("Content-Type", 'application/json')
        if meta_file_path.exists():
            self.write(meta_file_path.read_text())

    def get_album_metas(self):
        uris_comma_string = self.get_argument("uris", "nada...")
        uris: list[str] = uris_comma_string.split(",")
        metas: dict[str, dict] = {}
        for uri in uris:
            meta_file_path = self.uri_to_meta_path(uri)
            if meta_file_path.exists(): #todo: cache the meta in the db
                try:
                    metas[uri] = json.loads(meta_file_path.read_text()) #todo: don't first decode json to encode it again below.
                except Exception as e:
                    logger.error(f"Cannot parse meta file {meta_file_path}: {e}")

        self.set_header("Content-Type", 'application/json')
        self.write(json.dumps(metas))

    def set_album_meta(self):
        uri = self.get_argument("uri", "nada...")
        meta_file_path = self.uri_to_meta_path(uri)
        meta_file_path.write_text(self.request.body.decode("utf-8"))
        self.write("written:")
        self.write(self.request.body)

    def uri_to_meta_path(self, uri) -> pathlib.Path:
        path_string = schema.get_albums_path(self._connect(), (uri,))
        path = pathlib.Path(path_string)
        meta_file_path = path / "meta.eboplayer"
        return meta_file_path

    def _connect(self):
        if not self._connection:
            self._connection = sqlite3.connect(
                self._dbpath,
                factory=schema.Connection,
                timeout=self._config["timeout"],
                check_same_thread=False,
            )
        return self._connection

    def add_ref_to_playlist(self):
        logger.info("add_ref_to_playlist")
        logger.info(self.get_argument("item_uri"))
        logger.info(self.get_argument("playlist_uri"))
        logger.info(self.get_argument("ref_type"))
        logger.info(self.get_argument("sequence"))
        with self._connect() as c:
            schema.add_playlist_ref(
                c,
                self.get_argument("playlist_uri"),
                self.get_argument("item_uri"),
                self.get_argument("ref_type"),
                int(self.get_argument("sequence"))
            )

    def get_genres(self):
        with self._connect() as c:
            genres: list[GenreDefRow] = schema.get_genres(c)
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

    def update_album_images(self):
        import urllib.request
        album_uri = self.get_argument("album_uri", "--no album uri--")
        self.storage.update_album_images(album_uri)
        logger.info(f'Images in cache before clearing: {len(self.cache_holder["image_cache"])}')
        self.cache_holder["image_cache"] = None