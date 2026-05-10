from __future__ import annotations

from app.models import Reservation
from app.utils.constants import END_TIME_OPTIONS, TIME_OPTIONS
from app.utils.time_slots import (
    format_time_range,
    next_time_value,
    slot_overlap_status,
    week_dates,
)
from app.utils.validators import ValidationError, validate_reservation_input


WEEKDAY_LABELS = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]


class ReservationService:
    def __init__(self, database_service, pricing_service) -> None:
        self.database_service = database_service
        self.pricing_service = pricing_service

    def _row_to_model(self, row) -> Reservation:
        start_time = row["start_time"] or row["reservation_time"]
        end_time = row["end_time"] or next_time_value(start_time)
        return Reservation(
            id=row["id"],
            client_name=row["client_name"],
            service_type=row["service_type"],
            reservation_date=row["reservation_date"],
            reservation_time=start_time,
            start_time=start_time,
            end_time=end_time,
            people_count=row["people_count"],
            phone=row["phone"],
            address=row["address"],
            schedule=row["schedule"],
            subtotal=row["subtotal"],
            discount=row["discount"],
            total=row["total"],
            status=row["status"],
            created_at=row["created_at"],
        )

    def _pricing_for(self, cleaned: dict):
        return self.pricing_service.calculate_price(
            cleaned["reservation_date"],
            cleaned["start_time"],
            cleaned["people_count"],
            cleaned["end_time"],
        )

    def _ensure_slot_available(
        self,
        cancha_id: str,
        fecha: str,
        hora_inicio: str,
        hora_fin: str,
        *,
        exclude_reservation_id: int | None = None,
    ) -> None:
        if not self.is_slot_available(
            cancha_id,
            fecha,
            hora_inicio,
            hora_fin,
            exclude_reservation_id=exclude_reservation_id,
        ):
            raise ValidationError("Este horario ya esta reservado.")

    def count_reservations(self) -> int:
        with self.database_service.get_connection() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM reservations").fetchone()
        return int(row["total"])

    def seed_sample_data_if_empty(self, sample_items: list[dict]) -> None:
        if self.count_reservations() > 0:
            return
        for item in sample_items:
            self.create_reservation(item)

    def refresh_pricing_for_all_reservations(self) -> None:
        reservations = self.get_all_reservations()
        with self.database_service.get_connection() as connection:
            for reservation in reservations:
                pricing = self.pricing_service.calculate_price(
                    reservation.reservation_date,
                    reservation.start_time,
                    reservation.people_count,
                    reservation.end_time,
                )
                connection.execute(
                    """
                    UPDATE reservations
                    SET reservation_time = ?,
                        start_time = ?,
                        end_time = ?,
                        schedule = ?,
                        subtotal = ?,
                        discount = ?,
                        total = ?
                    WHERE id = ?
                    """,
                    (
                        reservation.start_time,
                        reservation.start_time,
                        reservation.end_time,
                        pricing.schedule,
                        pricing.subtotal,
                        pricing.discount,
                        pricing.total,
                        reservation.id,
                    ),
                )

    def get_all_reservations(self) -> list[Reservation]:
        with self.database_service.get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM reservations
                ORDER BY reservation_date ASC, start_time ASC, client_name ASC
                """
            ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def get_reservation(self, reservation_id: int) -> Reservation | None:
        with self.database_service.get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM reservations WHERE id = ?",
                (reservation_id,),
            ).fetchone()
        return self._row_to_model(row) if row else None

    def is_slot_available(
        self,
        cancha_id: str,
        fecha: str,
        hora_inicio: str,
        hora_fin: str,
        *,
        exclude_reservation_id: int | None = None,
    ) -> bool:
        query = """
            SELECT COUNT(*) AS total
            FROM reservations
            WHERE service_type = ?
              AND reservation_date = ?
              AND status != 'cancelada'
              AND start_time < ?
              AND end_time > ?
        """
        params: list[object] = [cancha_id, fecha, hora_fin, hora_inicio]
        if exclude_reservation_id is not None:
            query += " AND id != ?"
            params.append(exclude_reservation_id)

        with self.database_service.get_connection() as connection:
            row = connection.execute(query, tuple(params)).fetchone()
        return int(row["total"]) == 0

    def get_ocupadas(
        self,
        cancha_id: str,
        fecha: str,
        *,
        exclude_reservation_id: int | None = None,
    ) -> list[dict]:
        query = """
            SELECT id, client_name, service_type, reservation_date, reservation_time, start_time, end_time, status
            FROM reservations
            WHERE service_type = ?
              AND reservation_date = ?
              AND status != 'cancelada'
        """
        params: list[object] = [cancha_id, fecha]
        if exclude_reservation_id is not None:
            query += " AND id != ?"
            params.append(exclude_reservation_id)
        query += " ORDER BY start_time ASC, end_time ASC, client_name ASC"

        with self.database_service.get_connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()

        occupied = []
        for row in rows:
            start_time = row["start_time"] or row["reservation_time"]
            end_time = row["end_time"] or next_time_value(start_time)
            occupied.append(
                {
                    "id": row["id"],
                    "client_name": row["client_name"],
                    "service_type": row["service_type"],
                    "reservation_date": row["reservation_date"],
                    "start_time": start_time,
                    "end_time": end_time,
                    "status": row["status"],
                    "time_range": format_time_range(start_time, end_time),
                }
            )
        return occupied

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
            status = slot_overlap_status(slot_time, slot_end, occupied_ranges)
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
        self._ensure_slot_available(
            cleaned["service_type"],
            cleaned["reservation_date"],
            cleaned["start_time"],
            cleaned["end_time"],
        )
        pricing = self._pricing_for(cleaned).to_dict()

        reservation = Reservation(
            id=None,
            client_name=cleaned["client_name"],
            service_type=cleaned["service_type"],
            reservation_date=cleaned["reservation_date"],
            reservation_time=cleaned["start_time"],
            start_time=cleaned["start_time"],
            end_time=cleaned["end_time"],
            people_count=cleaned["people_count"],
            phone=cleaned["phone"],
            address=cleaned["address"],
            schedule=pricing["schedule"],
            subtotal=pricing["subtotal"],
            discount=pricing["discount"],
            total=pricing["total"],
            status=cleaned["status"],
        )

        with self.database_service.get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO reservations (
                    client_name,
                    service_type,
                    reservation_date,
                    reservation_time,
                    start_time,
                    end_time,
                    people_count,
                    phone,
                    address,
                    schedule,
                    subtotal,
                    discount,
                    total,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reservation.client_name,
                    reservation.service_type,
                    reservation.reservation_date,
                    reservation.reservation_time,
                    reservation.start_time,
                    reservation.end_time,
                    reservation.people_count,
                    reservation.phone,
                    reservation.address,
                    reservation.schedule,
                    reservation.subtotal,
                    reservation.discount,
                    reservation.total,
                    reservation.status,
                ),
            )
        return int(cursor.lastrowid)

    def update_reservation(self, reservation_id: int, payload: dict) -> None:
        if not self.get_reservation(reservation_id):
            raise ValidationError("La reserva seleccionada ya no existe.")

        cleaned = validate_reservation_input(payload)
        self._ensure_slot_available(
            cleaned["service_type"],
            cleaned["reservation_date"],
            cleaned["start_time"],
            cleaned["end_time"],
            exclude_reservation_id=reservation_id,
        )
        pricing = self._pricing_for(cleaned).to_dict()

        with self.database_service.get_connection() as connection:
            connection.execute(
                """
                UPDATE reservations
                SET client_name = ?,
                    service_type = ?,
                    reservation_date = ?,
                    reservation_time = ?,
                    start_time = ?,
                    end_time = ?,
                    people_count = ?,
                    phone = ?,
                    address = ?,
                    schedule = ?,
                    subtotal = ?,
                    discount = ?,
                    total = ?,
                    status = ?
                WHERE id = ?
                """,
                (
                    cleaned["client_name"],
                    cleaned["service_type"],
                    cleaned["reservation_date"],
                    cleaned["start_time"],
                    cleaned["start_time"],
                    cleaned["end_time"],
                    cleaned["people_count"],
                    cleaned["phone"],
                    cleaned["address"],
                    pricing["schedule"],
                    pricing["subtotal"],
                    pricing["discount"],
                    pricing["total"],
                    cleaned["status"],
                    reservation_id,
                ),
            )

    def delete_reservation(self, reservation_id: int) -> None:
        with self.database_service.get_connection() as connection:
            connection.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))

    def confirm_reservation(self, reservation_id: int) -> None:
        with self.database_service.get_connection() as connection:
            connection.execute(
                "UPDATE reservations SET status = 'confirmada' WHERE id = ?",
                (reservation_id,),
            )

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
