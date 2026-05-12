from __future__ import annotations

from app.services.api_client import ApiClient, ApiResponseError


class PaymentApiService:
    def __init__(self, api_client: ApiClient) -> None:
        self.api_client = api_client

    def _request(self, method: str, path: str, **kwargs) -> dict:
        response = self.api_client.request(method, path, **kwargs)
        payload = self.api_client.parse_response(response)
        if response.status_code not in {200, 201}:
            raise ApiResponseError(response.status_code, payload)
        return payload if isinstance(payload, dict) else {}

    def create_payment(self, reservation_id: int) -> dict:
        return self._request("POST", "/payments/create", json={"reservation_id": reservation_id})

    def get_payment_status(self, reservation_id: int) -> dict:
        return self._request("GET", f"/payments/status/{reservation_id}")
