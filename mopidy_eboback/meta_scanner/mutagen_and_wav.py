import pathlib

import mutagen
from mopidy.models import Track, Artist, Album
from mutagen import FileType
from wavinfo import WavInfoReader


def test_meta_scanners():
    # mutagen_tags = mutagen.File("/media/DATA1/Music/Gidon Kremer/Hommage À Piazzolla/07 Soledad.wav")
    # print(mutagen_tags)
    #
    # wav_tags = WavInfoReader("/media/DATA1/Music/Gidon Kremer/Hommage À Piazzolla/07 Soledad.wav")
    # print(wav_tags)
    # info_metadata = wav_tags.info
    # print(info_metadata)
    pass

def scan_mutagen_full(absolute_path: pathlib.Path, track: Track) -> Track | None:
    mutagen_tags = mutagen.File(absolute_path)

    if not mutagen_tags:
        return None

    names = mutagen_tags.get("TIT2")  # todo: only works for mp3 !!! wma has a different tag name for the track title.
    if names:
        names = [str(name) for name in names]
        name = "; ".join(names)
        track = track.replace(name=name)

    return scan_mutagen_extra(mutagen_tags, track)


def scan_mutagen_meta(absolute_path: pathlib.Path, track: Track) -> Track:
    mutagen_tags = mutagen.File(absolute_path)
    return scan_mutagen_extra(mutagen_tags, track)


def scan_mutagen_extra(mutagen_tags: FileType, track: Track) -> Track:
    def not_empty(s: str) -> bool:
        return s is not None and s.strip() != ""

    genres = mutagen_tags.get("WM/Genre")
    if genres:
        genres = [str(genre) for genre in genres]
        genre = "; ".join(genres)
        track = track.replace(genre=genre)

    artists = mutagen_tags.get("WM/AlbumArtist")
    if artists:
        if len(artists) > 0:
            artists = [str(artist) for artist in artists]
            artists = filter(not_empty, artists)
            artists = [Artist(name=str(artist)) for artist in artists]
            track = track.replace(artists=artists)

    composers = mutagen_tags.get("WM/Composer")
    if composers:
        if len(composers) > 0:
            composers = [str(composer) for composer in composers]
            composers = filter(not_empty, composers)
            composers = [Artist(name=str(composer)) for composer in composers]
            track = track.replace(composers=composers)

    track_numbers = mutagen_tags.get("WM/TrackNumber")
    if track_numbers:
        track_numbers = [str(track_no) for track_no in track_numbers]
        if len(track_numbers) > 0:
            track = track.replace(track_no=int(track_numbers[0]))

    years = mutagen_tags.get("WM/Year")
    if years:
        years = [str(artist) for artist in years]
        if len(years) > 0:
            track = track.replace(date=years[0])
    return track

def scan_wavinfo(absolute_path: pathlib.Path):
    wav_tags = WavInfoReader(absolute_path)
    if wav_tags.info:
        name = ""
        artist = None
        genre = ""
        album = None
        if wav_tags.info.title:
            name = wav_tags.info.title
        if wav_tags.info.artist:
            artist = wav_tags.info.artist
            if artist:
                artist = Artist(name=artist)
        if wav_tags.info.genre:
            genre = wav_tags.info.genre
        if wav_tags.info.album:
            album = wav_tags.info.album
            if album:
                album = Album(name=album, artists=[artist])

        # todo: re-encode everything to utf-8?
        # if wav_tags.info.encoding:
        #     encoding = wav_tags.info.encoding
        return Track(name=name, artists=[artist], genre=genre, album=album)
    else:
        return None
