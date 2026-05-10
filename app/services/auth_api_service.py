from __future__ import annotations

from app.services.api_client import ApiClient


class AuthApiServiceError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 0, code: str = "auth_error") -> None:
        self.status_code = status_code
        self.code = code
        super().__init__(message)


class AuthApiNetworkError(AuthApiServiceError):
    def __init__(self, message: str = "No fue posible conectarse con el servidor central.") -> None:
        super().__init__(message, status_code=0, code="network_error")


class AuthApiService:
    def __init__(self, api_client: ApiClient) -> None:
        self.api_client = api_client

    @staticmethod
    def _log(event: str, message: str) -> None:
        print(f"{event}: {message}", flush=True)

    @staticmethod
    def _message_from_payload(payload, fallback: str) -> str:
        if isinstance(payload, dict):
            detail = payload.get("detail") or payload.get("error") or payload.get("message")
            if detail:
                return str(detail)
        return fallback

    @staticmethod
    def _auth_unavailable_message(status_code: int, fallback: str) -> str:
        if status_code == 404:
            return "Servicio de autenticacion no disponible en la URL configurada."
        return fallback

    def _request(self, method: str, path: str, **kwargs):
        self._log("AUTH REQUEST", f"{method.upper()} {path} base={self.api_client.base_url}")
        response = self.api_client.request(method, path, **kwargs)
        payload = self.api_client.parse_response(response)
        status_code = int(getattr(response, "status_code", 0) or 0)
        response_event = "REGISTER RESPONSE" if path == "/auth/register" else "AUTH RESPONSE"
        self._log(response_event, f"{method.upper()} {path} status={status_code}")
        if response.status_code == 0 or self.api_client.last_error == "network_error":
            raise AuthApiNetworkError(self._message_from_payload(payload, "No fue posible conectarse con el servidor central."))
        if self.api_client.last_error == "timeout_error":
            raise AuthApiNetworkError("Tiempo de espera agotado conectando con el servidor central.")
        return response, payload

    def register(self, data: dict) -> dict:
        response, payload = self._request("POST", "/auth/register", json=data)
        if response.status_code != 201:
            message = self._message_from_payload(payload, "No fue posible crear la cuenta.")
            message = self._auth_unavailable_message(response.status_code, message)
            if response.status_code == 409:
                message = message or "Email ya existe."
            raise AuthApiServiceError(
                message,
                status_code=response.status_code,
                code="email_exists" if response.status_code == 409 else "register_error",
            )
        if not isinstance(payload, dict):
            raise AuthApiServiceError(
                "Respuesta invalida del servidor al crear la cuenta.",
                status_code=response.status_code,
                code="invalid_register_response",
            )
        return payload

    def login(self, email: str, password: str) -> dict:
        response, payload = self._request("POST", "/auth/login", json={"email": email, "password": password})
        if response.status_code != 200:
            message = self._message_from_payload(payload, "No fue posible iniciar sesion.")
            message = self._auth_unavailable_message(response.status_code, message)
            raise AuthApiServiceError(
                message,
                status_code=response.status_code,
                code="invalid_credentials" if response.status_code == 401 else "login_error",
            )
        if not isinstance(payload, dict):
            raise AuthApiServiceError(
                "Respuesta invalida del servidor al iniciar sesion.",
                status_code=response.status_code,
                code="invalid_login_response",
            )
        if not str(payload.get("access_token") or "").strip():
            raise AuthApiServiceError(
                "Respuesta invalida del servidor: token ausente.",
                status_code=response.status_code,
                code="missing_token",
            )
        if not isinstance(payload.get("user"), dict):
            raise AuthApiServiceError(
                "Respuesta invalida del servidor: usuario ausente.",
                status_code=response.status_code,
                code="missing_user",
            )
        return payload

    def me(self, token: str) -> dict:
        response, payload = self._request(
            "GET",
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code != 200:
            message = self._message_from_payload(payload, "No fue posible validar la sesion actual.")
            message = self._auth_unavailable_message(response.status_code, message)
            raise AuthApiServiceError(
                message,
                status_code=response.status_code,
                code="invalid_session" if response.status_code in {401, 403} else "me_error",
            )
        if not isinstance(payload, dict) or not payload:
            raise AuthApiServiceError(
                "Respuesta invalida del servidor al validar la sesion.",
                status_code=response.status_code,
                code="invalid_me_response",
            )
        return payload
