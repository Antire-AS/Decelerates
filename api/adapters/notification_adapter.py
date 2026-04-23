"""Azure Communication Services email adapter — implements NotificationPort."""

import base64
import logging
from dataclasses import dataclass
from typing import List, Optional

from api.ports.driven.notification_port import EmailAttachment, NotificationPort

logger = logging.getLogger(__name__)

_DEFAULT_SENDER = "donotreply@acs-broker-accelerator-prod.azurecomm.net"


@dataclass(frozen=True)
class NotificationConfig:
    conn_str: Optional[str] = None  # AZURE_COMMUNICATION_CONNECTION_STRING
    sender: str = _DEFAULT_SENDER  # ACS_SENDER_ADDRESS


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

    def send_email_with_attachments(
        self,
        to: str,
        subject: str,
        body_html: str,
        attachments: List[EmailAttachment],
        cc: Optional[List[str]] = None,
    ) -> bool:
        """ACS attachments: base64 content in the `attachments` array.
        The SDK passes that through to the REST API untouched."""
        if not self.is_configured():
            return False
        try:
            recipients: dict = {"to": [{"address": to}]}
            if cc:
                recipients["cc"] = [{"address": addr} for addr in cc]
            encoded_attachments = [
                {
                    "name": a.filename,
                    "contentType": a.content_type,
                    "contentInBase64": base64.b64encode(a.content).decode("ascii"),
                }
                for a in attachments
            ]
            message = {
                "senderAddress": self._config.sender,
                "recipients": recipients,
                "content": {"subject": subject, "html": body_html},
                "attachments": encoded_attachments,
            }
            poller = self._email_client().begin_send(message)
            poller.result()
            return True
        except Exception as exc:
            logger.warning("ACS send_email_with_attachments failed — %s", exc)
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
                f"<span style='color:{color};font-weight:bold'>{icon} {a.get('severity', '')}</span></td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'><strong>{a.get('navn', '')}</strong></td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{a.get('alert_type', '')}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{a.get('detail', '')}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{a.get('year_from', '')}→{a.get('year_to', '')}</td>"
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

    @staticmethod
    def _activity_row(a: dict, color: str) -> str:
        due = a.get("due_date") or "–"
        return (
            f"<tr>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #eee;"
            f"color:{color};font-weight:bold'>{due}</td>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>"
            f"{a.get('activity_type', '').capitalize()}</td>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>"
            f"<strong>{a.get('subject', '')}</strong></td>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>"
            f"{a.get('orgnr') or '–'}</td>"
            f"</tr>"
        )

    def send_activity_reminders(
        self, to: str, overdue: list[dict], due_today: list[dict]
    ) -> bool:
        if not overdue and not due_today:
            return False
        rows = "".join(
            [self._activity_row(a, "#c0392b") for a in overdue]
            + [self._activity_row(a, "#e67e22") for a in due_today]
        )
        n = len(overdue) + len(due_today)
        subject = f"Aktivitetspåminnelse — {n} oppgaver krever oppfølging"
        body_html = (
            "<html><body style='font-family:Arial,sans-serif;color:#222'>"
            "<h2 style='color:#1a252f'>Broker Accelerator — Aktivitetspåminnelse</h2>"
            f"<p><strong>{len(overdue)}</strong> forfalt · "
            f"<strong>{len(due_today)}</strong> forfaller i dag</p>"
            "<table style='border-collapse:collapse;width:100%;font-size:14px'>"
            "<thead><tr style='background:#f5f5f5'>"
            "<th style='padding:8px 12px;text-align:left'>Forfallsdato</th>"
            "<th style='padding:8px 12px;text-align:left'>Type</th>"
            "<th style='padding:8px 12px;text-align:left'>Oppgave</th>"
            "<th style='padding:8px 12px;text-align:left'>Orgnr</th>"
            f"</tr></thead><tbody>{rows}</tbody></table>"
            "<p style='margin-top:24px;font-size:12px;color:#888'>"
            "Logg inn i Broker Accelerator for å fullføre oppgavene.</p>"
            "</body></html>"
        )
        return self.send_email(to, subject, body_html)

    def send_forsikringstilbud(
        self, to: str, client_navn: str, orgnr: str, share_url: str
    ) -> bool:
        subject = f"Forsikringstilbud klar — {client_navn}"
        body_html = f"""
        <html><body style='font-family:Arial,sans-serif;color:#222'>
        <h2 style='color:#1a252f'>Broker Accelerator — Forsikringstilbud</h2>
        <p>Hei,</p>
        <p>Et forsikringstilbud for <strong>{client_navn}</strong> (orgnr: {orgnr})
        er nå klart for gjennomgang.</p>
        <p><a href='{share_url}' style='background:#1a73e8;color:#fff;padding:10px 20px;
        border-radius:4px;text-decoration:none;display:inline-block;margin-top:8px'>
        Se tilbudet</a></p>
        <p style='margin-top:24px;font-size:12px;color:#888'>
        Lenken er gyldig i 30 dager.</p>
        </body></html>
        """
        return self.send_email(to, subject, body_html)

    def send_renewal_stage_change(
        self, to: str, policy_number: str, insurer: str, product_type: str, stage: str
    ) -> bool:
        _STAGE_LABELS = {
            "not_started": "Ikke startet",
            "ready_to_quote": "Klar for tilbud",
            "quoted": "Tilbud sendt",
            "accepted": "Akseptert",
            "declined": "Avslått",
        }
        _STAGE_COLORS = {
            "not_started": "#888888",
            "ready_to_quote": "#e67e22",
            "quoted": "#2980b9",
            "accepted": "#27ae60",
            "declined": "#c0392b",
        }
        label = _STAGE_LABELS.get(stage, stage)
        color = _STAGE_COLORS.get(stage, "#888")
        subject = f"Fornyelse oppdatert — {policy_number} ({insurer})"
        body_html = f"""
        <html><body style='font-family:Arial,sans-serif;color:#222'>
        <h2 style='color:#1a252f'>Broker Accelerator — Fornyelse oppdatert</h2>
        <p>Status for følgende forsikringsavtale er oppdatert:</p>
        <table style='border-collapse:collapse;font-size:14px;margin:12px 0'>
          <tr><td style='padding:6px 16px 6px 0;color:#666'>Avtalenummer</td>
              <td style='padding:6px 0'><strong>{policy_number}</strong></td></tr>
          <tr><td style='padding:6px 16px 6px 0;color:#666'>Forsikringsselskap</td>
              <td style='padding:6px 0'>{insurer}</td></tr>
          <tr><td style='padding:6px 16px 6px 0;color:#666'>Produkt</td>
              <td style='padding:6px 0'>{product_type}</td></tr>
          <tr><td style='padding:6px 16px 6px 0;color:#666'>Ny status</td>
              <td style='padding:6px 0'>
                <span style='background:{color};color:#fff;padding:3px 10px;
                border-radius:12px;font-size:13px'>{label}</span>
              </td></tr>
        </table>
        <p style='margin-top:24px;font-size:12px;color:#888'>
          Logg inn i Broker Accelerator for å se fornyelsespipelinen.</p>
        </body></html>
        """
        return self.send_email(to, subject, body_html)

    def send_renewal_threshold_emails(
        self, to: str, threshold_days: int, policies: list[dict]
    ) -> bool:
        """Send targeted renewal reminder for a specific threshold (90/60/30 days)."""
        if not policies:
            return False
        color = (
            "#c0392b"
            if threshold_days <= 30
            else ("#e67e22" if threshold_days <= 60 else "#f1c40f")
        )
        rows_html = ""
        for p in policies:
            days = p.get("days_to_renewal", threshold_days)
            rows_html += (
                f"<tr>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee;color:{color};font-weight:bold'>"
                f"{days} dager</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{p.get('orgnr', '')}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{p.get('insurer', '')}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{p.get('product_type', '')}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>"
                f"kr {p.get('annual_premium_nok') or '–'}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{p.get('renewal_date', '')}</td>"
                f"</tr>"
            )
        subject = f"Fornyelsespåminnelse — {len(policies)} avtaler forfaller innen {threshold_days} dager"
        body_html = (
            "<html><body style='font-family:Arial,sans-serif;color:#222;'>"
            "<h2 style='color:#1a252f'>Broker Accelerator — Fornyelsespåminnelse</h2>"
            f"<p><strong>{len(policies)}</strong> forsikringsavtaler forfaller innen "
            f"<strong>{threshold_days} dager</strong>.</p>"
            "<table style='border-collapse:collapse;width:100%;font-size:14px'>"
            "<thead><tr style='background:#f5f5f5'>"
            "<th style='padding:8px 12px;text-align:left'>Dager igjen</th>"
            "<th style='padding:8px 12px;text-align:left'>Orgnr</th>"
            "<th style='padding:8px 12px;text-align:left'>Forsikringsselskap</th>"
            "<th style='padding:8px 12px;text-align:left'>Produkt</th>"
            "<th style='padding:8px 12px;text-align:left'>Årspremie</th>"
            "<th style='padding:8px 12px;text-align:left'>Fornyelsesdato</th>"
            f"</tr></thead><tbody>{rows_html}</tbody></table>"
            "<p style='margin-top:24px;font-size:12px;color:#888'>"
            "Logg inn i Broker Accelerator for å se fornyelsespipelinen.</p>"
            "</body></html>"
        )
        return self.send_email(to, subject, body_html)

    def send_renewal_digest(self, to: str, renewals: list[dict]) -> bool:
        if not renewals:
            return False

        def _color(days: int) -> str:
            if days <= 30:
                return "#c0392b"
            if days <= 60:
                return "#e67e22"
            return "#f1c40f"

        rows_html = ""
        for r in renewals:
            days = r.get("days_to_renewal", 0)
            rows_html += (
                f"<tr>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee;"
                f"color:{_color(days)};font-weight:bold'>{days} dager</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{r.get('orgnr', '')}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{r.get('insurer', '')}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{r.get('product_type', '')}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>"
                f"kr {r.get('annual_premium_nok') or '–'}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{r.get('renewal_date', '')}</td>"
                f"</tr>"
            )

        subject = f"Fornyelsespåminnelse — {len(renewals)} avtaler forfaller snart"
        body_html = (
            "<html><body style='font-family:Arial,sans-serif;color:#222;'>"
            "<h2 style='color:#1a252f'>Broker Accelerator — Fornyelsesdigest</h2>"
            f"<p><strong>{len(renewals)}</strong> aktive forsikringsavtaler forfaller innen 90 dager.</p>"
            "<table style='border-collapse:collapse;width:100%;font-size:14px'>"
            "<thead><tr style='background:#f5f5f5'>"
            "<th style='padding:8px 12px;text-align:left'>Dager igjen</th>"
            "<th style='padding:8px 12px;text-align:left'>Orgnr</th>"
            "<th style='padding:8px 12px;text-align:left'>Forsikringsselskap</th>"
            "<th style='padding:8px 12px;text-align:left'>Produkt</th>"
            "<th style='padding:8px 12px;text-align:left'>Årspremie</th>"
            "<th style='padding:8px 12px;text-align:left'>Fornyelsesdato</th>"
            f"</tr></thead><tbody>{rows_html}</tbody></table>"
            "<p style='margin-top:24px;font-size:12px;color:#888'>"
            "Logg inn i Broker Accelerator for å se fornyelsespipelinen.</p>"
            "</body></html>"
        )
        return self.send_email(to, subject, body_html)
