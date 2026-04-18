import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.application.services.tools.update_lead_identity import make_update_lead_identity_tool
from app.domain.entities.lead import Lead, LeadStatus


@pytest.fixture
def existing_lead():
    return Lead(
        id="11111111-1111-1111-1111-111111111111",
        telegram_chat_id="12345", name=None, phone=None, email=None,
        status=LeadStatus.NEW, preferred_language="en",
        last_contacted_at=None,
        created_at=datetime(2026, 4, 1), updated_at=datetime(2026, 4, 1),
    )


@pytest.fixture
def mock_lead_repo(existing_lead):
    repo = AsyncMock()
    repo.get_by_id.return_value = existing_lead
    repo.update.side_effect = lambda lead: lead
    return repo


async def test_saves_name_email_phone(mock_lead_repo):
    tool = make_update_lead_identity_tool(mock_lead_repo)
    result = await tool.ainvoke(
        {"name": "Alice", "email": "a@x.com", "phone": "+1555"},
        config={"configurable": {"lead_id": "11111111-1111-1111-1111-111111111111"}},
    )
    data = json.loads(result)
    assert data["success"] is True
    assert data["name"] == "Alice"
    assert data["email"] == "a@x.com"
    assert data["phone"] == "+1555"
    mock_lead_repo.update.assert_called_once()


async def test_requires_at_least_one_field(mock_lead_repo):
    tool = make_update_lead_identity_tool(mock_lead_repo)
    result = await tool.ainvoke(
        {},
        config={"configurable": {"lead_id": "11111111-1111-1111-1111-111111111111"}},
    )
    data = json.loads(result)
    assert "error" in data
    mock_lead_repo.update.assert_not_called()


async def test_requires_lead_id_in_config(mock_lead_repo):
    tool = make_update_lead_identity_tool(mock_lead_repo)
    result = await tool.ainvoke({"name": "Alice"}, config={"configurable": {}})
    data = json.loads(result)
    assert "error" in data
    mock_lead_repo.update.assert_not_called()
