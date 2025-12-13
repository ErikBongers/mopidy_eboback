import logging
import os
import pathlib

import tornado.web

logger = logging.getLogger(__name__)


class ImageHandler(tornado.web.StaticFileHandler):
    def get_cache_time(self, *args):
        return self.CACHE_MAX_AGE


class IndexHandler(tornado.web.RequestHandler):
    def initialize(self, root):
        self.root = root

    def get(self, path):
        return self.render("index.html", images=self.uris())

    def get_template_path(self):
        return pathlib.Path(__file__).parent / "www"

    def uris(self):
        from mopidy_eboback.storage import IMG_URI_PREFIX

        for _, _, files in os.walk(self.root):
            for file in files:
                yield pathlib.Path(IMG_URI_PREFIX).joinpath(file)
