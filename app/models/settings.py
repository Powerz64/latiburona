from dataclasses import dataclass


@dataclass(slots=True)
class AppSettings:
    price_morning: float
    price_afternoon: float
    price_night: float
    weekend_surcharge: float
    bulk_people_threshold: int
    bulk_discount: float
    peak_hour_multiplier: float
    off_peak_discount: float
    promo_window_discount: float
    allow_children: bool
    allow_pets: bool
