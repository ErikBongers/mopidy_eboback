from typing import TypedDict, NotRequired

AlbumMetaDict = TypedDict('AlbumMetaDict', {
    'albumTitle': NotRequired[str],
    'genre': NotRequired[str],
    'imageFile': NotRequired[str],
    'showTrackNumbers': NotRequired[bool],
    })

