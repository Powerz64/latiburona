from dataclasses import dataclass


@dataclass(slots=True)
class PricingResult:
    schedule: str
    base_price: float
    subtotal: float
    discount: float
    total: float
    duration_hours: int
    start_time: str
    end_time: str
    weekend_surcharge_percent: float
    weekend_surcharge_amount: float
    bulk_discount_percent: float
    bulk_discount_amount: float
    applied_labels: tuple[str, ...]
    smart_adjustment: float = 0.0
    smart_rules: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "schedule": self.schedule,
            "base_price": self.base_price,
            "subtotal": self.subtotal,
            "discount": self.discount,
            "total": self.total,
            "duration_hours": self.duration_hours,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "time_range": self.time_range,
            "weekend_surcharge_percent": self.weekend_surcharge_percent,
            "weekend_surcharge_amount": self.weekend_surcharge_amount,
            "bulk_discount_percent": self.bulk_discount_percent,
            "bulk_discount_amount": self.bulk_discount_amount,
            "applied_labels": list(self.applied_labels),
            "smart_adjustment": self.smart_adjustment,
            "smart_rules": list(self.smart_rules),
            "breakdown": self.breakdown,
        }

    @property
    def breakdown(self) -> list[tuple[str, float | str]]:
        return [
            ("Rango", self.time_range),
            ("Duracion", f"{self.duration_hours} hora(s)"),
            ("Tarifa base", self.base_price),
            ("Jornada", self.schedule),
            ("Recargo fin de semana", f"{self.weekend_surcharge_percent:.0f}%"),
            ("Valor recargo", self.weekend_surcharge_amount),
            ("Descuento por grupo", f"{self.bulk_discount_percent:.0f}%"),
            ("Valor descuento", self.bulk_discount_amount),
            ("Ajuste inteligente", self.smart_adjustment),
            ("Total", self.total),
        ]

    @property
    def time_range(self) -> str:
        return f"{self.start_time} - {self.end_time}"
