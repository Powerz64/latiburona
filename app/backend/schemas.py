from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CanchaOut(BaseModel):
    id: int
    nombre: str
    direccion: str
    ubicacion: str

    model_config = ConfigDict(from_attributes=True)


class ReservaBase(BaseModel):
    cancha_id: int
    fecha: str
    hora_inicio: str
    hora_fin: str
    estado: str = "pendiente"
    total: float = 0.0
    subtotal: float = 0.0
    descuento: float = 0.0
    jornada: str = "Manana"
    client_name: str = Field(min_length=3)
    phone: str = Field(min_length=7)
    address: str = Field(min_length=5)
    people_count: int = Field(ge=1, le=50)


class ReservaCreate(ReservaBase):
    pass


class ReservaUpdate(ReservaBase):
    pass


class ReservaOut(ReservaBase):
    id: int
    user_id: int | None = None
    cancha_nombre: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlternativeRange(BaseModel):
    inicio: str
    fin: str


class ConflictResponse(BaseModel):
    error: str
    suggestions: list[AlternativeRange]


class TorneoBase(BaseModel):
    nombre: str = Field(min_length=3)
    categoria: str = Field(min_length=3)
    participantes: str = Field(min_length=3)
    estado: str = "activo"


class TorneoCreate(TorneoBase):
    pass


class TorneoUpdate(TorneoBase):
    pass


class TorneoOut(TorneoBase):
    id: int
    user_id: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserPublic(BaseModel):
    id: int
    full_name: str
    display_name: str
    email: EmailStr
    role: str
    is_active: bool
    is_admin: bool

    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=3, max_length=140)
    display_name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    confirm_email: EmailStr
    phone: str = Field(default="", max_length=30)
    password: str = Field(min_length=6, max_length=128)
    confirm_password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=4096)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, max_length=4096)


class RegisterResponse(BaseModel):
    message: str
    user: UserPublic


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPublic
