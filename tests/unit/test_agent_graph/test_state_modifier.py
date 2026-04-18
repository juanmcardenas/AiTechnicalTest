import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.application.services.agent_graph import _build_state_modifier, SYSTEM_PROMPT


def test_state_modifier_prepends_system_prompt():
    mock_llm = MagicMock()
    modifier = _build_state_modifier(mock_llm)

    with patch("app.application.services.agent_graph.trim_messages") as mock_trim:
        mock_trim.return_value = [HumanMessage(content="Hello")]
        messages = modifier({"messages": [HumanMessage(content="Hello")]})

    assert isinstance(messages[0], SystemMessage)
    assert messages[0].content == SYSTEM_PROMPT


def test_state_modifier_includes_trimmed_messages():
    mock_llm = MagicMock()
    modifier = _build_state_modifier(mock_llm)
    human_msg = HumanMessage(content="Hello")

    with patch("app.application.services.agent_graph.trim_messages") as mock_trim:
        mock_trim.return_value = [human_msg]
        messages = modifier({"messages": [human_msg]})

    assert human_msg in messages
