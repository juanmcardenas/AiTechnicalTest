import json
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from app.domain.repositories.email_log_repository import IEmailLogRepository
from app.domain.repositories.inventory_repository import IInventoryRepository
from app.domain.use_cases.email_use_case import IEmailService


def make_send_email_tool(
    inventory_repo: IInventoryRepository,
    email_service: IEmailService,
    email_log_repo: IEmailLogRepository,
):
    @tool
    async def send_email(
        car_id: str,
        recipient_email: str,
        config: RunnableConfig = None,
    ) -> str:
        """Send a car specification HTML email via Gmail. Logs the result to email_sent_logs."""
        _ = (config or {}).get("configurable", {}).get("thread_id")
        car = await inventory_repo.get_car_by_id(car_id)
        if not car:
            return json.dumps({"error": f"Car {car_id} not found"})
        try:
            await email_service.send_car_specs(recipient_email, car)
            return json.dumps({"success": True, "message": f"Email sent to {recipient_email}"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    return send_email
