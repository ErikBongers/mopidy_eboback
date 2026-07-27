import pathlib
from typing import TypedDict

from cyclopts import App

from mopidy import config, ext

from mopidy_eboback.commands import commands
from mopidy_eboback.schema import ImageDict


class ImageCache(TypedDict):
    image_cache: list[ImageDict] | None

class Extension(ext.Extension):
    dist_name = "mopidy-eboback" #todo: are these still required? They are not mentioned in the Example command: https://docs.mopidy.com/latest/guides/extensiondev/#example-backend
    ext_name = "eboback"
    version = "4.0.0"

    def get_default_config(self):
        return config.read(pathlib.Path(__file__).parent / "ext.conf")

    def get_config_schema(self):
        schema = super().get_config_schema()
        schema["max_search_results"] = config.Integer(minimum=0)
        schema["media_dir"] = config.Path()
        schema["scan_timeout"] = config.Integer(
            minimum=1000, maximum=1000 * 60 * 60
        )
        schema["scan_flush_threshold"] = config.Integer(minimum=0)
        schema["scan_follow_symlinks"] = config.Boolean()
        schema["included_file_extensions"] = config.List(optional=True)
        schema["excluded_file_extensions"] = config.List(optional=True)
        schema["directories"] = config.List()
        schema["timeout"] = config.Integer(optional=True, minimum=1)
        schema["use_artist_sortname"] = config.Boolean()
        schema["album_art_files"] = config.List(optional=True)
        return schema

    def setup(self, registry):
        from .backend import EbobackBackend

        registry.add("backend", EbobackBackend)
        registry.add(
            "http:app", {"name": self.ext_name, "factory": self.webapp}
        )

    def get_command(self) -> App | None:
        return commands.app

    def webapp(self, config, core):
        from mopidy_eboback.web.file_handlers import ImageHandler, IndexHandler, ImageByIdHandler
        from mopidy_eboback.web.action_handlers import DataHandler
        from mopidy_eboback.storage import IMG_URI_PREFIX, MEDIA_URI_PREFIX, IMG_ID_PREFIX
        from .webSocketHandler import WebsocketHandler

        data_dir = self.get_data_dir(config)
        image_dir = self.get_image_dir(config)
        media_dir = config["eboback"]["media_dir"]
        image_cache_holder: ImageCache = { "image_cache": None }
        return [
            (r"/(index.html)?", IndexHandler, {"root": image_dir}),
            (r"/" + IMG_URI_PREFIX + r"/(.+)", ImageHandler, {"path": image_dir}),
            (r"/" + IMG_ID_PREFIX + r"/(.+)", ImageByIdHandler, {"data_dir": data_dir, "path": "/", "config": config, "image_cache_holder": image_cache_holder}), # "/" means: expecting absolute paths! Needed because StaticFileHandler requires the path to be in the passed root.
            (r"/" + MEDIA_URI_PREFIX + r"/(.+)", ImageHandler, {"path": media_dir}),
            (r"/data/(.+)", DataHandler, {"data_dir": data_dir, "config": config, "image_cache_holder": image_cache_holder}),
            (r"/ws2/?", WebsocketHandler, {"config": config}),  # Why this pattern??? I know it's in mopidy http somewhere, but still...

        ]

    # TODO: Add *paths to Extension.get_data_dir()?
    @classmethod
    def get_data_subdir(cls, config, *paths):
        data_dir = cls.get_data_dir(config)
        dir_path = data_dir.joinpath(*paths)
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path

    @classmethod
    def get_image_dir(cls, config):
        return cls.get_data_subdir(config, "images")
