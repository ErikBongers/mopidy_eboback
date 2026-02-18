from typing import TypedDict, NotRequired

AlbumMetaDict = TypedDict('AlbumMetaDict', {
    'albumTitle': NotRequired[str],
    'genre': NotRequired[str],
    'imageFile': NotRequired[str],
    'showTrackNumbers': NotRequired[bool],
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
    'items': list[PlaylistItemStream]
    })

empty_playlist_def: PlaylistDict = {'name': '', 'items': []}