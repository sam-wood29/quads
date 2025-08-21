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
--     rebuy_setting TEXT,
--     stack_amount REAL,
--     script_name TEXT
-- )

-- CREATE TABLE actions (
--     id INTEGER PRIMARY KEY AUTOINCREMENT,
--     game_session_id INTEGER NOT NULL,
--     hand_id INTEGER NOT NULL,
--     step_number INTEGER NOT NULL,
--     player_id INTEGER,
--     position TEXT,
--     phase TEXT,
--     action TEXT NOT NULL,
--     amount REAL,
--     hole_cards TEXT,
--     hole_card1 TEXT,
--     hole_card2 TEXT,
--     community_cards TEXT,
--     hand_rank INTEGER,
--     hand_class TEXT,
--     pf_hand_class TEXT,
--     high_rank INTEGER,
--     low_rank INTEGER,
--     is_pair BOOLEAN,
--     is_suited BOOLEAN,
--     gap INTEGER,
--     chen_score REAL,
--     amount_to_call REAL,
--     percent_stack_to_call REAL,
--     highest_bet REAL,
--     pot_odds REAL,
--     detail TEXT,
--     FOREIGN KEY (game_session_id) REFERENCES game_sessions(id),
--     FOREIGN KEY (hand_id) REFERENCES hands(id),
--     FOREIGN KEY (player_id) REFERENCES players(id)
-- );

ALTER TABLE actions
RENAME COLUMN hand_rank to hand_rank_5;