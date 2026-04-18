import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings
from app.domain.entities.car import Car
from app.domain.exceptions import EmailSendError
from app.domain.repositories.email_log_repository import IEmailLogRepository
from app.domain.use_cases.email_use_case import IEmailService

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


class GmailAdapter(IEmailService):
    def __init__(self, email_log_repo: IEmailLogRepository) -> None:
        self._email_log_repo = email_log_repo

    async def send_car_specs(self, recipient_email: str, car: Car) -> bool:
        subject = f"Car Specs: {car.year} {car.brand} {car.model}"
        html_body = self._build_html(car)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.gmail_sender
        msg["To"] = recipient_email
        msg.attach(MIMEText(html_body, "html"))

        success = False
        error: str | None = None
        try:
            await asyncio.to_thread(self._send_sync, msg.as_string(), recipient_email)
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

    def _send_sync(self, message_str: str, recipient: str) -> None:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(settings.gmail_sender, settings.gmail_app_password)
            smtp.sendmail(settings.gmail_sender, [recipient], message_str)

    def _build_html(self, car: Car) -> str:
        image_tag = (
            f'<img src="{car.image_url}" style="max-width:400px"/><br/>'
            if car.image_url
            else ""
        )
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
