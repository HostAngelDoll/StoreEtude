CREATE TABLE T_Type_Catalog_Reg (
    idx INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT,
    category TEXT,
    description TEXT
);

CREATE TABLE T_Opener_Models (
    id_model INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT,
    start_validity_overwrite TEXT,
    end_validity_overwrite TEXT,
    start_validity_locally TEXT,
    end_validity_locally TEXT,
    model_name_overwrite TEXT,
    model_name_locally TEXT,
    components TEXT,
    description TEXT
);

CREATE TABLE T_Type_Resources (
    idx INTEGER PRIMARY KEY AUTOINCREMENT,
    type_resource TEXT
);

CREATE TABLE T_Seasons (
    year INTEGER,
    prefix_by_year TEXT,
    is_spinoff INTEGER,
    precure_season_name TEXT PRIMARY KEY,
    japanese_name TEXT,
    romaji_name TEXT,
    episode_total INTEGER,
    theme_description TEXT,
    release_date TEXT,
    path_master TEXT
);
