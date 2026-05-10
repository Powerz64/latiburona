from __future__ import annotations

from app.models import Tournament
from app.services.api_client import ApiClient, ApiConnectionError, ApiResponseError
from app.utils.validators import ValidationError, count_participants, validate_tournament_input


class TournamentApiService:
    def __init__(self, api_client: ApiClient) -> None:
        self.api_client = api_client
        self._cache: list[Tournament] = []

    def _request(self, method: str, path: str, **kwargs):
        try:
            response = self.api_client.request(method, path, **kwargs)
        except ApiConnectionError as exc:
            raise ValidationError("No fue posible conectarse con el servidor central de LaTiburona.") from exc

        payload = self.api_client.parse_response(response)
        return response, payload

    def _to_model(self, payload: dict) -> Tournament:
        participants = payload["participantes"]
        return Tournament(
            id=int(payload["id"]),
            name=payload["nombre"],
            category=payload["categoria"],
            participants=participants,
            participant_count=count_participants(participants),
            status=payload.get("estado", "activo"),
            created_at=payload.get("created_at"),
        )

    def _cache_items(self, items: list[Tournament]) -> list[Tournament]:
        self._cache = sorted(
            items,
            key=lambda item: ((item.created_at or ""), item.name.lower()),
            reverse=True,
        )
        return list(self._cache)

    def count_tournaments(self) -> int:
        return len(self.get_all_tournaments())

    def seed_sample_data_if_empty(self, _sample_items: list[dict]) -> None:
        return None

    def reconcile_existing_records(self) -> None:
        return None

    def get_all_tournaments(self) -> list[Tournament]:
        try:
            response, payload = self._request("GET", "/torneos")
            if response.status_code != 200:
                raise ApiResponseError(response.status_code, payload)
            return self._cache_items([self._to_model(item) for item in payload])
        except (ApiResponseError, ValidationError):
            return list(self._cache)

    def get_tournament(self, tournament_id: int) -> Tournament | None:
        try:
            response, payload = self._request("GET", f"/torneos/{tournament_id}")
        except ValidationError:
            return next((item for item in self._cache if item.id == tournament_id), None)

        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise ApiResponseError(response.status_code, payload)
        tournament = self._to_model(payload)
        self._cache_items([item for item in self._cache if item.id != tournament.id] + [tournament])
        return tournament

    def create_tournament(self, payload: dict) -> int:
        cleaned = validate_tournament_input(payload)
        response, response_payload = self._request(
            "POST",
            "/torneos",
            json={
                "nombre": cleaned["name"],
                "categoria": cleaned["category"],
                "participantes": cleaned["participants"],
                "estado": cleaned["status"],
            },
        )
        if response.status_code != 201:
            raise ApiResponseError(response.status_code, response_payload)
        tournament = self._to_model(response_payload)
        self._cache_items([item for item in self._cache if item.id != tournament.id] + [tournament])
        return tournament.id or 0

    def update_tournament(self, tournament_id: int, payload: dict) -> None:
        cleaned = validate_tournament_input(payload)
        response, response_payload = self._request(
            "PUT",
            f"/torneos/{tournament_id}",
            json={
                "nombre": cleaned["name"],
                "categoria": cleaned["category"],
                "participantes": cleaned["participants"],
                "estado": cleaned["status"],
            },
        )
        if response.status_code == 404:
            raise ValidationError("El torneo seleccionado ya no existe.")
        if response.status_code != 200:
            raise ApiResponseError(response.status_code, response_payload)
        tournament = self._to_model(response_payload)
        self._cache_items([item for item in self._cache if item.id != tournament.id] + [tournament])

    def delete_tournament(self, tournament_id: int) -> None:
        response, payload = self._request("DELETE", f"/torneos/{tournament_id}")
        if response.status_code == 404:
            raise ValidationError("El torneo seleccionado ya no existe.")
        if response.status_code != 200:
            raise ApiResponseError(response.status_code, payload)
        self._cache = [item for item in self._cache if item.id != tournament_id]

    def get_status_summary(self) -> dict[str, int]:
        summary = {"activo": 0, "finalizado": 0}
        for tournament in self.get_all_tournaments():
            summary[tournament.status] = summary.get(tournament.status, 0) + 1
        return summary

    def get_participant_count(self, participants: str) -> int:
        return count_participants(participants)
