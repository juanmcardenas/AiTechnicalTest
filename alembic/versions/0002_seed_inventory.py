"""seed inventory

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SEED_VEHICLES = [
    ("Toyota", "Corolla", 2022, "White", 22500, 28000, "gasoline", "automatic", "used"),
    ("Toyota", "RAV4", 2023, "Silver", 34900, 0, "hybrid", "automatic", "new"),
    ("Honda", "Civic", 2021, "Black", 20000, 45000, "gasoline", "manual", "used"),
    ("Honda", "CR-V", 2022, "Blue", 31500, 18500, "gasoline", "automatic", "certified"),
    ("Ford", "Mustang", 2020, "Red", 38000, 62000, "gasoline", "manual", "used"),
    ("Ford", "Explorer", 2023, "Gray", 45000, 0, "gasoline", "automatic", "new"),
    ("Chevrolet", "Spark", 2022, "Yellow", 16000, 33000, "gasoline", "automatic", "used"),
    ("BMW", "320i", 2021, "White", 52000, 24000, "gasoline", "automatic", "certified"),
    ("Tesla", "Model 3", 2023, "Black", 48500, 0, "electric", "automatic", "new"),
    ("Nissan", "Sentra", 2022, "Silver", 19900, 41000, "gasoline", "automatic", "used"),
]


def upgrade() -> None:
    inventory = sa.table(
        "inventory",
        sa.column("brand"), sa.column("model"), sa.column("year"),
        sa.column("color"), sa.column("price"), sa.column("km"),
        sa.column("fuel_type"), sa.column("transmission"), sa.column("condition"),
        sa.column("available"),
    )
    op.bulk_insert(inventory, [
        {
            "brand": brand, "model": model, "year": year,
            "color": color, "price": price, "km": km,
            "fuel_type": fuel_type, "transmission": transmission,
            "condition": condition, "available": True,
        }
        for brand, model, year, color, price, km, fuel_type, transmission, condition in SEED_VEHICLES
    ])


def downgrade() -> None:
    op.execute("DELETE FROM inventory")
