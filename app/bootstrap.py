import os

from app.data import get_sample_reservations, get_sample_tournaments
from app.services.cache_service import has_any_cache
from app.services import (
    ApiClient,
    AnalyticsApiService,
    AnalyticsService,
    AuthApiService,
    SessionService,
    CourtApiService,
    CourtCatalogService,
    DatabaseService,
    ExportService,
    PricingService,
    ReservationApiService,
    ReservationService,
    SettingsService,
    TournamentApiService,
    TournamentService,
)
from app.utils.paths import BASE_DIR, DATABASE_PATH, ensure_database_file, ensure_exports_dir


def build_services(base_dir: str | None = None) -> dict:
    project_base_dir = base_dir or BASE_DIR
    database_path = (
        ensure_database_file() if project_base_dir == BASE_DIR else os.path.join(project_base_dir, "database.db")
    )
    database_service = DatabaseService(database_path)
    database_service.initialize_database()
    ensure_exports_dir()

    settings_service = SettingsService(database_service)
    settings_service.ensure_defaults()
    pricing_service = PricingService(settings_service)

    local_reservation_service = ReservationService(database_service, pricing_service)
    local_tournament_service = TournamentService(database_service)
    reservation_service = local_reservation_service
    tournament_service = local_tournament_service
    court_service = CourtCatalogService()
    api_client = ApiClient()
    session_service = SessionService()
    stored_session = session_service.load_session()
    if stored_session and stored_session.get("access_token"):
        api_client.set_access_token(stored_session["access_token"])

    auth_api_service = AuthApiService(api_client)
    sync_mode = "local"
    api_available = api_client.ping()

    if api_available or has_any_cache():
        court_service = CourtApiService(api_client)
        reservation_service = ReservationApiService(api_client, pricing_service, court_service)
        tournament_service = TournamentApiService(api_client)
        sync_mode = "remote"

    fallback_analytics_service = AnalyticsService(reservation_service)
    analytics_service = (
        AnalyticsApiService(api_client, fallback_service=fallback_analytics_service)
        if api_available
        else fallback_analytics_service
    )
    export_service = ExportService(pricing_service)

    if sync_mode == "local":
        reservation_service.seed_sample_data_if_empty(get_sample_reservations())
        reservation_service.refresh_pricing_for_all_reservations()
        tournament_service.seed_sample_data_if_empty(get_sample_tournaments())
        tournament_service.reconcile_existing_records()

    return {
        "api_client": api_client,
        "auth_api_service": auth_api_service,
        "court_service": court_service,
        "database_service": database_service,
        "session_service": session_service,
        "sync_mode": sync_mode,
        "settings_service": settings_service,
        "pricing_service": pricing_service,
        "reservation_service": reservation_service,
        "tournament_service": tournament_service,
        "analytics_service": analytics_service,
        "export_service": export_service,
    }
