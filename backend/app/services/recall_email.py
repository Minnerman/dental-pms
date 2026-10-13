"""Disabled by default. Enabling requires explicit server configuration and TLS."""
import smtplib
import ssl
from email.message import EmailMessage
from app.core.settings import settings


def email_ready() -> bool:
    return bool(settings.recall_email_enabled and settings.smtp_host
                and settings.smtp_username and settings.smtp_password)


def send_recall(copy):
    message = EmailMessage()
    message["From"] = copy.sender
    message["To"] = copy.recipient
    message["Subject"] = "Your dental recall"
    message["Message-ID"] = f"<dental-recall-{copy.id}@{copy.sender.split('@')[1]}>"
    message.set_content("Please find your dental recall letter attached. Please contact the practice to arrange an appointment.")
    message.add_attachment(copy.pdf_bytes, maintype="application", subtype="pdf", filename="dental-recall.pdf")
    context = ssl.create_default_context()
    if settings.smtp_ssl:
        connection = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20, context=context)
    else:
        connection = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
    with connection as smtp:
        if not settings.smtp_ssl:
            smtp.starttls(context=context)
        smtp.login(settings.smtp_username, settings.smtp_password)
        refused = smtp.send_message(message)
        if refused:
            raise RuntimeError("Recipient was not accepted")
