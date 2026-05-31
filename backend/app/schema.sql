CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    notes TEXT,
    recurrence_type TEXT NOT NULL DEFAULT 'none'
        CHECK (recurrence_type IN ('none', 'daily', 'weekly', 'monthly')),
    recurrence_interval INTEGER NOT NULL DEFAULT 1
        CHECK (recurrence_interval > 0),
    recurrence_until TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS idx_events_user_id ON events (user_id);
CREATE INDEX IF NOT EXISTS idx_events_start_time ON events (start_time);
CREATE INDEX IF NOT EXISTS idx_events_recurrence_type ON events (recurrence_type);

CREATE TABLE IF NOT EXISTS event_exceptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    series_id INTEGER NOT NULL,
    original_start_time TEXT NOT NULL,
    exception_type TEXT NOT NULL
        CHECK (exception_type IN ('cancelled', 'modified')),
    title TEXT,
    start_time TEXT,
    end_time TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (series_id) REFERENCES events (id),
    UNIQUE (user_id, series_id, original_start_time)
);

CREATE INDEX IF NOT EXISTS idx_event_exceptions_series_id ON event_exceptions (series_id);
CREATE INDEX IF NOT EXISTS idx_event_exceptions_original_start ON event_exceptions (original_start_time);
