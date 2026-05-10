import sqlite3
from pathlib import Path

from app.utils.time_slots import next_time_value


class DatabaseService:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def get_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize_database(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.get_connection() as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS reservations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_name TEXT NOT NULL,
                    service_type TEXT NOT NULL,
                    reservation_date TEXT NOT NULL,
                    reservation_time TEXT NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    people_count INTEGER NOT NULL,
                    phone TEXT NOT NULL,
                    address TEXT NOT NULL,
                    schedule TEXT NOT NULL,
                    subtotal REAL NOT NULL,
                    discount REAL NOT NULL,
                    total REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pendiente',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS tournaments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    participants TEXT NOT NULL,
                    participant_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'activo',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            self._ensure_column(connection, "reservations", "start_time", "TEXT")
            self._ensure_column(connection, "reservations", "end_time", "TEXT")
            self._ensure_column(connection, "tournaments", "participant_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "tournaments", "status", "TEXT NOT NULL DEFAULT 'activo'")
            self._backfill_reservation_ranges(connection)
            connection.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_reservations_date_time
                ON reservations(reservation_date, reservation_time);

                CREATE INDEX IF NOT EXISTS idx_reservations_service_range
                ON reservations(reservation_date, service_type, start_time, end_time);

                CREATE INDEX IF NOT EXISTS idx_reservations_status
                ON reservations(status);

                CREATE INDEX IF NOT EXISTS idx_tournaments_status
                ON tournaments(status);
                """
            )

    def _ensure_column(self, connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _backfill_reservation_ranges(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            SELECT id, reservation_time, start_time, end_time
            FROM reservations
            """
        ).fetchall()

        for row in rows:
            start_time = row["start_time"] or row["reservation_time"]
            end_time = row["end_time"] or next_time_value(start_time)
            if row["start_time"] != start_time or row["end_time"] != end_time:
                connection.execute(
                    """
                    UPDATE reservations
                    SET start_time = ?,
                        end_time = ?,
                        reservation_time = ?
                    WHERE id = ?
                    """,
                    (start_time, end_time, start_time, row["id"]),
                )
