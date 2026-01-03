# mopidy-eboback

This is a backend extension for the mopidy-eboplayer frontend extension.
It is based on the mopidy-local extension.
However, mopidy-eboback allows for metadata files within the media library, which facilitates easy copying and sharing of libraries.
The philosophy is that the specifications for the library are owned by the library and not the software. 

> This extension is still in early development.

## These are main features

* Maps audio files in a specified local media storage to mopidy albums and tracks.
    > TODO: allow for multiple media storages to allow multiple people to share their music drives.
* Extracts images from the audio files, if present.
* Extracts images from the local media storage.
  > TODO: this assumes tracks are in album folders. Otherwise it's unclear which image belongs to which track/album.
  > Allow `.eboplayer` file to specify which image belongs to which track/album. 
* Stores settings per album in the directory for a given album.
  > TODO: tracks may not be stored in a directories that matches the albums. 
  > Perhaps all tracks are in one big directory. Therefor the `.eboplayer` files
  > should either allow all data to be stored directly or have different `eboplayer` files per album.
  > Also note that not all tracks may belong to an album.
  > User should be able to edit the files directly - so preferably no big monolith.
* Loads playlists from `.wpl` files.
  > TODO !
* Has complex playlists that support.
  * nesting of playlists (not yet implemented)
  * playlists based on filters (queries) (not yet implemented)
* Store streams as tracks in a special playlist for which the name is defined in `root.eboplayer`.

## Configuration
### mopidy.conf
In the `mopidy.conf` file this is the only setting:

```
[eboback]
media_dir=path/to/your/music/storage
```
For more information on where to find this config file, Google "Mopidy Configuration file location".
### root.eboplayer
In the `root.eboplayer` you specify general settings for the library:
```json
{
	"//name": "A name for this media source",
	"name": "My media player library",
	"//streams_folder": "Relative path to folder where stream images, etc are stored",
	"streams_folder": "/RadioStreams",
    "//genre_groups": "You can also use this to create aliases",
    "genre_groups": {
       "rock": ["metal", "hard rock"],
       "Classical" : ["Baroque", "Romantic"]
    },
    "//genre_replacements": "These HIDE the original genre. Usefull to reduce clutter",
    "genre_replacements": {
       "Classical" : ["Classical music", "Classical Period"]
    },
    "//excluded_ext": "List of file extensions to exclude from the library",
    "excluded_ext": ["jpeg", "jpg", "txt"]
}
```

## Meta data for directories and albums
Eboplayer will look for a `.eboplayer` file in each directory.
A directory may contain tracks for a single or multiple albums.
Eboplayer determines the album name for a track from it's metadata tags within the file.
Depending on whether a directory contains tracks for multiple albums or a single album, 
eboplayer will look for different versions of the `.eboplayer` file.

### Single album directory

In case a directory contains tracks for a single album, eboplayer will 
look for a `.eboplayer` or a `meta.eboplayer` file in the directory.

### Multiple album directory

In case a directory contains tracks for multiple albums, eboplayer will 
look for `ALBUM_NAME.eboplayer` files in the directory, where `ALBUM_NAME` is the name of the album.
You can therefor have multiple `ALBUM_NAME.eboplayer` files in one directory.
If there are no tracks for a given album, eboplayer will ignore the related `ALBUM_NAME.eboplayer` file.

### Virtual albums

If you want to create virtual albums, you can do so by creating a `album.eboplayer` file in the directory.
Note that virtual albums are not the same as playlists.
If you want to create multiple virtual albums, you can create multiple `ALBUM_NAME.album.eboplayer` files.

## Playlists

Playlists are retrieved from `.wpl`, `.m3u` and `playlist.eboplayer` files in the media directory.
Eboplayer playlists allow for nesting of playlists and queries.

## Scanning

Changes to configuration files are not picked up automatically.
You need run the command `sudo mopidyctl eboback update_meta` to scan the media directory.
  > TODO: this probably needs to be integraded in the `scan` command.