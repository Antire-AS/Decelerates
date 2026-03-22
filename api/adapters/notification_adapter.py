"""Azure Communication Services email adapter — implements NotificationPort."""
import logging
from dataclasses import dataclass
from typing import Optional

from api.ports.driven.notification_port import NotificationPort

logger = logging.getLogger(__name__)

_DEFAULT_SENDER = "donotreply@acs-broker-accelerator-prod.azurecomm.net"


@dataclass(frozen=True)
class NotificationConfig:
    conn_str: Optional[str] = None  # AZURE_COMMUNICATION_CONNECTION_STRING
    sender: str = _DEFAULT_SENDER   # ACS_SENDER_ADDRESS


class AzureEmailNotificationAdapter(NotificationPort):
    def __init__(self, config: NotificationConfig) -> None:
        self._config = config

    def is_configured(self) -> bool:
        conn = self._config.conn_str or ""
        return bool(conn and conn != "your_connection_string_here")

    def _email_client(self):
        from azure.communication.email import EmailClient
        return EmailClient.from_connection_string(self._config.conn_str)

    def send_email(self, to: str, subject: str, body_html: str) -> bool:
        if not self.is_configured():
            return False
        try:
            message = {
                "senderAddress": self._config.sender,
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

    def send_portfolio_digest(
        self, to: str, portfolio_name: str, alerts: list[dict]
    ) -> bool:
        if not alerts:
            return False

        _SEV_ICON = {"Kritisk": "🚨", "Høy": "🔴", "Moderat": "🟡"}
        _SEV_COLOR = {"Kritisk": "#c0392b", "Høy": "#e67e22", "Moderat": "#f1c40f"}

        rows_html = ""
        for a in alerts:
            icon = _SEV_ICON.get(a.get("severity", ""), "⚪")
            color = _SEV_COLOR.get(a.get("severity", ""), "#888")
            rows_html += (
                f"<tr>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>"
                f"<span style='color:{color};font-weight:bold'>{icon} {a.get('severity','')}</span></td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'><strong>{a.get('navn','')}</strong></td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{a.get('alert_type','')}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{a.get('detail','')}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{a.get('year_from','')}→{a.get('year_to','')}</td>"
                f"</tr>"
            )

        subject = f"Porteføljedigest — {portfolio_name} ({len(alerts)} varsler)"
        body_html = f"""
        <html><body style='font-family:Arial,sans-serif;color:#222;'>
        <h2 style='color:#1a252f'>Broker Accelerator — Porteføljedigest</h2>
        <p>Portefølje: <strong>{portfolio_name}</strong> &nbsp;·&nbsp;
           <strong>{len(alerts)}</strong> aktive varsler</p>
        <table style='border-collapse:collapse;width:100%;font-size:14px'>
          <thead>
            <tr style='background:#f5f5f5'>
              <th style='padding:8px 12px;text-align:left'>Alvorlighet</th>
              <th style='padding:8px 12px;text-align:left'>Selskap</th>
              <th style='padding:8px 12px;text-align:left'>Varselstype</th>
              <th style='padding:8px 12px;text-align:left'>Detalj</th>
              <th style='padding:8px 12px;text-align:left'>År</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
        <p style='margin-top:24px;font-size:12px;color:#888'>
          Logg inn i Broker Accelerator for å se fullstendige detaljer og åpne selskapsprofiler.
        </p>
        </body></html>
        """
        return self.send_email(to, subject, body_html)
