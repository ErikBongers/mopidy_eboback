import mopidy
from mopidy.backend import PlaylistsProvider
from mopidy.models import Ref


class EbobackPlaylists(PlaylistsProvider):
    def __init__(self, backend):
        super().__init__(backend)

    def as_list(self) -> list[Ref]:
        just_a_ref = Ref.playlist(name="Whatever the list", uri="eboback:whatever")
        return [just_a_ref]
