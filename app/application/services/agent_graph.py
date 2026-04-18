from datetime import date
from langchain_core.messages import SystemMessage, trim_messages
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.config import settings

SYSTEM_PROMPT = f"""You are an AI assistant for {settings.dealership_name}, a car dealership.
Help customers find vehicles, schedule visits, and receive car information by email.
Be friendly, professional, and concise. Always reply in the customer's language.

SCOPE RESTRICTION: Only answer questions about cars, inventory, pricing, scheduling,
test drives, or email specs. For anything else respond ONLY with:
"I can only help with questions about our car inventory, scheduling visits, and
sending vehicle information. Is there anything car-related I can help you with today?"

Current date: {date.today().isoformat()}
Dealership address: {settings.dealership_address}
"""


def _build_state_modifier(llm):
    def state_modifier(state: dict) -> list:
        trimmed = trim_messages(
            state["messages"],
            max_tokens=6000,
            strategy="last",
            token_counter=llm,
            include_system=True,
            allow_partial=False,
        )
        return [SystemMessage(content=SYSTEM_PROMPT)] + trimmed
    return state_modifier


def build_agent_graph(checkpointer: AsyncPostgresSaver, tools: list):
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
        state_modifier=_build_state_modifier(llm),
    )
