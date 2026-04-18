import json

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.domain.repositories.lead_repository import ILeadRepository


def make_update_lead_identity_tool(lead_repo: ILeadRepository):
    @tool
    async def update_lead_identity(
        name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        config: RunnableConfig = None,
    ) -> str:
        """Save the customer's contact info to their lead record.
        Call this whenever the customer shares their name, email, or phone number.
        At least one of name/email/phone must be provided."""
        lead_id = (config or {}).get("configurable", {}).get("lead_id")
        if not lead_id:
            return json.dumps({"error": "Lead context missing"})
        if not (name or email or phone):
            return json.dumps({"error": "Provide at least one of name, email, phone"})
        lead = await lead_repo.get_by_id(lead_id)
        if lead is None:
            return json.dumps({"error": f"Lead {lead_id} not found"})
        if name is not None:
            lead.name = name
        if email is not None:
            lead.email = email
        if phone is not None:
            lead.phone = phone
        await lead_repo.update(lead)
        return json.dumps({
            "success": True,
            "name": lead.name,
            "email": lead.email,
            "phone": lead.phone,
        })

    return update_lead_identity
