from __future__ import annotations

from app.utils.validators import ValidationError


class ReservationConflictValidationError(ValidationError):
    def __init__(self, message: str, suggestions: list[dict[str, str]] | None = None) -> None:
        self.suggestions = suggestions or []
        super().__init__(message)

