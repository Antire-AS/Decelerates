"""Azure Communication Services email notifications."""
import logging
import os

logger = logging.getLogger(__name__)

_CONN_STR_ENV = "AZURE_COMMUNICATION_CONNECTION_STRING"
_SENDER_ENV = "ACS_SENDER_ADDRESS"
_DEFAULT_SENDER = "donotreply@acs-broker-accelerator-prod.azurecomm.net"


def _is_configured() -> bool:
    conn = os.getenv(_CONN_STR_ENV, "")
    return bool(conn and conn != "your_connection_string_here")


class NotificationService:
    def is_configured(self) -> bool:
        return _is_configured()

    def _sender(self) -> str:
        return os.getenv(_SENDER_ENV, _DEFAULT_SENDER)

    def _email_client(self):
        from azure.communication.email import EmailClient

        return EmailClient.from_connection_string(os.getenv(_CONN_STR_ENV))

    def send_email(self, to: str, subject: str, body_html: str) -> bool:
        """Send an HTML email via ACS. Returns True on success."""
        if not self.is_configured():
            return False
        try:
            message = {
                "senderAddress": self._sender(),
                "recipients": {"to": [{"address": to}]},
                "content": {"subject": subject, "html": body_html},
            }
            poller = self._email_client().begin_send(message)
            poller.result()
            return True
        except Exception as exc:
            logger.warning("ACS send_email failed — %s", exc)
            return False

    def send_sla_generated(self, to: str, client_navn: str) -> bool:
        """Notify broker contact that a new SLA agreement has been generated."""
        subject = f"Tjenesteavtale klar — {client_navn}"
        body_html = f"""
        <html><body>
        <p>Hei,</p>
        <p>En ny tjenesteavtale for <strong>{client_navn}</strong> er nå generert og klar for nedlasting.</p>
        <p>Logg inn i Broker Accelerator for å laste ned PDF-en.</p>
        <p>Med vennlig hilsen,<br>Broker Accelerator</p>
        </body></html>
        """
        return self.send_email(to, subject, body_html)

    def send_risk_report_ready(self, to: str, orgnr: str, navn: str) -> bool:
        """Notify broker contact that a risk report has been generated."""
        subject = f"Risikorapport klar — {navn}"
        body_html = f"""
        <html><body>
        <p>Hei,</p>
        <p>Risikorapporten for <strong>{navn}</strong> (orgnr: {orgnr}) er nå klar.</p>
        <p>Logg inn i Broker Accelerator for å se rapporten.</p>
        <p>Med vennlig hilsen,<br>Broker Accelerator</p>
        </body></html>
        """
        return self.send_email(to, subject, body_html)
