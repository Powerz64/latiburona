from datetime import date, timedelta


def get_sample_reservations() -> list[dict]:
    today = date.today()
    return [
        {
            "client_name": "Carlos Mendoza",
            "service_type": "Cancha sintetica",
            "reservation_date": (today + timedelta(days=1)).isoformat(),
            "reservation_time": "19:00",
            "start_time": "19:00",
            "end_time": "21:00",
            "people_count": 10,
            "phone": "3001234567",
            "address": "Barrio El Prado",
            "status": "confirmada",
        },
        {
            "client_name": "Laura Jimenez",
            "service_type": "Piscina",
            "reservation_date": (today + timedelta(days=2)).isoformat(),
            "reservation_time": "15:00",
            "start_time": "15:00",
            "end_time": "17:00",
            "people_count": 4,
            "phone": "3012345678",
            "address": "Villa Santos",
            "status": "pendiente",
        },
        {
            "client_name": "Andres Torres",
            "service_type": "Cancha multiple",
            "reservation_date": (today + timedelta(days=3)).isoformat(),
            "reservation_time": "19:00",
            "start_time": "19:00",
            "end_time": "20:00",
            "people_count": 8,
            "phone": "3023456789",
            "address": "Ciudad Jardin",
            "status": "confirmada",
        },
        {
            "client_name": "Daniela Acosta",
            "service_type": "Zona recreativa",
            "reservation_date": (today + timedelta(days=4)).isoformat(),
            "reservation_time": "09:00",
            "start_time": "09:00",
            "end_time": "11:00",
            "people_count": 3,
            "phone": "3034567890",
            "address": "Alto Prado",
            "status": "pendiente",
        },
        {
            "client_name": "Fundacion Deportiva Sur",
            "service_type": "Cancha sintetica",
            "reservation_date": (today + timedelta(days=5)).isoformat(),
            "reservation_time": "20:00",
            "start_time": "20:00",
            "end_time": "22:00",
            "people_count": 14,
            "phone": "3045678901",
            "address": "Soledad",
            "status": "confirmada",
        },
        {
            "client_name": "Escuela Caribe Pro",
            "service_type": "Cancha multiple",
            "reservation_date": (today + timedelta(days=6)).isoformat(),
            "reservation_time": "21:00",
            "start_time": "21:00",
            "end_time": "22:00",
            "people_count": 7,
            "phone": "3056789012",
            "address": "Riomar",
            "status": "pendiente",
        },
    ]


def get_sample_tournaments() -> list[dict]:
    return [
        {
            "name": "Copa Tiburon Barranquilla",
            "category": "Libre",
            "participants": "Tiburones FC\nCosta Norte\nLa 84 Team\nMalecon Club",
            "status": "activo",
        },
        {
            "name": "Reto Juvenil Caribe",
            "category": "Juvenil",
            "participants": "Academia Norte\nBarrio Abajo Kids\nMetropolitano Jr",
            "status": "finalizado",
        },
    ]
