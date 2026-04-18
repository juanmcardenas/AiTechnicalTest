import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.application.services.tools.send_email import make_send_email_tool
from app.domain.entities.car import Car
from app.domain.entities.lead import Lead, LeadStatus


@pytest.fixture
def sample_car():
    return Car(
        id="car-1", brand="Tesla", model="Model 3", year=2023,
        color="Black", price=48500.0, km=0, fuel_type="electric",
        transmission="automatic", condition="new", vin=None,
        description=None, image_url=None, available=True,
        created_at=datetime(2024, 1, 1),
    )


@pytest.fixture
def identified_lead():
    return Lead(
        id="11111111-1111-1111-1111-111111111111",
        telegram_chat_id="12345", name="Alice", phone=None,
        email="alice@example.com", status=LeadStatus.NEW,
        preferred_language="en", last_contacted_at=None,
        created_at=datetime(2026, 4, 1), updated_at=datetime(2026, 4, 1),
    )


@pytest.fixture
def unidentified_lead():
    return Lead(
        id="11111111-1111-1111-1111-111111111111",
        telegram_chat_id="12345", name=None, phone=None, email=None,
        status=LeadStatus.NEW, preferred_language="en",
        last_contacted_at=None,
        created_at=datetime(2026, 4, 1), updated_at=datetime(2026, 4, 1),
    )


def _inventory(car):
    repo = AsyncMock()
    repo.get_car_by_id.return_value = car
    return repo


def _lead_repo(lead):
    repo = AsyncMock()
    repo.get_by_id.return_value = lead
    return repo


@pytest.fixture
def mock_email_service():
    svc = AsyncMock()
    svc.send_car_specs.return_value = True
    return svc


@pytest.fixture
def mock_email_log_repo():
    return AsyncMock()


async def test_send_email_succeeds_for_identified_lead(
    sample_car, identified_lead, mock_email_service, mock_email_log_repo
):
    tool = make_send_email_tool(
        _inventory(sample_car), mock_email_service, mock_email_log_repo, _lead_repo(identified_lead),
    )
    result = await tool.ainvoke(
        {"car_id": "car-1", "recipient_email": "buyer@example.com"},
        config={"configurable": {"lead_id": "11111111-1111-1111-1111-111111111111"}},
    )
    assert "success" in result.lower()
    mock_email_service.send_car_specs.assert_called_once()


async def test_send_email_blocked_for_unidentified_lead(
    sample_car, unidentified_lead, mock_email_service, mock_email_log_repo
):
    tool = make_send_email_tool(
        _inventory(sample_car), mock_email_service, mock_email_log_repo, _lead_repo(unidentified_lead),
    )
    result = await tool.ainvoke(
        {"car_id": "car-1", "recipient_email": "buyer@example.com"},
        config={"configurable": {"lead_id": "11111111-1111-1111-1111-111111111111"}},
    )
    data = json.loads(result)
    assert "error" in data
    assert "not identified" in data["error"].lower()
    mock_email_service.send_car_specs.assert_not_called()


async def test_send_email_car_not_found(
    identified_lead, mock_email_service, mock_email_log_repo
):
    no_car = AsyncMock()
    no_car.get_car_by_id.return_value = None
    tool = make_send_email_tool(
        no_car, mock_email_service, mock_email_log_repo, _lead_repo(identified_lead),
    )
    result = await tool.ainvoke(
        {"car_id": "nonexistent", "recipient_email": "buyer@example.com"},
        config={"configurable": {"lead_id": "11111111-1111-1111-1111-111111111111"}},
    )
    assert "not found" in result.lower()
    mock_email_service.send_car_specs.assert_not_called()
