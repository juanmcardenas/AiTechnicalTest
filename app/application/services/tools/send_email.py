import json

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.domain.repositories.email_log_repository import IEmailLogRepository
from app.domain.repositories.inventory_repository import IInventoryRepository
from app.domain.repositories.lead_repository import ILeadRepository
from app.domain.use_cases.email_use_case import IEmailService


def make_send_email_tool(
    inventory_repo: IInventoryRepository,
    email_service: IEmailService,
    email_log_repo: IEmailLogRepository,
    lead_repo: ILeadRepository,
):
    @tool
    async def send_email(
        car_id: str,
        recipient_email: str,
        config: RunnableConfig = None,
    ) -> str:
        """Send a car specification HTML email via Gmail. Logs the result to email_sent_logs.
        Requires the lead to be identified (name, email, or phone on file)."""
        lead_id = (config or {}).get("configurable", {}).get("lead_id")
        if not lead_id:
            return json.dumps({"error": "Lead context missing"})
        lead = await lead_repo.get_by_id(lead_id)
        if lead is None or not (lead.name or lead.email or lead.phone):
            return json.dumps({
                "error": (
                    "Lead not identified. Ask the customer for their name, email, "
                    "or phone first and call update_lead_identity before retrying."
                )
            })

        car = await inventory_repo.get_car_by_id(car_id)
        if not car:
            return json.dumps({"error": f"Car {car_id} not found"})
        try:
            await email_service.send_car_specs(recipient_email, car)
            return json.dumps({"success": True, "message": f"Email sent to {recipient_email}"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    return send_email
