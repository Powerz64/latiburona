from .time_slots import generate_time_options

APP_NAME = "LaTiburona"

SERVICE_TYPES = [
    "Cancha sintetica",
    "Cancha multiple",
    "Zona recreativa",
    "Piscina",
]

TOURNAMENT_CATEGORIES = [
    "Juvenil",
    "Libre",
    "Empresarial",
    "Femenino",
    "Mixto",
]

TOURNAMENT_STATUS_OPTIONS = ["activo", "finalizado"]

TIME_BOUNDARY_OPTIONS = generate_time_options()
TIME_OPTIONS = TIME_BOUNDARY_OPTIONS[:-1]
END_TIME_OPTIONS = TIME_BOUNDARY_OPTIONS[1:]
SCHEDULE_LABELS = ["Manana", "Tarde", "Noche"]

DEFAULT_SETTINGS = {
    "price_morning": 70000.0,
    "price_afternoon": 90000.0,
    "price_night": 120000.0,
    "weekend_surcharge": 10.0,
    "bulk_people_threshold": 5,
    "bulk_discount": 15.0,
    "allow_children": True,
    "allow_pets": False,
}

LOCATION_INFO = {
    "direccion": "Calle 84 #52-18, Barranquilla, Atlantico",
    "como_llegar": (
        "Desde el norte de Barranquilla toma la Via 40 o la Carrera 53 y sigue "
        "hacia el sector de Alto Prado. El complejo deportivo esta a pocos minutos "
        "del corredor universitario."
    ),
    "puntos_referencia": (
        "Cerca de Viva Barranquilla, a menos de 10 minutos del Romelio Martinez y "
        "con acceso rapido desde la Circunvalar."
    ),
}
