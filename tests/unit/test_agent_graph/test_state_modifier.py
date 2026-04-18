from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.agent_graph import SYSTEM_PROMPT, _build_state_modifier


def test_state_modifier_prepends_static_system_prompt_when_no_session_ctx():
    mock_llm = MagicMock()
    modifier = _build_state_modifier(mock_llm, session_ctx="")
    with patch("app.application.services.agent_graph.trim_messages") as mock_trim:
        mock_trim.return_value = [HumanMessage(content="Hello")]
        messages = modifier({"messages": [HumanMessage(content="Hello")]})
    assert isinstance(messages[0], SystemMessage)
    assert messages[0].content == SYSTEM_PROMPT


def test_state_modifier_prepends_session_ctx_before_system_prompt():
    mock_llm = MagicMock()
    ctx = "SESSION CONTEXT:\n- test block"
    modifier = _build_state_modifier(mock_llm, session_ctx=ctx)
    with patch("app.application.services.agent_graph.trim_messages") as mock_trim:
        mock_trim.return_value = [HumanMessage(content="Hello")]
        messages = modifier({"messages": [HumanMessage(content="Hello")]})
    assert isinstance(messages[0], SystemMessage)
    assert messages[0].content.startswith(ctx)
    assert SYSTEM_PROMPT in messages[0].content


def test_state_modifier_includes_trimmed_messages():
    mock_llm = MagicMock()
    modifier = _build_state_modifier(mock_llm)
    human_msg = HumanMessage(content="Hello")
    with patch("app.application.services.agent_graph.trim_messages") as mock_trim:
        mock_trim.return_value = [human_msg]
        messages = modifier({"messages": [human_msg]})
    assert human_msg in messages
