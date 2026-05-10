from __future__ import annotations

import json
import os

from app.utils.paths import EXPORTS_DIR

SESSION_PATH = os.path.join(EXPORTS_DIR, "session.json")


class SessionService:
    def __init__(self, session_path: str | None = None) -> None:
        self.session_path = session_path or SESSION_PATH
        self._log_keys: set[str] = set()

    def _log_once(self, key: str, message: str) -> None:
        if key in self._log_keys:
            return
        self._log_keys.add(key)
        print(message, flush=True)

    def save_session(self, token: str, user: dict) -> None:
        token = str(token or "").strip()
        if not token or not isinstance(user, dict):
            self._log_once("invalid_save", "SESSION RESTORE: skipped invalid session save")
            return
        os.makedirs(os.path.dirname(self.session_path), exist_ok=True)
        payload = {
            "access_token": token,
            "user": user,
        }
        with open(self.session_path, "w", encoding="utf-8") as session_file:
            json.dump(payload, session_file, ensure_ascii=True, indent=2)
        print("SESSION RESTORE: session persisted", flush=True)

    def load_session(self) -> dict | None:
        if not os.path.exists(self.session_path):
            return None

        try:
            with open(self.session_path, "r", encoding="utf-8") as session_file:
                payload = json.load(session_file)
        except (OSError, json.JSONDecodeError) as exc:
            self._log_once("invalid_file", f"SESSION RESTORE: invalid session file: {exc}")
            return None

        if not isinstance(payload, dict):
            self._log_once("invalid_payload", "SESSION RESTORE: invalid session payload")
            return None
        if not payload.get("access_token") or not isinstance(payload.get("user"), dict):
            self._log_once("missing_token_or_user", "SESSION RESTORE: missing token or user")
            return None
        self._log_once("loaded", "SESSION RESTORE: saved session loaded")
        return payload

    def clear_session(self) -> None:
        try:
            if os.path.exists(self.session_path):
                os.remove(self.session_path)
                print("SESSION RESTORE: session cleared", flush=True)
        except OSError as exc:
            print(f"SESSION RESTORE: clear failed: {exc}", flush=True)
            return

    def is_logged_in(self) -> bool:
        return self.load_session() is not None
