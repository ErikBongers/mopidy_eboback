import logging
import operator
import pathlib
import re
import sqlite3
from sqlite3 import Row
from typing import TypedDict

from mopidy.models import Album, Artist, Image, Ref, Track

Uri = str

_IMAGE_SIZE_RE = re.compile(r".*-(\d+)x(\d+)\.(?:png|gif|jpeg)$")

_IMAGES_QUERY = "SELECT images FROM album WHERE images IS NOT NULL"

_ALBUM_IMAGE_QUERY = "SELECT images FROM album WHERE uri = ?"

_TRACK_IMAGE_QUERY = """
SELECT album.images AS images
  FROM track
  LEFT OUTER JOIN album ON track.album = album.uri
 WHERE track.uri = ?
"""

_BROWSE_QUERIES = {
    None: """
    SELECT CASE WHEN album.uri IS NULL THEN '%s' ELSE '%s' END AS type,
           coalesce(album.uri, track.uri) AS uri,
           coalesce(album.alt_name, album.name, track.name) AS name
      FROM track LEFT OUTER JOIN album ON track.album = album.uri
     WHERE %%s
     GROUP BY coalesce(album.uri, track.uri)
     ORDER BY %%s
    """
    % (Ref.TRACK, Ref.ALBUM),
    Ref.ALBUM: """
    SELECT '%s' AS type, uri AS uri, coalesce(alt_name, name) AS name
      FROM album
     WHERE %%s
     ORDER BY %%s
    """
    % Ref.ALBUM,
    Ref.ARTIST: """
    SELECT '%s' AS type, uri AS uri, name AS name
      FROM artist
     WHERE %%s
     ORDER BY %%s
    """
    % Ref.ARTIST,
    Ref.TRACK: """
    SELECT '%s' AS type, uri AS uri, name AS name
      FROM track
     WHERE %%s
     ORDER BY %%s
    """
    % Ref.TRACK,
}

_BROWSE_FILTERS = {
    None: {
        "album": "track.album = ?",
        "albumartist": "album.artists = ?",
        "artist": "track.artists = ?",
        "composer": "track.composers = ?",
        "date": "track.date LIKE ? || '%'",
        "genre": """
                coalesce(track.genre, 'null') IN
                   (
                   select coalesce(org_name, 'null')
                   from (
                        select new_name, org_name
                        from genre_replace
                        UNION
                        select genre, genre
                        from tracks
                        )
                   where coalesce(new_name, 'null') = ?
                   )
                """,
        "performer": "track.performers = ?",
        "max-age": "track.last_modified >= (strftime('%s', 'now') - ?) * 1000",
    },
    Ref.ARTIST: {
        "role": {
            "albumartist": """EXISTS (
                SELECT * FROM album WHERE album.artists = artist.uri
            )""",
            "artist": """EXISTS (
                SELECT * FROM track WHERE track.artists = artist.uri
            )""",
            "composer": """EXISTS (
                SELECT * FROM track WHERE track.composers = artist.uri
            )""",
            "performer": """EXISTS (
                SELECT * FROM track WHERE track.performers = artist.uri
            )""",
        },
    },
    Ref.ALBUM: {
        "albumartist": "artists = ?",
        "artist": """? IN (
            SELECT artists FROM track WHERE album = album.uri
        )""",
        "composer": """? IN (
            SELECT composers FROM track WHERE album = album.uri
        )""",
        "date": """EXISTS (
            SELECT * FROM track WHERE album = album.uri AND date LIKE ? || '%'
        )""",
        "genre": """? IN (
            SELECT coalesce(new_name, genre, 'null') genre
            FROM track 
            LEFT OUTER JOIN genre_replace on org_name = genre 
            WHERE album = album.uri
        )""",
        "performer": """? IN (
            SELECT performers FROM track WHERE album = album.uri
        )""",
        "max-age": """EXISTS (
            SELECT *
              FROM track
             WHERE album = album.uri
               AND last_modified >= (strftime('%s', 'now') - ?) * 1000
        )""",
    },
    Ref.TRACK: {
        "album": "album = ?",
        "albumartist": """? IN (
            SELECT artists FROM album WHERE uri = track.album
        )""",
        "artist": "artists = ?",
        "composer": "composers = ?",
        "date": "date LIKE ? || '%'",
        "genre": "genre IN ( select org_name from (select new_name, org_name from genre_replace UNION select genre, genre from tracks) where new_name = ?)",
        "performer": "performers = ?",
        "max-age": "last_modified >= (strftime('%s', 'now') - ?) * 1000",
    },
}

_LOOKUP_QUERIES = {
    Ref.ALBUM: """
    SELECT * FROM tracks WHERE album_uri = ?
    """,
    Ref.ARTIST: """
    SELECT * FROM tracks WHERE ? IN (artist_uri, albumartist_uri)
    """,
    Ref.TRACK: """
    SELECT * FROM tracks WHERE uri = ?
    """,
}

_SEARCH_SQL = """
SELECT *
  FROM tracks
 WHERE docid IN (SELECT docid FROM %s WHERE %s)
"""

_SEARCH_FILTERS = {
    "album": "album_uri = ?",
    "albumartist": "albumartist_uri = ?",
    "artist": "artist_uri = ?",
    "composer": "composer_uri = ?",
    "date": "date LIKE ? || '%'",
    "genre": "genre = ?",
    "performer": "performer_uri = ?",
    "max-age": "last_modified >= (strftime('%s', 'now') - ?) * 1000",
}

_SEARCH_FIELDS = {
    "uri",
    "track_name",
    "album",
    "artist",
    "composer",
    "performer",
    "albumartist",
    "genre",
    "track_no",
    "disc_no",
    "date",
    "comment",
    "musicbrainz_trackid",
    "musicbrainz_albumid",
    "musicbrainz_artistid",
}

schema_version = 8

logger = logging.getLogger(__name__)


class Connection(sqlite3.Connection):
    class Row(sqlite3.Row):
        def __getattr__(self, name):
            return self[name]

    def __init__(self, *args, **kwargs):
        sqlite3.Connection.__init__(self, *args, **kwargs)
        self.execute("PRAGMA foreign_keys = ON")
        self.row_factory = self.Row


def create_or_update_db(c) -> int | None:
    upgraded_to_version = None
    sql_dir = pathlib.Path(__file__).parent / "sql"
    user_version = c.execute("PRAGMA user_version").fetchone()[0]
    while user_version != schema_version:
        if user_version:
            logger.info("Upgrading SQLite database schema v%s", user_version)
            filename = "upgrade-v%s.sql" % user_version
        else:
            logger.info("Creating SQLite database schema v%s", schema_version)
            filename = "schema.sql"
        with open(sql_dir / filename) as fh:
            c.executescript(fh.read())
        new_version = c.execute("PRAGMA user_version").fetchone()[0]
        assert new_version != user_version
        user_version = new_version
        upgraded_to_version = new_version
    return upgraded_to_version


def tracks(c):
    return list(map(_track, c.execute("SELECT * FROM tracks")))

def list_distinct(c, field, query=tuple()):
    if field not in _SEARCH_FIELDS:
        raise LookupError("Invalid search field: %s" % field)
    sql = (
        """
    SELECT DISTINCT %s AS field
      FROM search
     WHERE field IS NOT NULL
    """
        % field
    )
    terms = []
    params = []
    for key, value in query:
        if key == "any":
            terms.append("? IN (%s)" % ",".join(_SEARCH_FIELDS))
        elif key in _SEARCH_FIELDS:
            terms.append("%s = ?" % key)
        else:
            raise LookupError("Invalid query field: %s" % key)
        params.append(value)
    if terms:
        sql += " AND " + " AND ".join(terms)
    logger.debug("SQLite list query %r: %s", params, sql)
    return list(map(operator.itemgetter(0), c.execute(sql, params)))


def dates(c, format="%Y-%m-%d"):
    return list(
        map(
            operator.itemgetter(0),
            c.execute(
                """
        SELECT DISTINCT(strftime(?, substr(date || '-01-01', 1, 10))) AS date
          FROM track
         WHERE date IS NOT NULL
         ORDER BY date
        """,
                [format],
            ),
        )
    )


def lookup(c, type, uri):
    return list(map(_track, c.execute(_LOOKUP_QUERIES[type], [uri])))


def exists(c, uri):
    rows = c.execute("SELECT EXISTS(SELECT * FROM track WHERE uri = ?)", [uri])
    return rows.fetchone()[0]


def browse(c, type=None, order=("type", "name COLLATE NOCASE"), **kwargs):
    filters, params = _filters(_BROWSE_FILTERS[type], **kwargs)
    sql = _BROWSE_QUERIES[type] % (
        " AND ".join(filters) or "1",
        ", ".join(order),
    )
    logger.debug("SQLite browse query %r: %s", params, sql)
    return [Ref(**row) for row in c.execute(sql, params)]


def search_tracks(c, query, limit, offset, exact, filters=tuple()):
    if not query:
        sql, params = ("SELECT * FROM tracks WHERE 1", [])
    elif exact:
        sql, params = _indexed_query(query)
    else:
        sql, params = _fulltext_query(query)
    clauses = []
    for kwargs in filters:
        f, p = _filters(_SEARCH_FILTERS, **kwargs)
        if f:
            clauses.append("(%s)" % " AND ".join(f))
            params.extend(p)
        else:
            logger.debug("Skipped SQLite search filter %r", kwargs)
    if clauses:
        sql += " AND (%s)" % " OR ".join(clauses)
    sql += " LIMIT ? OFFSET ?"
    params += [limit, offset]
    logger.debug("SQLite search query %r: %s", params, sql)
    rows = c.execute(sql, params)
    return list(map(_track, rows))


def get_unreferenced_images(c):
    rows = c.execute("""
        select file_path 
        from images
        where embedded = TRUE
        and id not in (
            select id_min_image from album where id_min_image is not null
            union
            select id_max_image from album where id_max_image is not null
        )
        """)
    return [row[0] for row in rows.fetchall()]

def delete_unreferenced_images(c):
    c.execute("""
        delete 
        from images
        where embedded = TRUE
        and id not in (
            select id_min_image from album where id_min_image is not null
            union
            select id_max_image from album where id_max_image is not null
            )
        """)

def get_album_images(c, uri):
    images = []
    for row in c.execute(_ALBUM_IMAGE_QUERY, (uri,)):
        images.extend(_images(row.images))
    return images


def get_track_images(c, uri):
    images = []
    for row in c.execute(_TRACK_IMAGE_QUERY, (uri,)):
        images.extend(_images(row.images))
    return images


def insert_artists(c, artists):
    if not artists:
        return None
    if len(artists) != 1:
        logger.warning("Ignoring multiple artists: %r", artists)
    artist = next(iter(artists))
    _insert_or_replace(
        c,
        "artist",
        {
            "uri": artist.uri,
            "name": artist.name,
            "sortname": artist.sortname,
            "musicbrainz_id": artist.musicbrainz_id,
        },
    )
    return artist.uri


def insert_album(c, album, images:set[str], file_path=None):
    if not album or not album.name:
        return None
    image_str: str | None = None
    if len(images):
        image_str = " ".join(images)
    _insert_or_replace(
        c,
        "album",
        {
            "uri": album.uri,
            "name": album.name,
            "artists": insert_artists(c, album.artists),
            "num_tracks": album.num_tracks,
            "num_discs": album.num_discs,
            "date": album.date,
            "musicbrainz_id": album.musicbrainz_id,
            "images": image_str,
            "path": file_path
        },
    )
    return album.uri


def insert_track(c: Connection, track, images:set[str], file_path: str | None = None):
    _insert_or_replace(
        c,
        "track",
        {
            "uri": track.uri,
            "name": track.name,
            "album": insert_album(c, track.album, images, file_path),
            "artists": insert_artists(c, track.artists),
            "composers": insert_artists(c, track.composers),
            "performers": insert_artists(c, track.performers),
            "genre": track.genre,
            "track_no": track.track_no,
            "disc_no": track.disc_no,
            "date": track.date,
            "length": track.length,
            "bitrate": track.bitrate,
            "comment": track.comment,
            "musicbrainz_id": track.musicbrainz_id,
            "last_modified": track.last_modified,
        },
    )
    return track.uri

def insert_stream_track(c, track, exclude_streamlines: str, program_titles: str):
    _insert_or_replace(
        c,
        "track",
        {
            "uri": track.uri,
            "name": track.name,
            "album": None,
            "artists": None,
            "composers": None,
            "performers": None,
            "genre": track.genre,
            "track_no": None,
            "disc_no": None,
            "date": None,
            "length": 0,
            "bitrate": None,
            "comment": None,
            "musicbrainz_id": None,
            "last_modified": None,
            "exclude_streamlines": exclude_streamlines,
            "program_titles": program_titles
        },
    )
    return track.uri

def get_playlists(c):
    return c.execute("SELECT * FROM playlists").fetchall()

def delete_file_playlists(c):
    c.execute("DELETE FROM playlists where file_path IS NOT NULL")

def insert_playlist(c, uri, name, file_path):
    _insert_or_replace(
        c,
        "playlists",
        {
            "uri": uri,
            "name": name,
            "file_path": file_path,
        },
    )

def insert_genre_replacement(c, org_name, new_name):
    _insert_or_replace(
        c,
        "genre_replace",
        {
            "org_name": org_name,
            "new_name": new_name,
        },
    )

def add_playlist_ref(c: Connection, playlist_uri: str, uri: str, ref_type: str, sequence: int) -> None:
    _insert_or_replace(c, "playlist_refs", {
        "playlist_uri": playlist_uri,
        "uri": uri,
        "ref_type": ref_type,
        "sequence": sequence
    })


def get_playlist_tracks(c, uri: Uri):
    return c.execute("""
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

def insert_image(c: Connection, file_path, width: int, height: int, embedded: bool) -> int:
    cursor = c.execute("select id from images where file_path = ?", (file_path,))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor = c.execute("""
        insert into images (id, file_path, width, height, embedded) 
        values((select max(id)+1 from images), ?, ?, ?, ?) 
        returning id""",
        (file_path, width, height, embedded))
    image_id =  cursor.fetchone()[0]
    return image_id

def delete_track(c, uri):
    c.execute("DELETE FROM track WHERE uri = ?", (uri,))


def count_tracks(c):
    return c.execute("SELECT count(*) FROM track").fetchone()[0]


def cleanup(c):
    c.execute(
        """
    DELETE FROM album WHERE NOT EXISTS (
        SELECT uri FROM track WHERE track.album = album.uri
    )
    """
    )
    c.execute(
        """
    DELETE FROM artist WHERE NOT EXISTS (
        SELECT uri FROM track WHERE track.artists = artist.uri
         UNION
        SELECT uri FROM track WHERE track.composers = artist.uri
         UNION
        SELECT uri FROM track WHERE track.performers = artist.uri
         UNION
        SELECT uri FROM album WHERE album.artists = artist.uri
    )
    """
    )
    c.execute("ANALYZE")


def clear_except_history(c):
    c.executescript(
        """
    DELETE FROM track;
    DELETE FROM album;
    DELETE FROM artist;
    DELETE FROM playlists;
    DELETE FROM playlist_excludes;
    DELETE FROM playlist_filters;
    DELETE FROM playlist_refs;
    DELETE FROM images;
    DELETE FROM track_images;
    DELETE FROM album_images;
    DELETE FROM genre_replace;
    VACUUM;
    """
    )


def _insert_or_replace(c, table, params):
    sql = "INSERT OR REPLACE INTO {} ({}) VALUES ({})".format(
        table, ", ".join(params.keys()), ", ".join(["?"] * len(params))
    )
    logger.debug("SQLite insert statement: %s %r", sql, params.values())
    return c.execute(sql, list(params.values()))


def _filters(mapping, role=None, **kwargs):
    filters, params = [], []
    if role and "role" in mapping:
        rolemap = mapping["role"]
        if isinstance(role, (str, bytes)):
            filters.append(rolemap[role])
        else:
            filters.append(" OR ".join(rolemap[r] for r in role))
    for key, value in kwargs.items():
        if key in mapping:
            filters.append(mapping[key])
            params.append(value)
        else:
            logger.debug("Skipped SQLite filter expression: %s=%r", key, value)
    return (filters, params)


def _indexed_query(query):
    terms = []
    params = []
    for field, value in query:
        if field == "any":
            terms.append("? IN (%s)" % ",".join(_SEARCH_FIELDS))
        elif field in _SEARCH_FIELDS:
            terms.append("%s = ?" % field)
        else:
            raise LookupError("Invalid search field: %s" % field)
        params.append(value)
    return (_SEARCH_SQL % ("search", " AND ".join(terms)), params)


def _fulltext_query(query):
    terms = []
    params = []
    for field, value in query:
        if field == "any":
            terms.append(_SEARCH_SQL % ("fts", "fts MATCH ?"))
        elif field in _SEARCH_FIELDS:
            terms.append(_SEARCH_SQL % ("fts", "%s MATCH ?" % field))
        else:
            raise LookupError("Invalid search field: %s" % field)
        params.append(value)
    return (" INTERSECT ".join(terms), params)


def _track(row):
    kwargs = {
        "uri": row.uri,
        "name": row.name,
        "genre": row.genre,
        "track_no": row.track_no,
        "disc_no": row.disc_no,
        "date": row.date,
        "length": row.length,
        "bitrate": row.bitrate,
        "comment": row.comment,
        "musicbrainz_id": row.musicbrainz_id,
        "last_modified": row.last_modified,
    }
    if row.album_uri is not None:
        if row.albumartist_uri is not None:
            albumartists = [
                Artist(
                    uri=row.albumartist_uri,
                    name=row.albumartist_name,
                    sortname=row.albumartist_sortname,
                    musicbrainz_id=row.albumartist_musicbrainz_id,
                )
            ]
        else:
            albumartists = None
        kwargs["album"] = Album(
            uri=row.album_uri,
            name=row.album_name,
            artists=albumartists,
            num_tracks=row.album_num_tracks,
            num_discs=row.album_num_discs,
            date=row.album_date,
            musicbrainz_id=row.album_musicbrainz_id,
        )
    if row.artist_uri is not None:
        kwargs["artists"] = [
            Artist(
                uri=row.artist_uri,
                name=row.artist_name,
                sortname=row.artist_sortname,
                musicbrainz_id=row.artist_musicbrainz_id,
            )
        ]
    if row.composer_uri is not None:
        kwargs["composers"] = [
            Artist(
                uri=row.composer_uri,
                name=row.composer_name,
                sortname=row.composer_sortname,
                musicbrainz_id=row.composer_musicbrainz_id,
            )
        ]
    if row.performer_uri is not None:
        kwargs["performers"] = [
            Artist(
                uri=row.performer_uri,
                name=row.performer_name,
                sortname=row.performer_sortname,
                musicbrainz_id=row.performer_musicbrainz_id,
            )
        ]
    return Track(**kwargs)

def count_albums(c):
    res = c.execute("select count() as cnt from album")
    cnt, = res.fetchone()
    return cnt

def get_albums_path(c, uri): #todo: rename get_album_path
    res = c.execute("select path from album where uri = ?", uri)
    path, = res.fetchone()
    return path

def get_album_paths_and_path_counts(c) -> list[Row] :
    res = c.execute(
        """
        select uri, name, album.path, counts.cnt as albums_in_dir
        from album,
            (select path, count(name) cnt
            from album
            group by path
            ) as counts
        where album.path = counts.path;
        """
    )
    return res.fetchall()

def update_album_meta(c, uri, meta_data):
    c.execute(
        """
        update album set alt_name = ? where uri = ?
        """, (meta_data["albumTitle"], uri))


def _images(field):
    images = []
    for uri in field.split() if field else []:
        m = _IMAGE_SIZE_RE.match(uri)
        if m:
            width = int(m.group(1))
            height = int(m.group(2))
            images.append(Image(uri=uri, width=width, height=height))
        else:
            images.append(Image(uri=uri))
    return images


def get_images(c, uri):
    return c.execute("""
    select * 
    from images
    where id in (
        select id from track_images where track_uri = ?
        union
        select album_images.image_id from album_images where album_uri = ?
        union
        select album_images.image_id from album_images where album_uri in (
            select tracks.album_uri from tracks where tracks.uri = ?
        )
    )""", (uri,uri,uri)).fetchall()

GenreDefRow = TypedDict('GenreDefRow', {'genre': str, 'replacement': str})

def get_genres(c) -> list[GenreDefRow]:
    rows = c.execute("""
        select distinct 
            coalesce(genre, 'null') as genre, 
            genre_replace.new_name as replacement
        from track
        LEFT OUTER JOIN genre_replace on genre = genre_replace.org_name
    """).fetchall()
    def to_genre_def(row) -> GenreDefRow:
        return {'genre': row[0], 'replacement': row[1]}
    return list(map(to_genre_def, rows))

def get_genre_defs(c) -> list[GenreDefRow]:
    rows = c.execute("""
        select * from genre_replace
    """).fetchall()
    def to_genre_def(row) -> GenreDefRow:
        return {'genre': row[0], 'replacement': row[1]}
    return list(map(to_genre_def, rows))


def get_excluded_streamlines(c, uri: str):
    row = c.execute("select exclude_streamlines from track where uri = ?", (uri,)).fetchone()
    return row[0] if row else None

def get_program_titles(c, uri: str):
    row = c.execute("select program_titles from track where uri = ?", (uri,)).fetchone()
    return row[0] if row else None

def insert_history_line(c: Connection, moment: int, name: str, uri: str, ref_type: str):
    _insert_or_replace(c, "history", {"moment": moment, "name": name, "uri": uri, "type": ref_type})


def get_history(c, limit: int, offset: int):
    def to_hist_def(row):
        return {'moment': row[0], 'type': row[1], 'uri': row[2], 'name': row[3], 'ref_count': row[4], 'album': row[5], 'artist': row[6]}
    rows = c.execute("""
            select history.moment, history.type, history.uri, coalesce(track.name, history.name) as name, history.ref_count, album.name as album, artist.name as artist
            from compressed_history as history
            left outer join track on history.uri = track.uri
            left outer join album on track.album = album.uri
            left outer join artist on track.artists = artist.uri
            order by moment desc
            limit ? offset ?
        """,
        (limit, offset)).fetchall()
    return list(map(to_hist_def, rows))


def update_album_dates(c: Connection):
    logger.info("Updating album dates")
    c.execute("""
            update album 
            set last_modified = (select max(track.last_modified) 
                                 from track 
                                 where album.uri = track.album)
             """)


def get_all_refs(c: Connection):
    def to_ref(row):
        return {'refType': row[0], 'uri': row[1], 'name': row[2], 'lastModified': row[3], 'idMinImage': row[4], 'idMaxImage': row[5]}
    rows = c.execute("select ref_type, uri, name, last_modified, id_min_image, id_max_image from all_refs")
    return list(map(to_ref, rows))


def update_all_album_min_max_images(c: Connection):
    c.execute("""
        update album
        set id_max_image = album_images_min_max.max_id,
            id_min_image = album_images_min_max.min_id
        from album_images_min_max
        where album.uri = album_images_min_max.uri
        """)

ImageDict = TypedDict('ImageDict', {'id': int, 'uri': str, 'file_path': str, 'width': int, 'height': int})

def get_all_images(c) -> list[ImageDict]:
    def to_image(row):
        return {'id': row[0], 'file_path': row[1], 'width': row[2], 'height': row[3]}
    rows = c.execute("select id, file_path, width, height from images order by id")
    return list(map(to_image, rows))


def add_album_image(c: Connection, uri: str, image_id: int):
    c.execute("insert into album_images(album_uri, image_id) values(?,?)", (uri, image_id))

def add_track_image(c: Connection, uri: str, image_id: int):
    c.execute("insert into track_images(track_uri, image_id) values(?,?)", (uri, image_id))

def get_album_track_uris(c, album_uri: str) -> list[str]:
    rows = c.execute("select distinct uri from track where album = ?", (album_uri,)).fetchall()
    return [row[0] for row in rows]