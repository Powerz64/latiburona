from app.models import AppSettings
from app.utils.constants import DEFAULT_SETTINGS
from app.utils.validators import validate_settings_input


class SettingsService:
    def __init__(self, database_service) -> None:
        self.database_service = database_service

    def ensure_defaults(self) -> None:
        with self.database_service.get_connection() as connection:
            current_values = {
                row["key"]: row["value"]
                for row in connection.execute("SELECT key, value FROM settings").fetchall()
            }

            if "weekend_surcharge" not in current_values:
                connection.execute(
                    "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
                    ("weekend_surcharge", str(DEFAULT_SETTINGS["weekend_surcharge"])),
                )

            if (
                current_values.get("bulk_people_threshold") in {"8", "8.0"}
                and current_values.get("bulk_discount") in {"5", "5.0"}
            ):
                connection.execute(
                    "REPLACE INTO settings(key, value) VALUES(?, ?)",
                    ("bulk_people_threshold", str(DEFAULT_SETTINGS["bulk_people_threshold"])),
                )
                connection.execute(
                    "REPLACE INTO settings(key, value) VALUES(?, ?)",
                    ("bulk_discount", str(DEFAULT_SETTINGS["bulk_discount"])),
                )

            for key, value in DEFAULT_SETTINGS.items():
                connection.execute(
                    "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
                    (key, str(value)),
                )

    def load_settings(self) -> AppSettings:
        values = DEFAULT_SETTINGS.copy()
        with self.database_service.get_connection() as connection:
            rows = connection.execute("SELECT key, value FROM settings").fetchall()

        for row in rows:
            if row["key"] not in values:
                continue
            raw_value = row["value"]
            if row["key"] in {"allow_children", "allow_pets"}:
                values[row["key"]] = raw_value.lower() == "true"
            elif row["key"] == "bulk_people_threshold":
                values[row["key"]] = int(float(raw_value))
            else:
                values[row["key"]] = float(raw_value)

        return AppSettings(**values)

    def save_settings(self, payload: dict) -> AppSettings:
        cleaned = validate_settings_input(payload)
        with self.database_service.get_connection() as connection:
            for key, value in cleaned.items():
                connection.execute(
                    "REPLACE INTO settings(key, value) VALUES(?, ?)",
                    (key, str(value)),
                )
        return self.load_settings()
