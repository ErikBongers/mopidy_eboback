import logging
import os
import pathlib
from pathlib import Path

import tornado.web

from mopidy_eboback.schema import ImageDict
from mopidy_eboback.storage import LocalStorageProvider
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
    def initialize(self, data_dir: Path, path: str, config) -> None:
        self.root = path #todo: required by superclass. How to enforce?
        self.config = config["eboback"]
        self._dbpath = data_dir / "library.db"
        self._connection = None
        self.storage = LocalStorageProvider(config)
        self.image_files: list[ImageDict | None] | None = None

    def parse_url_path(self, url_path: str) -> str:
        if self.image_files is None:
            self.image_files = self.load_image_files()
        image_dict = self.image_files[int(url_path)]
        if image_dict:
            return image_dict["file_path"]
        return "---no image found at index---"

    def load_image_files(self):
        all_images: list[ImageDict] = self.storage.get_all_images()
        last_image = all_images[-1]
        image_list: list[ImageDict | None] = [None] * (last_image["id"]+1)
        for image in all_images:
            image_list[image["id"]] = image
        return image_list


