import sqlite3
import os
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "asphalt_bot.db")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True) if os.path.dirname(DB_PATH) else None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Реквизиты завода (одна строка)
    c.execute("""
        CREATE TABLE IF NOT EXISTS company (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            name TEXT,
            bin TEXT,
            address TEXT,
            phone TEXT,
            bank TEXT,
            bik TEXT,
            iban TEXT,
            director TEXT,
            updated_at TEXT
        )
    """)

    # Покупатели
    c.execute("""
        CREATE TABLE IF NOT EXISTS buyers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            bin TEXT,
            address TEXT,
            phone TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Справочник объектов строительства
    c.execute("""
        CREATE TABLE IF NOT EXISTS objects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT
        )
    """)

    # Справочник марок асфальта
    c.execute("""
        CREATE TABLE IF NOT EXISTS asphalt_grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            unit TEXT DEFAULT 'т',
            active INTEGER DEFAULT 1
        )
    """)

    # Журнал рейсов
    c.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_number INTEGER NOT NULL,
            trip_date TEXT NOT NULL,
            trip_time TEXT NOT NULL,
            vehicle_number TEXT NOT NULL,
            driver_name TEXT,
            buyer_id INTEGER,
            buyer_name TEXT,
            asphalt_grade TEXT,
            tare_kg REAL NOT NULL,
            gross_kg REAL NOT NULL,
            net_kg REAL NOT NULL,
            object_name TEXT,
            temperature INTEGER DEFAULT 160,
            created_by INTEGER,
            pdf_file_id TEXT,
            FOREIGN KEY (buyer_id) REFERENCES buyers(id)
        )
    """)

    # Счётчик номеров накладных
    c.execute("""
        CREATE TABLE IF NOT EXISTS doc_counter (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            current_number INTEGER DEFAULT 1,
            year INTEGER
        )
    """)

    # Вставим счётчик если нет
    current_year = datetime.now().year
    c.execute("""
        INSERT OR IGNORE INTO doc_counter (id, current_number, year)
        VALUES (1, 1, ?)
    """, (current_year,))

    # Добавим несколько марок по умолчанию
    c.execute("SELECT COUNT(*) FROM asphalt_grades")
    if c.fetchone()[0] == 0:
        grades = [
            ("АС 9.5/12.5 Тип А (верхний слой)",),
            ("АС 12.5/20 Тип Б (нижний слой)",),
            ("АС 19/25 Тип В (основание)",),
            ("ЩМА-15",),
            ("ЩМА-20",),
        ]
        c.executemany("INSERT INTO asphalt_grades (name) VALUES (?)", grades)

    conn.commit()
    conn.close()


# ── Компания ─────────────────────────────────────────────────────────────────

def get_company():
    conn = get_conn()
    row = conn.execute("SELECT * FROM company WHERE id=1").fetchone()
    conn.close()
    return dict(row) if row else {}


def save_company(data: dict):
    conn = get_conn()
    data["updated_at"] = datetime.now().isoformat()
    data["id"] = 1
    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" for _ in data)
    updates = ", ".join(f"{k}=excluded.{k}" for k in data if k != "id")
    conn.execute(
        f"INSERT INTO company ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT(id) DO UPDATE SET {updates}",
        list(data.values())
    )
    conn.commit()
    conn.close()


# ── Покупатели ────────────────────────────────────────────────────────────────

def get_buyers():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM buyers ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_buyer(buyer_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM buyers WHERE id=?", (buyer_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_buyer(name, bin_=None, address=None, phone=None):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO buyers (name, bin, address, phone) VALUES (?,?,?,?)",
        (name, bin_, address, phone)
    )
    buyer_id = cur.lastrowid
    conn.commit()
    conn.close()
    return buyer_id


def update_buyer(buyer_id, **kwargs):
    conn = get_conn()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    conn.execute(f"UPDATE buyers SET {sets} WHERE id=?", [*kwargs.values(), buyer_id])
    conn.commit()
    conn.close()


# ── Марки асфальта ────────────────────────────────────────────────────────────

def get_grades():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM asphalt_grades WHERE active=1 ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_grade(name, unit="т"):
    conn = get_conn()
    cur = conn.execute("INSERT INTO asphalt_grades (name, unit) VALUES (?,?)", (name, unit))
    gid = cur.lastrowid
    conn.commit()
    conn.close()
    return gid


# ── Счётчик накладных ─────────────────────────────────────────────────────────

def get_next_doc_number() -> int:
    conn = get_conn()
    current_year = datetime.now().year
    row = conn.execute("SELECT * FROM doc_counter WHERE id=1").fetchone()

    if row["year"] != current_year:
        # Новый год — сбрасываем счётчик
        conn.execute(
            "UPDATE doc_counter SET current_number=2, year=? WHERE id=1",
            (current_year,)
        )
        num = 1
    else:
        num = row["current_number"]
        conn.execute(
            "UPDATE doc_counter SET current_number=? WHERE id=1",
            (num + 1,)
        )

    conn.commit()
    conn.close()
    return num


def set_doc_number(new_number: int):
    conn = get_conn()
    conn.execute(
        "UPDATE doc_counter SET current_number=? WHERE id=1",
        (new_number + 1,)
    )
    conn.commit()
    conn.close()


# ── Рейсы / журнал ────────────────────────────────────────────────────────────

def save_trip(data: dict) -> int:
    conn = get_conn()
    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" for _ in data)
    cur = conn.execute(
        f"INSERT INTO trips ({cols}) VALUES ({placeholders})",
        list(data.values())
    )
    trip_id = cur.lastrowid
    conn.commit()
    conn.close()
    return trip_id


def update_trip_pdf(trip_id: int, file_id: str):
    conn = get_conn()
    conn.execute("UPDATE trips SET pdf_file_id=? WHERE id=?", (file_id, trip_id))
    conn.commit()
    conn.close()


def get_trips(date_from: str = None, date_to: str = None):
    conn = get_conn()
    query = "SELECT * FROM trips WHERE 1=1"
    params = []
    if date_from:
        query += " AND trip_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND trip_date <= ?"
        params.append(date_to)
    query += " ORDER BY trip_date, trip_time"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trips_today():
    today = datetime.now().strftime("%Y-%m-%d")
    return get_trips(date_from=today, date_to=today)


# ── Объекты строительства ─────────────────────────────────────────────────────

def get_objects():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM objects ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_object(obj_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM objects WHERE id=?", (obj_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_object(name: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO objects (name, created_at) VALUES (?, datetime('now'))",
        (name,)
    )
    oid = cur.lastrowid
    conn.commit()
    conn.close()
    return oid

