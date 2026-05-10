from datetime import datetime

from app.models import PricingResult
from app.utils.time_slots import hour_slots_between, next_time_value


class PricingService:
    def __init__(self, settings_service) -> None:
        self.settings_service = settings_service

    def get_schedule_and_base_price(self, time_value: str, settings=None) -> tuple[str, float]:
        settings = settings or self.settings_service.load_settings()
        hour = int(time_value.split(":")[0])
        if 6 <= hour < 12:
            return "Manana", settings.price_morning
        if 12 <= hour < 18:
            return "Tarde", settings.price_afternoon
        return "Noche", settings.price_night

    def calculate_price(
        self,
        reservation_date: str,
        reservation_time: str,
        people_count: int,
        end_time: str | None = None,
    ) -> PricingResult:
        settings = self.settings_service.load_settings()
        end_time = end_time or next_time_value(reservation_time)
        slots = hour_slots_between(reservation_time, end_time)
        if not slots:
            raise ValueError("El rango horario debe incluir al menos una hora.")

        hourly_segments: list[tuple[str, float]] = [
            self.get_schedule_and_base_price(slot_time, settings)
            for slot_time in slots
        ]
        schedules = [item[0] for item in hourly_segments]
        base_price = round(sum(item[1] for item in hourly_segments), 2)
        schedule = schedules[0] if len(set(schedules)) == 1 else "Mixta"

        weekday = datetime.strptime(reservation_date, "%Y-%m-%d").weekday()
        is_weekend = weekday >= 5

        weekend_surcharge_percent = settings.weekend_surcharge if is_weekend else 0.0
        weekend_surcharge_amount = round(base_price * (weekend_surcharge_percent / 100), 2)
        subtotal = round(base_price + weekend_surcharge_amount, 2)

        bulk_discount_percent = settings.bulk_discount if people_count >= settings.bulk_people_threshold else 0.0
        bulk_discount_amount = round(subtotal * (bulk_discount_percent / 100), 2)
        total = round(subtotal - bulk_discount_amount, 2)

        applied_labels: list[str] = []
        if weekend_surcharge_percent:
            applied_labels.append(f"Recargo fin de semana: {weekend_surcharge_percent:.0f}%")
        if bulk_discount_percent:
            applied_labels.append(f"Descuento aplicado: {bulk_discount_percent:.0f}%")

        return PricingResult(
            schedule=schedule,
            base_price=round(base_price, 2),
            subtotal=subtotal,
            discount=bulk_discount_amount,
            total=total,
            duration_hours=len(slots),
            start_time=reservation_time,
            end_time=end_time,
            weekend_surcharge_percent=weekend_surcharge_percent,
            weekend_surcharge_amount=weekend_surcharge_amount,
            bulk_discount_percent=bulk_discount_percent,
            bulk_discount_amount=bulk_discount_amount,
            applied_labels=tuple(applied_labels),
        )
