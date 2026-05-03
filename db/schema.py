import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'localfind.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS shops (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_name      TEXT    NOT NULL,
        shop_name       TEXT    NOT NULL,
        category        TEXT    NOT NULL,
        description     TEXT,
        address         TEXT    NOT NULL,
        area            TEXT    NOT NULL,
        city            TEXT    NOT NULL DEFAULT 'jaipur',
        pincode         TEXT    NOT NULL,
        latitude        REAL,
        longitude       REAL,
        wa_primary      TEXT    NOT NULL,
        wa_backup       TEXT,
        open_time       TEXT,
        close_time      TEXT,
        email           TEXT    UNIQUE,
        password_hash   TEXT,
        auth_token      TEXT,
        is_active       INTEGER NOT NULL DEFAULT 1,
        is_verified     INTEGER NOT NULL DEFAULT 0,
        rating          REAL    DEFAULT 0,
        total_reviews   INTEGER DEFAULT 0,
        created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT,
        phone       TEXT    UNIQUE,
        latitude    REAL,
        longitude   REAL,
        city        TEXT    DEFAULT 'jaipur',
        created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS requests (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER REFERENCES users(id),
        user_phone      TEXT    NOT NULL,
        item_name       TEXT    NOT NULL,
        category        TEXT,
        description     TEXT,
        latitude        REAL    NOT NULL,
        longitude       REAL    NOT NULL,
        radius_km       REAL    NOT NULL DEFAULT 5,
        city            TEXT    NOT NULL DEFAULT 'jaipur',
        status          TEXT    NOT NULL DEFAULT 'open',
        notified_shops  TEXT    DEFAULT '[]',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        expires_at      TEXT    NOT NULL DEFAULT (datetime('now', '+2 hours'))
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS responses (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id      INTEGER NOT NULL REFERENCES requests(id),
        shop_id         INTEGER NOT NULL REFERENCES shops(id),
        replied_from    TEXT,
        wa_number       TEXT,
        status          TEXT    NOT NULL DEFAULT 'pending',
        price           REAL,
        note            TEXT,
        replied_at      TEXT,
        locked_at       TEXT,
        created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        UNIQUE(request_id, shop_id)
    )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_shops_city ON shops(city, is_active)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status, city)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_responses_req ON responses(request_id, status)")

    conn.commit()
    conn.close()
    print("✅ Database ready!")

if __name__ == '__main__':
    init_db()