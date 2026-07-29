import hashlib
from pathlib import Path
from sqlite3 import Connection

from mopidy.models import Ref
from mopidy.types import Uri

from mopidy_eboback.schema import _insert_or_replace
from mopidy_eboback.types import PlaylistRow


def get_playlists(c):
    return c.execute("SELECT * FROM playlists").fetchall()

def get_playlist_by_name(c, name) -> PlaylistRow | None:
    cursor = c.execute("SELECT uri, name, file_path FROM playlists WHERE name = ?", (name,)).fetchone()
    if cursor is None:
        return None
    row: PlaylistRow = {"uri": cursor[0], "name": cursor[1], "file_path": cursor[2]}
    return row

def delete_file_playlists(c):
    c.execute("DELETE FROM playlists where file_path IS NOT NULL")

def insert_playlist(c: Connection, name: str, file_path: Path) -> Uri:
    file_path_str = str(file_path)
    digest = hashlib.md5(str(file_path_str).encode(encoding="utf-8")).hexdigest()
    uri = "eboback:playlist:md5:" + digest
    _insert_or_replace(
        c,
        "playlists",
        {
            "uri": uri,
            "name": name,
            "file_path": file_path_str,
        },
    )
    return uri

def add_playlist_ref(c: Connection, playlist_uri: str, uri: str, ref_type: str, sequence: int) -> None:
    _insert_or_replace(c, "playlist_refs", {
        "playlist_uri": playlist_uri,
        "uri": uri,
        "ref_type": ref_type,
        "sequence": sequence
    })


def get_playlist_tracks(c, uri: Uri) -> list[Ref]:
    rows = c.execute("""
        SELECT refs.uri, track.name, refs.sequence
        FROM playlist_refs as refs
                 INNER JOIN track ON track.uri = refs.uri
        WHERE playlist_uri = ?
          AND refs.ref_type = 'track'
        UNION
        SELECT track.uri, track.name, album_refs.sequence
        FROM playlist_refs as album_refs
                 INNER JOIN track ON track.album = album_refs.uri
        WHERE playlist_uri = ?
          AND album_refs.ref_type = 'album'
        ORDER BY sequence;
    """,
    (uri,uri)).fetchall()
    return list(map(lambda row: Ref.track(name=row["name"], uri=row["uri"]), rows))

def read_playlist(c: Connection, playlist_uri: str) -> PlaylistRow:
    cursor = c.execute("""
        select uri, name, file_path from playlists where uri = ?;
    """, (playlist_uri,))
    row = cursor.fetchone()
    return {"uri": row[0], "name": row[1], "file_path": row[2]}

def add_playlist_file(c: Connection, playlist_uri: str, file_path: str):
    c.execute("insert into playlist_files(playlist_uri, path) values(?,?)", (playlist_uri, file_path))


def delete_playlist_items(c: Connection, playlist_uri: Uri):
    c.execute("delete from playlist_refs where playlist_uri = ?", (playlist_uri,))
    c.execute("delete from playlist_files where playlist_uri = ?", (playlist_uri,))
    c.execute("delete from playlist_excludes where playlist_uri = ?", (playlist_uri,))
    c.execute("delete from playlist_filters where playlist_uri = ?", (playlist_uri,))

def get_playlist_items_by_name(c, playlist_name: str) -> list[Uri]:
    rows = c.execute("""
        select path from playlist_files 
        where playlist_uri in (
            select uri from playlists where name = ?
            )
    """, (playlist_name,)).fetchall()
    return [row[0] for row in rows]

def get_playlist_items(c, playlist_uri: Uri) -> list[Uri]:
    rows = c.execute("""
        select path from playlist_files 
        where playlist_uri  = ?
    """, (playlist_uri,)).fetchall()
    return [row[0] for row in rows]
