from __future__ import annotations

import os
import time

import requests

PRODUCTION_API_BASE_URL = "https://latiburona-1.onrender.com"
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 0.5
NETWORK_ERROR_COOLDOWN_SECONDS = 5
LOCAL_API_MARKERS = ("127.0.0.1", "localhost", "0.0.0.0")


def _api_log(event: str, message: str) -> None:
    print(f"{event}: {message}", flush=True)


def _normalize_base_url(base_url: str | None) -> str:
    raw_value = (base_url or PRODUCTION_API_BASE_URL).strip().rstrip("/")
    if not raw_value:
        return PRODUCTION_API_BASE_URL
    if any(marker in raw_value.lower() for marker in LOCAL_API_MARKERS):
        if os.getenv("LATIBURONA_ALLOW_LOCAL_API", "").strip() == "1":
            return raw_value
        _api_log("API CONFIG", f"local API URL ignored; using {PRODUCTION_API_BASE_URL}")
        return PRODUCTION_API_BASE_URL
    return raw_value


DEFAULT_API_BASE_URL = _normalize_base_url(os.getenv("LATIBURONA_API_BASE_URL"))


class NetworkErrorResponse:
    status_code = 0

    def __init__(self, error: str = "network_error", text: str | None = None) -> None:
        self.error = error
        self.text = text or error
        self.reason = self.text

    def json(self) -> dict:
        return {"error": self.error, "detail": self.text}


class ApiConnectionError(RuntimeError):
    """Raised when the API cannot be reached."""


class ApiResponseError(RuntimeError):
    def __init__(self, status_code: int, payload) -> None:
        self.status_code = status_code
        self.payload = payload
        detail = payload.get("detail") if isinstance(payload, dict) else payload
        if isinstance(detail, dict):
            message = detail.get("message") or detail.get("error") or str(detail)
        else:
            message = str(detail or "")
        super().__init__(message or f"Respuesta inesperada del API ({status_code}).")


class ApiClient:
    def __init__(self, base_url: str | None = None, *, timeout: float = 8.0) -> None:
        self.base_url = _normalize_base_url(base_url or DEFAULT_API_BASE_URL)
        self.timeout = timeout
        self.access_token: str | None = None
        self.last_error: str | None = None
        self.last_error_at: float | None = None

    def set_access_token(self, token: str | None) -> None:
        self.access_token = str(token or "").strip() or None

    def clear_access_token(self) -> None:
        self.access_token = None

    def ping(self) -> bool:
        for path in ("/health", "/canchas"):
            url = f"{self.base_url}{path}"
            try:
                response = requests.get(url, timeout=min(self.timeout, 4.0))
            except requests.Timeout:
                self.last_error = "timeout_error"
                self.last_error_at = time.monotonic()
                _api_log("TIMEOUT ERROR", f"GET {path}")
                continue
            except requests.RequestException as exc:
                self.last_error = "network_error"
                self.last_error_at = time.monotonic()
                _api_log("API ERROR", f"GET {path}: {exc}")
                continue
            if response.status_code == 200:
                self.last_error = None
                self.last_error_at = None
                return True
            if response.status_code in {401, 403}:
                self.last_error = None
                self.last_error_at = None
                return True
            _api_log("API ERROR", f"GET {path} status={response.status_code}")

        return False

    def reset_error(self) -> None:
        self.last_error = None
        self.last_error_at = None

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        headers = dict(kwargs.pop("headers", {}) or {})
        if self.access_token and not any(key.lower() == "authorization" for key in headers):
            headers["Authorization"] = f"Bearer {self.access_token}"
        if headers:
            kwargs["headers"] = headers
        kwargs.setdefault("timeout", self.timeout)
        last_error = "network_error"
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.request(method, url, **kwargs)
                self.last_error = None
                self.last_error_at = None
                return response
            except requests.Timeout as exc:
                last_error = "timeout_error"
                _api_log("TIMEOUT ERROR", f"{method.upper()} {path} attempt={attempt + 1}: {exc}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY_SECONDS)
            except requests.RequestException as exc:
                last_error = "network_error"
                _api_log("API ERROR", f"{method.upper()} {path} attempt={attempt + 1}: {exc}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY_SECONDS)

        self.last_error = last_error
        self.last_error_at = time.monotonic()
        message = "Tiempo de espera agotado conectando con la API." if last_error == "timeout_error" else (
            "No fue posible conectarse con la API."
        )
        return NetworkErrorResponse(last_error, message)

    @staticmethod
    def parse_response(response):
        if response is None:
            return {"detail": "Respuesta vacia del servidor."}
        try:
            return response.json()
        except Exception:
            return {"detail": getattr(response, "text", "") or "Respuesta invalida del servidor."}
