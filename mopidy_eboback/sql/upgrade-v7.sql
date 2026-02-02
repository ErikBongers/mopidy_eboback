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
    id INTEGER  PRIMARY KEY AUTOINCREMENT,
    file_path TEXT,
    width INTEGER,
    height INTEGER,
    embedded BOOLEAN NOT NULL
);

create index images_path_index on images (file_path);

create table playlist_refs
(
    uri          TEXT not null,
    sequence     INTEGER not null,
    playlist_uri TEXT not null
        constraint playlist_refs_playlists_fk
            references playlists ON DELETE CASCADE,
    ref_type     TEXT not null
);

create index playlist_refs_playlist_uri_index
    on playlist_refs (playlist_uri);

create index playlist_refs_uri_ref_type_index
  on playlist_refs (playlist_uri, ref_type);

create index playlist_refs_uri_index
    on playlist_refs (uri);

create table playlist_filters
(
    playlist_uri TEXT not null
        constraint playlist_filters_playlists_fk
            references playlists ON DELETE CASCADE,
    sequence INTEGER not null,
    search_text TEXT not null,
    album BOOLEAN not null,
    artist BOOLEAN not null,
    track BOOLEAN not null,
    genre BOOLEAN not null
);

create index playlist_filters_playlist_uri_index
    on playlist_filters (playlist_uri);

create table playlist_excludes
(
    playlist_uri TEXT not null
        constraint playlist_excludes_playlists_fk
            references playlists ON DELETE CASCADE,
    sequence INTEGER not null,
    uri TEXT not null
);

create index playlist_excludes_playlist_uri_index
    on playlist_excludes (playlist_uri);

create table genre_replace
(
    org_name TEXT not null primary key,
    new_name TEXT
);

alter table track add column exclude_streamlines text;
alter table track add column program_titles text;

create table history
(
    moment integer not null,
    type text,
    uri text,
    name text,
    ref_count integer default 1
);

create index history_moment_idx on history (moment);
create index history_moment_uri_idx on history (moment, uri);

create view compressed_history as
WITH
    partitioning AS
        (
            SELECT *,
                   ROW_NUMBER() OVER (ORDER BY moment)
                       -
                   ROW_NUMBER() OVER (PARTITION BY type, uri, name ORDER BY moment)
                       AS partition_id
            FROM
                history
        )
SELECT
    MAX(moment) as moment,
    type, uri, name,
    COUNT(*) as row_count,
    SUM(ref_count) as ref_count
FROM
    partitioning
GROUP BY

    type, uri, name,
    partition_id
ORDER BY
    MAX(moment);

create view favorites as
    with dedup as (
        with weighted_history as (
            with
                latest as (
                    select 100000 as base_weight, '1. latest' as period, h.*
                    from compressed_history as h
                    order by moment desc
                    limit 1
                    ),
                last_days as (
                    select 1000 as base_weight, '2. last days' as period, h.*
                    from compressed_history as h
                    where moment > unixepoch() - 60 * 60 * 24 * 2
                    order by base_weight desc, moment desc
                    limit -1 offset 1
                ),
                last_year as (
                    select 100 as base_weight, '3. last year' as period, h.*
                    from compressed_history as h
                    where moment > unixepoch() - 60 * 60 * 24 * 365
                    and moment < unixepoch() - 60 * 60 * 24 * 2
                )
            select *, 0 as days_ago -- days not relevant
            from latest
            union
            select*, (unixepoch() - moment) / 60 / 60 / 24 as days_ago
            from last_days
            union
            select *, (unixepoch() - moment) / 60 / 60 / 24 as days_ago
            from last_year
            )
        select base_weight+(ref_count*10)-days_ago as weight, ref_count, days_ago, *
        from weighted_history
        )
    select max(weight) as weight, substr(min(period), 4) as period, max(type) as type, uri, max(name) as name, sum(ref_count) as ref_count from dedup
    group by uri
    order by weight desc;

alter table album add column last_modified integer;

create view all_refs as
-- ALL_REFS for tracks without an album
with max_images as (
    select track.*, images.id as id_max_image, row_number() over (partition by track.uri order by width*height desc) as rank
    from track
    left outer join track_images on track.uri = track_images.track_uri
    left outer join images on track_images.image_id = images.id
    where track.album is null
    ),
    min_images as (
    select track.*, images.id as id_min_image, row_number() over (partition by track.uri order by width*height) as rank
    from track
    left outer join track_images on track.uri = track_images.track_uri
    left outer join images on track_images.image_id = images.id
    where track.album is null
    )
select case when max_images.last_modified is null then 'radio' else 'track' end as ref_type, max_images.uri, max_images.name, max_images.last_modified, min_images.id_min_image, max_images.id_max_image
from max_images, min_images
where max_images.rank = 1
and min_images.rank = 1
and max_images.uri = min_images.uri
union
-- ALL_REFS for tracks with an album
select case when track.last_modified is null then 'radio' else 'track' end as ref_type, track.uri, track.name, track.last_modified, album.id_min_image, album.id_max_image
from track, album
where track.album = album.uri
union
select 'album' as ref_type, uri, name, last_modified, id_min_image, id_max_image from album
union
select 'artist' as ref_type, uri, name, null as last_modified, null, null from artist
union
select distinct 'genre' as ref_type, replacement as uri, replacement as name, null, null, null
from genres
where replacement is not null and replacement != ''
union
select distinct 'genre' as ref_type, genre as uri, genre as name, null, null, null
from genres
where replacement is null
union
select 'playlist' as ref_type, uri, name, null, null, null
from playlists;

create view genres as
        select distinct
            coalesce(genre, 'null') as genre,
            genre_replace.new_name as replacement
        from track
        LEFT OUTER JOIN genre_replace on genre = genre_replace.org_name;

create table album_images
(
    album_uri TEXT not null,
    image_id INTEGER not null,
    FOREIGN KEY (album_uri) REFERENCES album(uri) ON DELETE CASCADE
);

create unique index album_images_idx on album_images (album_uri, image_id);

create table track_images
(
    track_uri TEXT not null,
    image_id INTEGER not null,
    FOREIGN KEY (track_uri) REFERENCES track(uri) ON DELETE CASCADE
);

create unique index track_images_idx on track_images (track_uri, image_id);

create view album_images_min_max as
with max_images as (
    select album_images.album_uri, id, width*height as size, row_number() over (partition by album_images.album_uri order by width*height desc) as rank
    from album_images
    join images on images.id = album_images.image_id
    order by album_images.album_uri
    ),
    min_images as (
    select album_images.album_uri, id, width*height as size, row_number() over (partition by album_images.album_uri order by width*height) as rank
    from album_images
    join images on images.id = album_images.image_id
    order by album_images.album_uri
    )
select max_images.album_uri as uri, min_images.id as min_id, max_images.id as max_id
from max_images, min_images
where max_images.album_uri = min_images.album_uri
and max_images.rank = 1
and min_images.rank = 1;

alter table album add column id_max_image integer;
alter table album add column id_min_image integer;

PRAGMA user_version = 8;  -- update schema version

END TRANSACTION;
