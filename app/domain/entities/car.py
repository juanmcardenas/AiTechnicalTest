from dataclasses import dataclass
from datetime import datetime


@dataclass
class Car:
    id: str
    brand: str
    model: str
    year: int
    color: str
    price: float
    km: int
    fuel_type: str
    transmission: str
    condition: str
    vin: str | None
    description: str | None
    image_url: str | None
    available: bool
    created_at: datetime
