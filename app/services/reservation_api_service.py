from __future__ import annotations

from datetime import datetime, timedelta

from app.models import Reservation
from app.services.api_client import ApiClient, ApiConnectionError, ApiResponseError
from app.services.api_exceptions import ReservationConflictValidationError
from app.utils.constants import END_TIME_OPTIONS, TIME_OPTIONS
from app.utils.time_slots import format_time_range, next_time_value, week_dates
from app.utils.validators import ValidationError, validate_reservation_input

WEEKDAY_LABELS = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
BUFFER_MINUTES = 10


class ReservationApiService:
    def __init__(self, api_client: ApiClient, pricing_service, court_service) -> None:
        self.api_client = api_client
        self.pricing_service = pricing_service
        self.court_service = court_service
        self._cache: list[Reservation] = []

    def _request(self, method: str, path: str, **kwargs):
        try:
            response = self.api_client.request(method, path, **kwargs)
        except ApiConnectionError as exc:
            raise ValidationError("No fue posible conectarse con el servidor central de LaTiburona.") from exc

        payload = self.api_client.parse_response(response)
        return response, payload

    def _reservation_from_payload(self, payload: dict) -> Reservation:
        start_time = payload["hora_inicio"]
        end_time = payload["hora_fin"]
        service_type = payload.get("cancha_nombre") or self.court_service.get_cancha_name(int(payload["cancha_id"]))
        schedule = payload.get("jornada") or self.pricing_service.get_schedule_and_base_price(start_time)[0]
        return Reservation(
            id=int(payload["id"]),
            client_name=payload["client_name"],
            service_type=service_type,
            reservation_date=payload["fecha"],
            reservation_time=start_time,
            start_time=start_time,
            end_time=end_time,
            people_count=int(payload["people_count"]),
            phone=payload["phone"],
            address=payload["address"],
            schedule=schedule,
            subtotal=float(payload.get("subtotal", 0.0) or 0.0),
            discount=float(payload.get("descuento", 0.0) or 0.0),
            total=float(payload.get("total", 0.0) or 0.0),
            status=payload.get("estado", "pendiente"),
            created_at=payload.get("created_at"),
            payment_status=payload.get("payment_status"),
            payment_url=payload.get("payment_url"),
            payment_transaction_id=payload.get("payment_transaction_id"),
            payment_expires_at=payload.get("payment_expires_at"),
        )

    def _payload_to_range(self, payload: dict) -> dict:
        return {
            "id": int(payload["id"]),
            "client_name": payload["client_name"],
            "service_type": payload.get("cancha_nombre") or self.court_service.get_cancha_name(int(payload["cancha_id"])),
            "reservation_date": payload["fecha"],
            "start_time": payload["hora_inicio"],
            "end_time": payload["hora_fin"],
            "status": payload.get("estado", "pendiente"),
            "time_range": format_time_range(payload["hora_inicio"], payload["hora_fin"]),
        }

    def _cache_items(self, items: list[Reservation]) -> list[Reservation]:
        self._cache = sorted(
            items,
            key=lambda item: (item.reservation_date, item.start_time, item.client_name.lower()),
        )
        return list(self._cache)

    def _reservations_from_response(self, payload: list[dict]) -> list[Reservation]:
        return [self._reservation_from_payload(item) for item in payload]

    def _build_request_payload(self, cleaned: dict) -> dict:
        pricing = self.pricing_service.calculate_price(
            cleaned["reservation_date"],
            cleaned["start_time"],
            cleaned["people_count"],
            cleaned["end_time"],
        )
        return {
            "cancha_id": self.court_service.get_cancha_id(cleaned["service_type"]),
            "fecha": cleaned["reservation_date"],
            "hora_inicio": cleaned["start_time"],
            "hora_fin": cleaned["end_time"],
            "estado": cleaned["status"],
            "total": pricing.total,
            "subtotal": pricing.subtotal,
            "descuento": pricing.discount,
            "jornada": pricing.schedule,
            "client_name": cleaned["client_name"],
            "phone": cleaned["phone"],
            "address": cleaned["address"],
            "people_count": cleaned["people_count"],
        }

    def _handle_mutation_response(self, response, payload):
        if response.status_code == 409:
            raise ReservationConflictValidationError(
                payload.get("error", "Este horario ya esta reservado."),
                payload.get("suggestions", []),
            )
        if response.status_code in {200, 201}:
            return payload
        raise ApiResponseError(response.status_code, payload)

    @staticmethod
    def _to_datetime(fecha: str, hora: str) -> datetime:
        return datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")

    def _buffer_conflict(self, reserva: dict, fecha: str, hora_inicio: str, hora_fin: str) -> bool:
        new_start = self._to_datetime(fecha, hora_inicio)
        new_end = self._to_datetime(fecha, hora_fin)
        existing_start = self._to_datetime(fecha, reserva["start_time"]) - timedelta(minutes=BUFFER_MINUTES)
        existing_end = self._to_datetime(fecha, reserva["end_time"]) + timedelta(minutes=BUFFER_MINUTES)
        return existing_start < new_end and existing_end > new_start

    def _slot_status(self, fecha: str, slot_start: str, slot_end: str, occupied_ranges: list[dict]) -> str:
        slot_start_dt = self._to_datetime(fecha, slot_start)
        slot_end_dt = self._to_datetime(fecha, slot_end)
        has_partial_overlap = False

        for item in occupied_ranges:
            occupied_start = self._to_datetime(fecha, item["start_time"])
            occupied_end = self._to_datetime(fecha, item["end_time"])
            if occupied_start < slot_end_dt and occupied_end > slot_start_dt:
                return "occupied"

            blocked_start = occupied_start - timedelta(minutes=BUFFER_MINUTES)
            blocked_end = occupied_end + timedelta(minutes=BUFFER_MINUTES)
            if blocked_start < slot_end_dt and blocked_end > slot_start_dt:
                has_partial_overlap = True

        return "partial" if has_partial_overlap else "available"

    def count_reservations(self) -> int:
        return len(self.get_all_reservations())

    def seed_sample_data_if_empty(self, _sample_items: list[dict]) -> None:
        return None

    def refresh_pricing_for_all_reservations(self) -> None:
        return None

    def get_all_reservations(self) -> list[Reservation]:
        try:
            response, payload = self._request("GET", "/reservas")
            if response.status_code != 200:
                raise ApiResponseError(response.status_code, payload)
            return self._cache_items(self._reservations_from_response(payload))
        except (ApiResponseError, ValidationError):
            return list(self._cache)

    def get_reservation(self, reservation_id: int) -> Reservation | None:
        try:
            response, payload = self._request("GET", f"/reservas/{reservation_id}")
        except ValidationError:
            return next((item for item in self._cache if item.id == reservation_id), None)

        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise ApiResponseError(response.status_code, payload)
        reservation = self._reservation_from_payload(payload)
        self._cache_items([item for item in self._cache if item.id != reservation.id] + [reservation])
        return reservation

    def is_slot_available(
        self,
        cancha_id: str,
        fecha: str,
        hora_inicio: str,
        hora_fin: str,
        *,
        exclude_reservation_id: int | None = None,
    ) -> bool:
        occupied_ranges = self.get_ocupadas(cancha_id, fecha, exclude_reservation_id=exclude_reservation_id)
        return not any(self._buffer_conflict(item, fecha, hora_inicio, hora_fin) for item in occupied_ranges)

    def get_ocupadas(
        self,
        cancha_id: str,
        fecha: str,
        *,
        exclude_reservation_id: int | None = None,
    ) -> list[dict]:
        cancha_numeric_id = self.court_service.get_cancha_id(cancha_id)
        try:
            response, payload = self._request("GET", f"/reservas?cancha_id={cancha_numeric_id}&fecha={fecha}")
            if response.status_code != 200:
                raise ApiResponseError(response.status_code, payload)
            items = [self._payload_to_range(item) for item in payload]
        except (ApiResponseError, ValidationError):
            items = [
                {
                    "id": item.id or 0,
                    "client_name": item.client_name,
                    "service_type": item.service_type,
                    "reservation_date": item.reservation_date,
                    "start_time": item.start_time,
                    "end_time": item.end_time,
                    "status": item.status,
                    "time_range": item.time_range,
                }
                for item in self._cache
                if item.service_type == cancha_id and item.reservation_date == fecha and item.status != "cancelada"
            ]

        if exclude_reservation_id is not None:
            items = [item for item in items if int(item["id"]) != exclude_reservation_id]
        return sorted(items, key=lambda item: (item["start_time"], item["end_time"], item["client_name"].lower()))

    def get_time_grid(self) -> list[str]:
        return list(TIME_OPTIONS)

    def get_available_end_times(
        self,
        cancha_id: str,
        fecha: str,
        hora_inicio: str,
        *,
        exclude_reservation_id: int | None = None,
    ) -> list[str]:
        if hora_inicio not in TIME_OPTIONS:
            return []

        available_end_times: list[str] = []
        for candidate in END_TIME_OPTIONS:
            if candidate <= hora_inicio:
                continue
            if self.is_slot_available(
                cancha_id,
                fecha,
                hora_inicio,
                candidate,
                exclude_reservation_id=exclude_reservation_id,
            ):
                available_end_times.append(candidate)
            else:
                break
        return available_end_times

    def get_daily_availability(
        self,
        cancha_id: str,
        fecha: str,
        *,
        exclude_reservation_id: int | None = None,
    ) -> dict:
        occupied_ranges = self.get_ocupadas(
            cancha_id,
            fecha,
            exclude_reservation_id=exclude_reservation_id,
        )
        slots = []
        available_count = 0
        partial_count = 0
        occupied_count = 0

        for slot_time in TIME_OPTIONS:
            slot_end = next_time_value(slot_time)
            status = self._slot_status(fecha, slot_time, slot_end, occupied_ranges)
            if status == "available":
                available_count += 1
            elif status == "partial":
                partial_count += 1
            else:
                occupied_count += 1

            slots.append(
                {
                    "time": slot_time,
                    "start_time": slot_time,
                    "end_time": slot_end,
                    "time_range": format_time_range(slot_time, slot_end),
                    "status": status,
                    "disabled": status != "available",
                }
            )

        return {
            "cancha_id": cancha_id,
            "date": fecha,
            "slots": slots,
            "occupied_ranges": occupied_ranges,
            "available_count": available_count,
            "partial_count": partial_count,
            "occupied_count": occupied_count,
            "has_availability": available_count > 0,
        }

    def get_week_availability(self, cancha_id: str, reference_date: str | None = None) -> list[dict]:
        days = []
        for current_date in week_dates(reference_date):
            availability = self.get_daily_availability(cancha_id, current_date.isoformat())
            days.append(
                {
                    "date": current_date.isoformat(),
                    "weekday": WEEKDAY_LABELS[current_date.weekday()],
                    "day_number": f"{current_date.day:02d}",
                    "summary": (
                        f"{availability['available_count']} disp. / "
                        f"{availability['occupied_count']} ocup."
                    ),
                    "tone": (
                        "danger"
                        if not availability["has_availability"]
                        else "warning"
                        if availability["occupied_count"] >= availability["available_count"]
                        else "success"
                    ),
                    "has_availability": availability["has_availability"],
                }
            )
        return days

    def create_reservation(self, payload: dict) -> int:
        cleaned = validate_reservation_input(payload)
        request_payload = self._build_request_payload(cleaned)
        response, response_payload = self._request("POST", "/reservas", json=request_payload)
        created_payload = self._handle_mutation_response(response, response_payload)
        reservation = self._reservation_from_payload(created_payload)
        self._cache_items([item for item in self._cache if item.id != reservation.id] + [reservation])
        return reservation.id or 0

    def update_reservation(self, reservation_id: int, payload: dict) -> None:
        cleaned = validate_reservation_input(payload)
        request_payload = self._build_request_payload(cleaned)
        response, response_payload = self._request("PUT", f"/reservas/{reservation_id}", json=request_payload)
        updated_payload = self._handle_mutation_response(response, response_payload)
        reservation = self._reservation_from_payload(updated_payload)
        self._cache_items([item for item in self._cache if item.id != reservation.id] + [reservation])

    def delete_reservation(self, reservation_id: int) -> None:
        response, payload = self._request("DELETE", f"/reservas/{reservation_id}")
        if response.status_code != 200:
            raise ApiResponseError(response.status_code, payload)
        self._cache = [item for item in self._cache if item.id != reservation_id]

    def confirm_reservation(self, reservation_id: int) -> None:
        reservation = self.get_reservation(reservation_id)
        if reservation is None:
            raise ValidationError("La reserva seleccionada ya no existe.")

        payload = {
            "client_name": reservation.client_name,
            "service_type": reservation.service_type,
            "reservation_date": reservation.reservation_date,
            "start_time": reservation.start_time,
            "end_time": reservation.end_time,
            "people_count": reservation.people_count,
            "phone": reservation.phone,
            "address": reservation.address,
            "status": "confirmada",
        }
        self.update_reservation(reservation_id, payload)

    def get_pricing_preview(
        self,
        reservation_date: str,
        reservation_time: str,
        people_count: str | int,
        end_time: str | None = None,
    ) -> dict:
        people_raw = str(people_count).strip()
        if not people_raw.isdigit():
            raise ValidationError("La cantidad de personas debe ser numerica.")
        return self.pricing_service.calculate_price(
            reservation_date,
            reservation_time,
            int(people_raw),
            end_time,
        ).to_dict()
