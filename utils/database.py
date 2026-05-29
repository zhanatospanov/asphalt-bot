"""
База данных — PostgreSQL (Railway) или SQLite (локально).
Автоматически определяет по наличию DATABASE_URL.
"""
import os
import sqlite3
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL", "")
DB_PATH      = os.environ.get("DB_PATH", "asphalt_bot.db")
USE_PG       = bool(DATABASE_URL)


def get_conn():
    if USE_PG:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True) if os.path.dirname(DB_PATH) else None
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def _q(sql):
    """Адаптирует SQL: заменяет ? на %s для PostgreSQL."""
    if USE_PG:
        return sql.replace("?", "%s")
    return sql


def _rows(cursor):
    """Возвращает список dict независимо от драйвера."""
    if USE_PG:
        cols = [d[0] for d in cursor.description] if cursor.description else []
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    return [dict(r) for r in cursor.fetchall()]


def _row(cursor):
    rows = _rows(cursor)
    return rows[0] if rows else None


def _auto(sql):
    """AUTOINCREMENT для SQLite, SERIAL для PG — в CREATE TABLE."""
    if USE_PG:
        return sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")\
                  .replace("DEFAULT (datetime('now'))", "DEFAULT NOW()")
    return sql


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute(_auto("""
        CREATE TABLE IF NOT EXISTS company (
            id INTEGER PRIMARY KEY,
            name TEXT, bin TEXT, address TEXT, phone TEXT,
            bank TEXT, bik TEXT, iban TEXT, director TEXT, updated_at TEXT
        )
    """))

    c.execute(_auto("""
        CREATE TABLE IF NOT EXISTS buyers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, bin TEXT, address TEXT, phone TEXT,
            created_at TEXT
        )
    """))

    c.execute(_auto("""
        CREATE TABLE IF NOT EXISTS objects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, created_at TEXT
        )
    """))

    c.execute(_auto("""
        CREATE TABLE IF NOT EXISTS asphalt_grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, unit TEXT DEFAULT 'т', active INTEGER DEFAULT 1
        )
    """))

    c.execute(_auto("""
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_number INTEGER NOT NULL,
            trip_date TEXT NOT NULL, trip_time TEXT NOT NULL,
            vehicle_number TEXT NOT NULL, driver_name TEXT,
            buyer_id INTEGER, buyer_name TEXT, asphalt_grade TEXT,
            tare_kg REAL NOT NULL, gross_kg REAL NOT NULL, net_kg REAL NOT NULL,
            object_name TEXT, temperature INTEGER DEFAULT 160,
            created_by INTEGER, pdf_file_id TEXT
        )
    """))

    c.execute(_auto("""
        CREATE TABLE IF NOT EXISTS current_session (
            id INTEGER PRIMARY KEY,
            buyer_id INTEGER, buyer_name TEXT, buyer_bin TEXT, buyer_address TEXT,
            object_id INTEGER, object_name TEXT, asphalt_grade TEXT,
            temperature INTEGER DEFAULT 160
        )
    """))

    if USE_PG:
        c.execute("INSERT INTO current_session (id, temperature) VALUES (1, 160) ON CONFLICT DO NOTHING")
    else:
        c.execute("INSERT OR IGNORE INTO current_session (id, temperature) VALUES (1, 160)")

    c.execute(_auto("""
        CREATE TABLE IF NOT EXISTS doc_counter (
            id INTEGER PRIMARY KEY,
            current_number INTEGER DEFAULT 1, year INTEGER
        )
    """))

    current_year = datetime.now().year
    if USE_PG:
        c.execute("INSERT INTO doc_counter (id, current_number, year) VALUES (1, 1, %s) ON CONFLICT DO NOTHING",
                  (current_year,))
    else:
        c.execute("INSERT OR IGNORE INTO doc_counter (id, current_number, year) VALUES (1, 1, ?)",
                  (current_year,))

    # Стандартные марки
    STANDARD_GRADES = [
        "Смесь асфальтобетонная дорожная горячая крупнозернистая плотная тип А, марка I",
        "Смесь асфальтобетонная дорожная горячая крупнозернистая плотная тип А, марка II",
        "Смесь асфальтобетонная дорожная горячая крупнозернистая плотная тип Б, марка I",
        "Смесь асфальтобетонная дорожная горячая крупнозернистая плотная тип Б, марка II",
        "Смесь асфальтобетонная дорожная горячая крупнозернистая плотная тип Б, марка III",
        "Смесь асфальтобетонная дорожная горячая крупнозернистая высокопористая щебеночная, марка I",
        "Смесь асфальтобетонная дорожная горячая крупнозернистая пористая, марка I",
        "Смесь асфальтобетонная дорожная горячая крупнозернистая пористая, марка II",
        "Смесь асфальтобетонная дорожная горячая мелкозернистая плотная тип А, марка I",
        "Смесь асфальтобетонная дорожная горячая мелкозернистая плотная тип А, марка II",
        "Смесь асфальтобетонная дорожная горячая мелкозернистая плотная тип Б, марка I",
        "Смесь асфальтобетонная дорожная горячая мелкозернистая плотная тип Б, марка II",
        "Смесь асфальтобетонная дорожная горячая мелкозернистая плотная тип Б, марка III",
        "Смесь асфальтобетонная дорожная горячая мелкозернистая плотная тип В, марка II",
        "Смесь асфальтобетонная дорожная горячая мелкозернистая плотная тип В, марка III",
    ]
    c.execute("SELECT name FROM asphalt_grades")
    existing = {r[0] for r in c.fetchall()}
    for g in STANDARD_GRADES:
        if g not in existing:
            c.execute(_q("INSERT INTO asphalt_grades (name) VALUES (?)"), (g,))

    conn.commit()
    conn.close()


# ── Компания ──────────────────────────────────────────────────────────────────

def get_company():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM company WHERE id=1")
    row = _row(c)
    conn.close()
    return row or {}


def save_company(data: dict):
    conn = get_conn()
    c = conn.cursor()
    data["updated_at"] = datetime.now().isoformat()
    data["id"] = 1
    if USE_PG:
        cols = ", ".join(data.keys())
        vals = ", ".join("%s" for _ in data)
        updates = ", ".join(f"{k}=EXCLUDED.{k}" for k in data if k != "id")
        c.execute(f"INSERT INTO company ({cols}) VALUES ({vals}) ON CONFLICT (id) DO UPDATE SET {updates}",
                  list(data.values()))
    else:
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        updates = ", ".join(f"{k}=excluded.{k}" for k in data if k != "id")
        c.execute(f"INSERT INTO company ({cols}) VALUES ({placeholders}) ON CONFLICT(id) DO UPDATE SET {updates}",
                  list(data.values()))
    conn.commit()
    conn.close()


# ── Покупатели ────────────────────────────────────────────────────────────────

def get_buyers():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM buyers ORDER BY name")
    rows = _rows(c)
    conn.close()
    return rows


def get_buyer(buyer_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT * FROM buyers WHERE id=?"), (buyer_id,))
    row = _row(c)
    conn.close()
    return row


def add_buyer(name, bin_=None, address=None, phone=None):
    conn = get_conn()
    c = conn.cursor()
    if USE_PG:
        c.execute("INSERT INTO buyers (name, bin, address, phone) VALUES (%s,%s,%s,%s) RETURNING id",
                  (name, bin_, address, phone))
        buyer_id = c.fetchone()[0]
    else:
        c.execute("INSERT INTO buyers (name, bin, address, phone) VALUES (?,?,?,?)",
                  (name, bin_, address, phone))
        buyer_id = c.lastrowid
    conn.commit()
    conn.close()
    return buyer_id


# ── Объекты ───────────────────────────────────────────────────────────────────

def get_objects():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM objects ORDER BY name")
    rows = _rows(c)
    conn.close()
    return rows


def get_object(obj_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT * FROM objects WHERE id=?"), (obj_id,))
    row = _row(c)
    conn.close()
    return row


def add_object(name: str) -> int:
    conn = get_conn()
    c = conn.cursor()
    if USE_PG:
        c.execute("INSERT INTO objects (name) VALUES (%s) RETURNING id", (name,))
        oid = c.fetchone()[0]
    else:
        c.execute("INSERT INTO objects (name) VALUES (?)", (name,))
        oid = c.lastrowid
    conn.commit()
    conn.close()
    return oid


# ── Марки ─────────────────────────────────────────────────────────────────────

def get_grades():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM asphalt_grades WHERE active=1 ORDER BY name")
    rows = _rows(c)
    conn.close()
    return rows


def add_grade(name, unit="т"):
    conn = get_conn()
    c = conn.cursor()
    if USE_PG:
        c.execute("INSERT INTO asphalt_grades (name, unit) VALUES (%s,%s) RETURNING id", (name, unit))
        gid = c.fetchone()[0]
    else:
        c.execute("INSERT INTO asphalt_grades (name, unit) VALUES (?,?)", (name, unit))
        gid = c.lastrowid
    conn.commit()
    conn.close()
    return gid


# ── Счётчик ───────────────────────────────────────────────────────────────────

def get_next_doc_number() -> int:
    conn = get_conn()
    c = conn.cursor()
    current_year = datetime.now().year
    c.execute("SELECT * FROM doc_counter WHERE id=1")
    row = _row(c)
    if row["year"] != current_year:
        c.execute(_q("UPDATE doc_counter SET current_number=2, year=? WHERE id=1"), (current_year,))
        num = 1
    else:
        num = row["current_number"]
        c.execute(_q("UPDATE doc_counter SET current_number=? WHERE id=1"), (num + 1,))
    conn.commit()
    conn.close()
    return num


def set_doc_number(new_number: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("UPDATE doc_counter SET current_number=? WHERE id=1"), (new_number,))
    conn.commit()
    conn.close()


# ── Рейсы ─────────────────────────────────────────────────────────────────────

def save_trip(data: dict) -> int:
    conn = get_conn()
    c = conn.cursor()
    cols = ", ".join(data.keys())
    if USE_PG:
        vals = ", ".join("%s" for _ in data)
        c.execute(f"INSERT INTO trips ({cols}) VALUES ({vals}) RETURNING id", list(data.values()))
        trip_id = c.fetchone()[0]
    else:
        vals = ", ".join("?" for _ in data)
        c.execute(f"INSERT INTO trips ({cols}) VALUES ({vals})", list(data.values()))
        trip_id = c.lastrowid
    conn.commit()
    conn.close()
    return trip_id


def update_trip_pdf(trip_id: int, file_id: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("UPDATE trips SET pdf_file_id=? WHERE id=?"), (file_id, trip_id))
    conn.commit()
    conn.close()


def get_trips(date_from=None, date_to=None):
    conn = get_conn()
    c = conn.cursor()
    query = "SELECT * FROM trips WHERE 1=1"
    params = []
    if date_from:
        query += _q(" AND trip_date >= ?"); params.append(date_from)
    if date_to:
        query += _q(" AND trip_date <= ?"); params.append(date_to)
    query += " ORDER BY trip_date, trip_time"
    c.execute(query, params)
    rows = _rows(c)
    conn.close()
    return rows


def get_trips_today():
    today = datetime.now().strftime("%Y-%m-%d")
    return get_trips(date_from=today, date_to=today)


# ── Текущая сессия ────────────────────────────────────────────────────────────

def get_current_session() -> dict:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM current_session WHERE id=1")
    row = _row(c)
    conn.close()
    return row or {}


def save_current_session(data: dict):
    conn = get_conn()
    c = conn.cursor()
    sets = ", ".join(_q("?").replace("?", f"{k}=%s" if USE_PG else f"{k}=?") for k in data)
    if USE_PG:
        sets = ", ".join(f"{k}=%s" for k in data)
    else:
        sets = ", ".join(f"{k}=?" for k in data)
    c.execute(f"UPDATE current_session SET {sets} WHERE id=1", list(data.values()))
    conn.commit()
    conn.close()
