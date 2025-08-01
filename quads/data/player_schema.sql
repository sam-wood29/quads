-- player_schema.sql

-- CREATE TABLE IF NOT EXISTS players (
--     id INTEGER PRIMARY KEY,
--     name TEXT
-- )

-- CREATE TABLE game_sessions (
--     id INTEGER PRIMARY KEY AUTOINCREMENT,
--     created_at TEXT DEFAULT CURRENT_TIMESTAMP,
--     object_game_type TEXT,
--     small_blind REAL,
--     big_blind REAL,
--     same_stack BOOLEAN,
--     stack_amount REAL,
--     script_name TEXT
-- )


-- DROP TABLE IF EXISTS game_sessions;
-- CREATE TABLE game_sessions (
--     id INTEGER PRIMARY KEY AUTOINCREMENT,
--     created_at TEXT DEFAULT CURRENT_TIMESTAMP,
--     object_game_type TEXT,
--     small_blind REAL,
--     big_blind REAL,
--     same_stack BOOLEAN,
--     rebuy_setting TEXT,
--     stack_amount REAL,
--     script_name TEXT
-- )

-- CREATE TABLE IF NOT EXISTS actions (
--     id INTEGER PRIMARY KEY AUTOINCREMENT,
--     hand_id INTEGER NOT NULL,
--     step_number INTEGER NOT NULL,
--     player_id INTEGER,
--     action TEXT NOT NULL,
--     amount REAL,
--     phase TEXT,
--     cards TEXT,
--     detail TEXT,
--     FOREIGN KEY (hand_id) REFERENCES hand(id),
--     FOREIGN KEY (player_id) REFERENCES players(id)
-- );

-- ALTER TABLE actions ADD COLUMN position TEXT;

-- DROP TABLE IF EXISTS actions;
-- DELETE FROM sqlite_sequence WHERE name = 'players';

CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_session_id INTEGER NOT NULL,
    hand_id INTEGER NOT NULL,
    step_number INTEGER NOT NULL,
    player_id INTEGER,
    action TEXT NOT NULL,
    amount REAL,
    phase TEXT,
    cards TEXT,
    detail TEXT,
    position TEXT,
    FOREIGN KEY (game_session_id) REFERENCES game_sessions(id),
    FOREIGN KEY (player_id) REFERENCES players(id)
);