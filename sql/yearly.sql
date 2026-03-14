CREATE TABLE IF NOT EXISTS T_Resources (
    title_material TEXT PRIMARY KEY,
    type_material INTEGER,
    precure_season_name TEXT,
    ep_num INTEGER,
    ep_sp_num INTEGER,
    released_utc_09 TEXT,
    released_soundtrack_utc_09 TEXT,
    released_spinoff_utc_09 TEXT,
    duration_file TEXT,
    datetime_download TEXT,
    relative_path_of_file TEXT,
    relative_path_of_soundtracks TEXT,
    relative_path_of_lyrics TEXT
);

CREATE TABLE IF NOT EXISTS T_Registry (
    idx INTEGER PRIMARY KEY AUTOINCREMENT,
    title_material TEXT,
    datetime_range_utc_06 TEXT,
    type_repeat TEXT,
    type_listen TEXT,
    model_writer TEXT,
    lapsed_calculated TEXT,
    opener_model TEXT,
    name_of_opener_model TEXT,
    FOREIGN KEY (title_material) REFERENCES T_Resources(title_material)
);
