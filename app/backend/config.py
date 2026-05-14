from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass

from app.models import AppSettings
from app.utils.constants import DEFAULT_SETTINGS
from app.utils.paths import BASE_DIR


def get_required_secret_key() -> str:
    secret_key = os.getenv("LATIBURONA_SECRET_KEY", "").strip()
    if not secret_key:
        raise RuntimeError("LATIBURONA_SECRET_KEY es obligatoria para iniciar el backend.")
    return secret_key


def _get_env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return float(default)
    try:
        return float(raw_value.replace(",", "."))
    except ValueError:
        return float(default)


def _get_env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return int(default)
    try:
        return int(float(raw_value))
    except ValueError:
        return int(default)


def _get_env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name, "").strip().lower()
    if not raw_value:
        return default
    return raw_value in {"1", "true", "yes", "si", "on"}


def get_cors_origins() -> list[str]:
    raw_value = (
        os.getenv("CORS_ORIGINS", "").strip()
        or os.getenv("LATIBURONA_CORS_ORIGINS", "").strip()
        or "*"
    )
    if not raw_value or raw_value == "*":
        return ["*"]
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def get_sqlite_fallback_path() -> Path:
    raw_value = os.getenv("LATIBURONA_SQLITE_PATH", "").strip()
    if raw_value:
        return Path(raw_value).expanduser()
    return Path(BASE_DIR) / "server.db"


def normalize_database_url(database_url: str | None) -> str:
    raw_value = (database_url or "").strip()
    if not raw_value:
        sqlite_path = get_sqlite_fallback_path()
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{sqlite_path}"

    if raw_value.startswith("postgres://"):
        raw_value = raw_value.replace("postgres://", "postgresql+psycopg://", 1)
    elif raw_value.startswith("postgresql://") and "+psycopg" not in raw_value:
        raw_value = raw_value.replace("postgresql://", "postgresql+psycopg://", 1)

    return raw_value


def database_backend_name(database_url: str) -> str:
    return "sqlite" if database_url.startswith("sqlite") else "postgresql"


@dataclass(frozen=True)
class PaymentSettings:
    public_key: str
    access_token: str
    webhook_secret: str
    provider: str
    mode: str
    timeout_minutes: int
    public_base_url: str
    success_url: str
    failure_url: str
    pending_url: str


def load_payment_settings() -> PaymentSettings:
    return PaymentSettings(
        public_key=os.getenv("MERCADOPAGO_PUBLIC_KEY", "").strip(),
        access_token=os.getenv("MERCADOPAGO_ACCESS_TOKEN", "").strip(),
        webhook_secret=os.getenv("MERCADOPAGO_WEBHOOK_SECRET", "").strip(),
        provider=os.getenv("PAYMENT_PROVIDER", "manual").strip().lower() or "manual",
        mode=os.getenv("PAYMENT_MODE", "test").strip().lower() or "test",
        timeout_minutes=max(5, _get_env_int("RESERVATION_PAYMENT_TIMEOUT_MINUTES", 20)),
        public_base_url=(
            os.getenv("LATIBURONA_PUBLIC_API_URL", "").strip()
            or os.getenv("PUBLIC_API_BASE_URL", "").strip()
            or os.getenv("RENDER_EXTERNAL_URL", "").strip()
        ),
        success_url=os.getenv("PAYMENT_SUCCESS_URL", "").strip(),
        failure_url=os.getenv("PAYMENT_FAILURE_URL", "").strip(),
        pending_url=os.getenv("PAYMENT_PENDING_URL", "").strip(),
    )


def load_backend_pricing_settings() -> AppSettings:
    return AppSettings(
        price_morning=_get_env_float("LATIBURONA_PRICE_MORNING", DEFAULT_SETTINGS["price_morning"]),
        price_afternoon=_get_env_float("LATIBURONA_PRICE_AFTERNOON", DEFAULT_SETTINGS["price_afternoon"]),
        price_night=_get_env_float("LATIBURONA_PRICE_NIGHT", DEFAULT_SETTINGS["price_night"]),
        weekend_surcharge=_get_env_float("LATIBURONA_WEEKEND_SURCHARGE", DEFAULT_SETTINGS["weekend_surcharge"]),
        bulk_people_threshold=_get_env_int(
            "LATIBURONA_BULK_PEOPLE_THRESHOLD",
            DEFAULT_SETTINGS["bulk_people_threshold"],
        ),
        bulk_discount=_get_env_float("LATIBURONA_BULK_DISCOUNT", DEFAULT_SETTINGS["bulk_discount"]),
        peak_hour_multiplier=_get_env_float(
            "LATIBURONA_PEAK_HOUR_MULTIPLIER",
            DEFAULT_SETTINGS["peak_hour_multiplier"],
        ),
        off_peak_discount=_get_env_float("LATIBURONA_OFF_PEAK_DISCOUNT", DEFAULT_SETTINGS["off_peak_discount"]),
        promo_window_discount=_get_env_float(
            "LATIBURONA_PROMO_WINDOW_DISCOUNT",
            DEFAULT_SETTINGS["promo_window_discount"],
        ),
        allow_children=_get_env_bool("LATIBURONA_ALLOW_CHILDREN", DEFAULT_SETTINGS["allow_children"]),
        allow_pets=_get_env_bool("LATIBURONA_ALLOW_PETS", DEFAULT_SETTINGS["allow_pets"]),
    )
