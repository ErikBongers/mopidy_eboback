-- mopidy-eboback-SQLite schema upgrade v6 -> v7

BEGIN EXCLUSIVE TRANSACTION;

alter table album
    add path TEXT;

PRAGMA user_version = 8;  -- update schema version

END TRANSACTION;
