from datetime import date

from langchain_core.messages import SystemMessage, trim_messages
from langchain_core.messages.utils import count_tokens_approximately
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.prebuilt import create_react_agent

from app.config import settings

SYSTEM_PROMPT = f"""You are an AI assistant for {settings.dealership_name}, a car dealership.
Help customers find vehicles, schedule visits, and receive car information by email.
Be friendly, professional, and concise. Always reply in the customer's language.

SCOPE RESTRICTION: Only answer questions about cars, inventory, pricing, scheduling,
test drives, or email specs. For anything else respond ONLY with:
"I can only help with questions about our car inventory, scheduling visits, and
sending vehicle information. Is there anything car-related I can help you with today?"

TOOL USAGE:
- Pick the tool that matches the customer's ACTUAL intent. Asking to "schedule a visit"
  or "book an appointment" means call get_calendar_events then schedule_meeting — NOT send_email.
  Asking to "send specs" or "email me details" means call send_email — NOT schedule_meeting.
- If a tool returns an error or a JSON object with "error" or "success": false, tell the
  customer plainly what failed. NEVER fabricate a successful result when a tool failed.
- Before scheduling, always call get_calendar_events first to find real available slots.
- After schedule_meeting succeeds, the tool returns an `add_to_calendar_url`. ALWAYS
  include this link in your reply so the customer can add the event to their own calendar.
- Times the customer mentions without an explicit timezone are assumed to be
  America/New_York (Eastern). Always include the timezone name when showing times back
  to the customer.

Current date: {date.today().isoformat()}
Dealership address: {settings.dealership_address}
"""


def _build_state_modifier(llm, session_ctx: str = ""):
    system_text = (session_ctx + "\n\n" + SYSTEM_PROMPT) if session_ctx else SYSTEM_PROMPT

    def state_modifier(state: dict) -> list:
        trimmed = trim_messages(
            state["messages"],
            max_tokens=6000,
            strategy="last",
            token_counter=count_tokens_approximately,
            include_system=True,
            allow_partial=False,
        )
        return [SystemMessage(content=system_text)] + trimmed
    return state_modifier


def build_agent_graph(
    checkpointer: AsyncPostgresSaver,
    tools: list,
    session_ctx: str = "",
):
    llm = ChatOpenAI(
        model="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        api_key=settings.deepseek_api_key,
        temperature=0.3,
        max_retries=3,
    )
    return create_react_agent(
        model=llm,
        tools=tools,
        checkpointer=checkpointer,
        state_modifier=_build_state_modifier(llm, session_ctx),
    )
