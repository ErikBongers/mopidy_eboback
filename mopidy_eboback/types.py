from typing import TypedDict, NotRequired

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