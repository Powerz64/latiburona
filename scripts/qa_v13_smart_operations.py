from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main as entry  # noqa: F401
from app.data import get_sample_reservations, get_sample_tournaments
from app.services import (
    AnalyticsService,
    ApiClient,
    AuthApiService,
    CourtCatalogService,
    DatabaseService,
    ExportService,
    PricingService,
    ReservationService,
    SessionService,
    SettingsService,
    TournamentService,
)
from kivy.clock import Clock
from kivy.core.window import Window
from kivy_ui import LaTiburonaApp

PROJECT_ROOT = Path(r"C:\latiburona")
EXPORTS_DIR = PROJECT_ROOT / "exports"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
PREFIX = EXPORTS_DIR / f"qa_v13_smart_operations_{STAMP}"
LOG_PATH = EXPORTS_DIR / f"qa_v13_smart_operations_{STAMP}.json"
DB_PATH = EXPORTS_DIR / f"qa_v13_smart_operations_{STAMP}.db"

errors: list[dict] = []
screenshots: dict[str, str] = {}


def build_services() -> dict:
    database_service = DatabaseService(str(DB_PATH))
    database_service.initialize_database()
    settings_service = SettingsService(database_service)
    settings_service.ensure_defaults()
    pricing_service = PricingService(settings_service)
    reservation_service = ReservationService(database_service, pricing_service)
    tournament_service = TournamentService(database_service)
    reservation_service.seed_sample_data_if_empty(get_sample_reservations())
    reservation_service.refresh_pricing_for_all_reservations()
    tournament_service.seed_sample_data_if_empty(get_sample_tournaments())
    tournament_service.reconcile_existing_records()
    api_client = ApiClient()
    return {
        "api_client": api_client,
        "auth_api_service": AuthApiService(api_client),
        "court_service": CourtCatalogService(),
        "database_service": database_service,
        "session_service": SessionService(),
        "sync_mode": "local",
        "settings_service": settings_service,
        "pricing_service": pricing_service,
        "reservation_service": reservation_service,
        "tournament_service": tournament_service,
        "analytics_service": AnalyticsService(reservation_service),
        "export_service": ExportService(pricing_service),
    }


class QaApp(LaTiburonaApp):
    def on_start(self) -> None:
        pass


services = build_services()
services["session_service"].clear_session()
app = QaApp(services)


def record_error(label: str, exc: BaseException) -> None:
    errors.append({"label": label, "error": str(exc), "traceback": traceback.format_exc(limit=4)})
    print(f"QA_V13_ERROR {label}: {exc}", flush=True)


def shell():
    return app.get_shell_screen()


def boot(_dt) -> None:
    try:
        user = {"display_name": "QA Admin", "email": "qa@latiburona.local", "role": "admin", "is_admin": True}
        app.current_user = dict(user)
        app.is_authenticated = True
        if app.root is not None and hasattr(app.root, "current"):
            app.root.current = "shell"
        shell().after_login(user, offline=False)
        print("QA_V13_BOOT_OK", flush=True)
    except Exception as exc:
        record_error("boot", exc)


def switch_to(name: str) -> None:
    try:
        shell().switch_screen(name)
    except Exception as exc:
        record_error(f"switch_{name}", exc)


def capture(name: str) -> None:
    try:
        filename = str(PREFIX) + f"_{name}.png"
        result = Window.screenshot(name=filename)
        screenshots[name] = result or filename
        print(f"QA_V13_SCREENSHOT {name} {screenshots[name]}", flush=True)
    except Exception as exc:
        record_error(f"capture_{name}", exc)


def assert_widget_bounds(name: str, widget) -> None:
    if widget.width <= 0 or widget.height <= 0:
        raise AssertionError(f"{name} invisible")
    if widget.right > Window.width + 2 or widget.x < -2:
        raise AssertionError(f"{name} horizontal overflow x={widget.x} right={widget.right} window={Window.width}")


def validate_reservations(_dt) -> None:
    try:
        screen = shell().ids.inner_sm.get_screen("reservations")
        assert "smart_ops_card" in screen.ids, "smart ops card missing"
        assert "activity_feed_list" in screen.ids, "activity feed missing"
        assert_widget_bounds("smart_ops_card", screen.ids.smart_ops_card)
        for row in screen.ids.reservations_list.children:
            assert_widget_bounds("reservation_row", row)
        print("QA_V13_RESERVATIONS_LAYOUT_OK", flush=True)
    except Exception as exc:
        record_error("reservations_layout", exc)


def operator_mode(_dt) -> None:
    try:
        user = {"display_name": "QA Operator", "email": "operator@latiburona.local", "role": "operator", "is_admin": False}
        app.current_user = dict(user)
        shell().after_login(user, offline=False)
        switch_to("reservations")
        print("QA_V13_OPERATOR_OK", flush=True)
    except Exception as exc:
        record_error("operator_mode", exc)


def narrow(_dt) -> None:
    try:
        Window.size = (900, 760)
        switch_to("reservations")
        print("QA_V13_NARROW_OK", flush=True)
    except Exception as exc:
        record_error("narrow", exc)


def finish(_dt) -> None:
    payload = {
        "errors": errors,
        "screenshots": screenshots,
        "generated_at": datetime.now().isoformat(),
    }
    LOG_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"QA_V13_ERRORS {len(errors)}", flush=True)
    print(f"QA_V13_LOG {LOG_PATH}", flush=True)
    if errors:
        app.stop()
        raise SystemExit(1)
    app.stop()


Clock.schedule_once(boot, 0.4)
Clock.schedule_once(lambda _dt: switch_to("dashboard"), 3.4)
Clock.schedule_once(lambda _dt: capture("analytics_admin"), 4.2)
Clock.schedule_once(lambda _dt: switch_to("reservations"), 5.0)
Clock.schedule_once(validate_reservations, 6.0)
Clock.schedule_once(lambda _dt: capture("reservations_payments"), 6.4)
Clock.schedule_once(lambda _dt: switch_to("settings"), 7.2)
Clock.schedule_once(lambda _dt: capture("settings_admin"), 8.0)
Clock.schedule_once(operator_mode, 8.8)
Clock.schedule_once(lambda _dt: capture("operator_mode"), 10.0)
Clock.schedule_once(narrow, 10.8)
Clock.schedule_once(lambda _dt: capture("narrow_width"), 12.0)
Clock.schedule_once(finish, 12.8)

app.run()
