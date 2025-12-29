-- mopidy-eboback-SQLite schema upgrade v6 -> v7

BEGIN EXCLUSIVE TRANSACTION;

alter table album
    add path TEXT;

alter table album
    add show_track_numbers integer default 0 not null;

alter table album
    add alt_name text;

 alter table album
    add image_file text;

create table playlists (
    uri       TEXT not null
        constraint playlists_pk
            primary key,
    name      TEXT not null,
    file_path TEXT not null
);

create table images (
    uri TEXT,
    file_path TEXT
);

create index images_uri_index on images (uri);

create table playlist_refs
(
    uri          TEXT not null,
    playlist_uri TEXT not null
        constraint playlist_refs_playlists_fk
            references playlists
);

create index playlist_refs_playlist_uri_index
    on playlist_refs (playlist_uri);

create index playlist_refs_uri_index
    on playlist_refs (uri);


PRAGMA user_version = 8;  -- update schema version

END TRANSACTION;
