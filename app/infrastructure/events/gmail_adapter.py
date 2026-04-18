import json
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from googleapiclient.discovery import build
from google.oauth2 import service_account
from app.config import settings
from app.domain.entities.car import Car
from app.domain.exceptions import EmailSendError
from app.domain.repositories.email_log_repository import IEmailLogRepository
from app.domain.use_cases.email_use_case import IEmailService

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class GmailAdapter(IEmailService):
    def __init__(self, email_log_repo: IEmailLogRepository) -> None:
        self._email_log_repo = email_log_repo
        sa_info = settings.google_service_account_json
        if sa_info.endswith(".json"):
            with open(sa_info) as f:
                sa_dict = json.load(f)
        else:
            sa_dict = json.loads(sa_info)
        creds = service_account.Credentials.from_service_account_info(
            sa_dict, scopes=SCOPES, subject=settings.gmail_sender
        )
        self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    async def send_car_specs(self, recipient_email: str, car: Car) -> bool:
        subject = f"Car Specs: {car.year} {car.brand} {car.model}"
        html_body = self._build_html(car)
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.gmail_sender
        msg["To"] = recipient_email
        msg.attach(MIMEText(html_body, "html"))
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        success = False
        error = None
        try:
            self._service.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()
            success = True
        except Exception as e:
            error = str(e)
        await self._email_log_repo.log(
            lead_id="unknown",
            car_id=car.id,
            recipient=recipient_email,
            subject=subject,
            template="car_specs",
            success=success,
            error=error,
        )
        if not success:
            raise EmailSendError(error)
        return True

    def _build_html(self, car: Car) -> str:
        image_tag = f'<img src="{car.image_url}" style="max-width:400px"/><br/>' if car.image_url else ""
        return f"""
        <html><body>
        <h2>{car.year} {car.brand} {car.model}</h2>
        {image_tag}
        <table border="1" cellpadding="6">
          <tr><td>Color</td><td>{car.color}</td></tr>
          <tr><td>Price</td><td>${car.price:,.0f}</td></tr>
          <tr><td>KM</td><td>{car.km:,}</td></tr>
          <tr><td>Fuel</td><td>{car.fuel_type}</td></tr>
          <tr><td>Transmission</td><td>{car.transmission}</td></tr>
          <tr><td>Condition</td><td>{car.condition}</td></tr>
        </table>
        <p>{car.description or ""}</p>
        </body></html>
        """
