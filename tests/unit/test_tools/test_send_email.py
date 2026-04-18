import pytest
from datetime import datetime
from unittest.mock import AsyncMock
from app.domain.entities.car import Car
from app.application.services.tools.send_email import make_send_email_tool


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
def mock_inventory_repo(sample_car):
    repo = AsyncMock()
    repo.get_car_by_id.return_value = sample_car
    return repo


@pytest.fixture
def mock_email_service():
    svc = AsyncMock()
    svc.send_car_specs.return_value = True
    return svc


@pytest.fixture
def mock_email_log_repo():
    return AsyncMock()


async def test_send_email_sends_specs(mock_inventory_repo, mock_email_service, mock_email_log_repo):
    tool = make_send_email_tool(mock_inventory_repo, mock_email_service, mock_email_log_repo)
    result = await tool.ainvoke({
        "car_id": "car-1",
        "recipient_email": "buyer@example.com",
        "lead_id": "lead-1",
    })
    assert "sent" in result.lower() or "success" in result.lower()
    mock_email_service.send_car_specs.assert_called_once()


async def test_send_email_car_not_found(mock_inventory_repo, mock_email_service, mock_email_log_repo):
    mock_inventory_repo.get_car_by_id.return_value = None
    tool = make_send_email_tool(mock_inventory_repo, mock_email_service, mock_email_log_repo)
    result = await tool.ainvoke({
        "car_id": "nonexistent",
        "recipient_email": "buyer@example.com",
        "lead_id": "lead-1",
    })
    assert "not found" in result.lower()
    mock_email_service.send_car_specs.assert_not_called()
