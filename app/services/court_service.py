from __future__ import annotations

from app.services.api_client import ApiClient, ApiConnectionError, ApiResponseError
from app.utils.constants import LOCATION_INFO, SERVICE_TYPES
from app.utils.validators import ValidationError


class CourtCatalogService:
    def list_canchas(self) -> list[dict]:
        return [
            {
                "id": index + 1,
                "nombre": name,
                "direccion": LOCATION_INFO["direccion"],
                "ubicacion": LOCATION_INFO["puntos_referencia"],
            }
            for index, name in enumerate(SERVICE_TYPES)
        ]

    def get_service_names(self) -> list[str]:
        return [item["nombre"] for item in self.list_canchas()]

    def get_cancha_id(self, nombre: str) -> int:
        for item in self.list_canchas():
            if item["nombre"] == nombre:
                return item["id"]
        raise ValidationError("Selecciona una cancha valida.")

    def get_cancha_name(self, cancha_id: int) -> str:
        for item in self.list_canchas():
            if item["id"] == cancha_id:
                return item["nombre"]
        return str(cancha_id)


class CourtApiService(CourtCatalogService):
    def __init__(self, api_client: ApiClient) -> None:
        self.api_client = api_client
        self._cache: list[dict] | None = None

    def list_canchas(self) -> list[dict]:
        try:
            response = self.api_client.request("GET", "/canchas")
        except ApiConnectionError:
            if self._cache is not None:
                return self._cache
            return super().list_canchas()

        payload = self.api_client.parse_response(response)
        if response.status_code != 200:
            if self._cache is not None:
                return self._cache
            raise ApiResponseError(response.status_code, payload)
        self._cache = payload
        return payload

    def _canchas(self) -> list[dict]:
        if self._cache is None:
            return self.list_canchas()
        return self._cache

    def get_service_names(self) -> list[str]:
        return [item["nombre"] for item in self._canchas()]

    def get_cancha_id(self, nombre: str) -> int:
        for item in self._canchas():
            if item["nombre"] == nombre:
                return int(item["id"])
        raise ValidationError("Selecciona una cancha valida.")

    def get_cancha_name(self, cancha_id: int) -> str:
        for item in self._canchas():
            if int(item["id"]) == cancha_id:
                return item["nombre"]
        return str(cancha_id)
