# mopidy-eboback

This is a backend extension for the mopidy-eboplayer frontend extension.
It is based on the mopidy-local extension.

> This extension is still in early development.

## These are main features

* Maps audio files in a local media storage to mopidy albums and tracks.
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
In the `mopidy.conf` file under `[eboback]` you specify the root of the drive:
```json

```