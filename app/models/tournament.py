from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class Tournament:
    id: Optional[int]
    name: str
    category: str
    participants: str
    participant_count: int
    status: str = "activo"
    created_at: Optional[str] = None
