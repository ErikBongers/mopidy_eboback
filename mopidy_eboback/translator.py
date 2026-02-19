from __future__ import annotations
#todo: remove the future annotation?
import logging
import os
import urllib
from pathlib import Path
from typing import Union

from mopidy_eboback.types import Uri

logger = logging.getLogger(__name__)


def local_uri_to_file_uri(local_uri: str, media_dir: Path) -> str:
    """Convert local track or directory URI to file URI."""
    path = local_uri_to_path(local_uri, media_dir)
    return path.as_uri()


def local_uri_to_path(local_uri: str, media_dir: Path) -> Path:
    """Convert local track or directory URI to absolute path."""
    if not local_uri.startswith(("eboback:directory:", "eboback:track:")):
        raise ValueError("Invalid URI.")
    uri_path = urllib.parse.urlsplit(local_uri.split(":", 2)[2]).path
    file_bytes = urllib.parse.unquote_to_bytes(uri_path)
    file_path = Path(os.fsdecode(file_bytes))
    return media_dir / file_path


def path_to_file_uri(path: Union[str, bytes, Path]) -> str:
    """Convert absolute path to file URI."""
    ppath = Path(os.fsdecode(path))
    assert ppath.is_absolute()
    return ppath.as_uri()


def path_to_track_or_stream_uri(path: Union[str, bytes, Path], media_dir: Path) -> str:
    """Convert path to local track URI."""
    if isinstance(path, str):
        if path.startswith("http"):
            return f"eboback:stream:{path}"
    ppath = Path(os.fsdecode(path))
    if ppath.is_absolute():
        ppath = ppath.relative_to(media_dir)
    quoted_path = urllib.parse.quote(bytes(ppath))
    return f"eboback:track:{quoted_path}"

def track_or_stream_uri_to_path_or_url(uri: Uri, media_dir: Path):
    if uri.startswith("eboback:stream:"):
        return uri[len("eboback:stream:"):]
    return local_uri_to_path(uri, media_dir)