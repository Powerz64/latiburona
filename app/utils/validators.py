import re
from datetime import datetime

from .constants import (
    END_TIME_OPTIONS,
    SERVICE_TYPES,
    TIME_OPTIONS,
    TOURNAMENT_CATEGORIES,
    TOURNAMENT_STATUS_OPTIONS,
)
from .time_slots import hours_between, next_time_value, time_to_minutes


class ValidationError(ValueError):
    """Error de validacion de datos de entrada."""


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def validate_reservation_input(payload: dict) -> dict:
    client_name = normalize_text(payload.get("client_name", ""))
    if len(client_name) < 3:
        raise ValidationError("El nombre del cliente debe tener al menos 3 caracteres.")

    service_type = normalize_text(payload.get("service_type", ""))
    if service_type not in SERVICE_TYPES:
        raise ValidationError("Selecciona un tipo de servicio valido.")

    reservation_date = normalize_text(payload.get("reservation_date", ""))
    try:
        datetime.strptime(reservation_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValidationError("La fecha debe estar en formato AAAA-MM-DD.") from exc

    start_time = normalize_text(payload.get("start_time", payload.get("reservation_time", "")))
    if start_time not in TIME_OPTIONS:
        raise ValidationError("Selecciona una hora de inicio valida.")

    end_time = normalize_text(payload.get("end_time", ""))
    if not end_time:
        end_time = next_time_value(start_time)
    if end_time not in END_TIME_OPTIONS:
        raise ValidationError("Selecciona una hora de fin valida.")
    if time_to_minutes(end_time) <= time_to_minutes(start_time):
        raise ValidationError("La hora de fin debe ser posterior a la hora de inicio.")

    people_raw = str(payload.get("people_count", "")).strip()
    if not people_raw.isdigit():
        raise ValidationError("La cantidad de personas debe ser numerica.")

    people_count = int(people_raw)
    if people_count <= 0 or people_count > 50:
        raise ValidationError("La cantidad de personas debe estar entre 1 y 50.")

    phone = normalize_text(payload.get("phone", ""))
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 7 or len(digits) > 15:
        raise ValidationError("Ingresa un telefono valido.")

    address = normalize_text(payload.get("address", ""))
    if len(address) < 5:
        raise ValidationError("La direccion debe ser mas descriptiva.")

    status_raw = normalize_text(payload.get("status", "pendiente")) or "pendiente"
    status = status_raw.upper() if "_" in status_raw else status_raw.lower()
    if status not in {
        "pendiente",
        "confirmada",
        "cancelada",
        "PENDING_PAYMENT",
        "PARTIAL_PAYMENT",
        "PAID",
        "FAILED",
        "CANCELLED",
        "REFUNDED",
        "EXPIRED",
    }:
        raise ValidationError("El estado de la reserva no es valido.")

    return {
        "client_name": client_name,
        "service_type": service_type,
        "reservation_date": reservation_date,
        "reservation_time": start_time,
        "start_time": start_time,
        "end_time": end_time,
        "duration_hours": hours_between(start_time, end_time),
        "people_count": people_count,
        "phone": phone,
        "address": address,
        "status": status,
    }


def parse_participants(value: str) -> list[str]:
    tokens = re.split(r"[\n,;]+", value)
    return [normalize_text(token) for token in tokens if normalize_text(token)]


def count_participants(value: str) -> int:
    return len(parse_participants(value))


def validate_tournament_input(payload: dict) -> dict:
    cleaned_name = normalize_text(payload.get("name", ""))
    if len(cleaned_name) < 3:
        raise ValidationError("El torneo debe tener un nombre claro.")

    cleaned_category = normalize_text(payload.get("category", ""))
    if cleaned_category not in TOURNAMENT_CATEGORIES:
        raise ValidationError("Selecciona una categoria valida.")

    participant_names = parse_participants(payload.get("participants", ""))
    if len(participant_names) < 2:
        raise ValidationError("Debes registrar al menos 2 participantes.")

    cleaned_status = normalize_text(payload.get("status", "activo")).lower() or "activo"
    if cleaned_status not in TOURNAMENT_STATUS_OPTIONS:
        raise ValidationError("El estado del torneo debe ser activo o finalizado.")

    return {
        "name": cleaned_name,
        "category": cleaned_category,
        "participants": "\n".join(participant_names),
        "participant_count": len(participant_names),
        "status": cleaned_status,
    }


def validate_settings_input(payload: dict) -> dict:
    try:
        price_morning = float(str(payload["price_morning"]).replace(",", "."))
        price_afternoon = float(str(payload["price_afternoon"]).replace(",", "."))
        price_night = float(str(payload["price_night"]).replace(",", "."))
        weekend_surcharge = float(str(payload["weekend_surcharge"]).replace(",", "."))
        bulk_people_threshold = int(str(payload["bulk_people_threshold"]).strip())
        bulk_discount = float(str(payload["bulk_discount"]).replace(",", "."))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("Las configuraciones deben contener solo valores numericos validos.") from exc

    if min(price_morning, price_afternoon, price_night) <= 0:
        raise ValidationError("Las tarifas por horario deben ser mayores a cero.")
    if weekend_surcharge < 0 or bulk_discount < 0:
        raise ValidationError("Los porcentajes no pueden ser negativos.")
    if bulk_people_threshold < 2 or bulk_people_threshold > 50:
        raise ValidationError("El umbral de grupo debe estar entre 2 y 50 personas.")

    return {
        "price_morning": price_morning,
        "price_afternoon": price_afternoon,
        "price_night": price_night,
        "weekend_surcharge": weekend_surcharge,
        "bulk_people_threshold": bulk_people_threshold,
        "bulk_discount": bulk_discount,
        "allow_children": bool(payload.get("allow_children", False)),
        "allow_pets": bool(payload.get("allow_pets", False)),
    }
