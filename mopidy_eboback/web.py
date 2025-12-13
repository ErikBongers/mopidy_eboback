import logging
import os
import pathlib
import sqlite3

import tornado.web
from mopidy_eboback import schema
from . import Extension

logger = logging.getLogger(__name__)


class ImageHandler(tornado.web.StaticFileHandler):
    def get_cache_time(self, *args):
        return self.CACHE_MAX_AGE


class IndexHandler(tornado.web.RequestHandler):
    # noinspection PyAttributeOutsideInit
    def initialize(self, root):
        self.root = root

    def get(self, path):
        return self.render("index.html", images=self.uris())

    # noinspection PyMethodMayBeStatic
    def get_template_path(self):
        return pathlib.Path(__file__).parent / "www"

    def uris(self):
        from mopidy_eboback.storage import IMG_URI_PREFIX

        for _, _, files in os.walk(self.root):
            for file in files:
                yield pathlib.Path(IMG_URI_PREFIX).joinpath(file)



class DataHandler(tornado.web.RequestHandler):
    # noinspection PyAttributeOutsideInit
    def initialize(self, data_dir, config):
        self._dbpath = data_dir / "library.db"
        self._connection = None
        self._config = config[Extension.ext_name]

    def get(self, data_path):
        cnt = schema.count_albums(self._connect())
        self.write("Hello, data for: " + data_path)
        self.write("" + str(cnt))

    def _connect(self):
        if not self._connection:
            self._connection = sqlite3.connect(
                self._dbpath,
                factory=schema.Connection,
                timeout=self._config["timeout"],
                check_same_thread=False,
            )
        return self._connection
