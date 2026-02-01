import logging
import os
import pathlib

import tornado.web

from mopidy_eboback.web.modified_static_file_handler import ModifiedStaticFiledHandler

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

class ImageByIdHandler(ModifiedStaticFiledHandler):
    def initialize(self, path: str, config) -> None:
        self.root = path #todo: required by superclass. How to enforce?
        self.config = config

    def parse_url_path(self, url_path: str) -> str:
        return "/media/DATA1/Music/RadioStreams/VRT_Klara_2020.svg"
        return "/var/lib/mopidy/eboback/images/dfe6b22aafd6304fc2e621145be961fc-75x75.jpeg"
        return "/var/lib/mopidy/eboback/images/3e25d50f44f943f8e9353f50ad20e6d8-9999x9999.svg"


