DELETE FROM game_sessions;
DELETE FROM sqlite_sequence WHERE name = 'game_sessions';

DELETE FROM actions;
DELETE FROM sqlite_sequence WHERE name = 'actions'