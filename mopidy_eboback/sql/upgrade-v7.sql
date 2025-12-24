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
    name      text not null
        constraint playlists_pk
            primary key,
    file_path TEXT not null
);



PRAGMA user_version = 8;  -- update schema version

END TRANSACTION;
