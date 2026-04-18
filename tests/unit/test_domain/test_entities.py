from datetime import datetime
import pytest
from app.domain.entities.car import Car
from app.domain.entities.lead import Lead, LeadStatus
from app.domain.entities.meeting import Meeting
from app.domain.entities.reminder import Reminder


def test_car_creation():
    car = Car(
        id="car-1", brand="Toyota", model="Corolla", year=2022,
        color="White", price=22500.0, km=28000, fuel_type="gasoline",
        transmission="automatic", condition="used", vin=None,
        description=None, image_url=None, available=True,
        created_at=datetime(2024, 1, 1),
    )
    assert car.brand == "Toyota"
    assert car.available is True


def test_lead_status_enum():
    assert LeadStatus.NEW == "new"
    assert LeadStatus.CONVERTED == "converted"


def test_lead_creation():
    lead = Lead(
        id="lead-1", telegram_chat_id="12345", name="Alice",
        phone=None, email=None, status=LeadStatus.NEW,
        preferred_language="en", last_contacted_at=None,
        created_at=datetime(2024, 1, 1), updated_at=datetime(2024, 1, 1),
    )
    assert lead.telegram_chat_id == "12345"
    assert lead.status == LeadStatus.NEW


def test_meeting_creation():
    meeting = Meeting(
        id="meet-1", lead_id="lead-1", car_id="car-1",
        google_event_id=None, google_meet_link=None,
        scheduled_at=datetime(2024, 6, 1, 10, 0),
        duration_minutes=60, location="Dealership showroom",
        status="scheduled", notes=None,
        created_at=datetime(2024, 1, 1), updated_at=datetime(2024, 1, 1),
    )
    assert meeting.duration_minutes == 60
    assert meeting.status == "scheduled"


def test_reminder_creation():
    reminder = Reminder(
        id="rem-1", lead_id="lead-1",
        remind_at=datetime(2024, 7, 1, 9, 0),
        message="Follow up with Alice", sent=False,
        sent_at=None, created_at=datetime(2024, 1, 1),
    )
    assert reminder.sent is False
