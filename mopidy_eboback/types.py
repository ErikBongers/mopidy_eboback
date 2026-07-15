from typing import TypedDict, NotRequired, Optional

from mopidy_eboback.schema import GenreReplacementRow

type Uri = str

AlbumMetaDict = TypedDict('AlbumMetaDict', {
    'albumTitle': NotRequired[str],
    'genre': NotRequired[str],
    'imageFile': NotRequired[str],
    'showTrackNumbers': NotRequired[bool],
    'volumeAdjust': NotRequired[int]
    })

PlaylistItemStream = TypedDict('PlaylistItemStream', {
    'type': str,
    'uri': str,
    'name': str,
    'genre': str,
    'image': str,
    'exclude_streamlines': list[str],
    'program_titles': list[str]
    })

PlaylistDict = TypedDict('PlaylistDict', {
    'name': str,
    'items': list[PlaylistItemStream | str],
    })

empty_playlist_def: PlaylistDict = {
    'name': '',
    'items': [],
}

PlaylistRow = TypedDict('PlaylistRow', {'uri': str, 'name': str, 'file_path': str})

TrackRow = TypedDict('TrackRow', {
    "uri": str,
    "name": str,
    "album": str,
    "artists": str,
    "composers": str,
    "performers": str,
    "genre": str,
    "track_no": int,
    "disc_no": int,
    "date": str,
    "length": int,
    "bitrate": int,
    "comment": str,
    "musicbrainz_id": str,
    "last_modified": int,
    "exclude_streamlines": str,
    "program_titles": str
    })
RootMetaDef = TypedDict( "RootMetaDef", {
    "//name": str,
    "name": str,
    "//streams_folder": str,
    "streams_folder": str,
    "//favorites_playlist": str,
    "favorites_playlist": str,
    "//genre_replacements": str,
    "genre_replacements": list[GenreReplacementRow],
    "//saved_stream_lines": str,
    "saved_stream_lines": list[str]
    }
)

ImageDef = TypedDict("ImageDef", {
    "width": Optional[int],
    "height": Optional[int],
    "path": str,
    "embedded": bool
})
