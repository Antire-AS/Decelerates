"""Email compose service — broker-authored outbound mail with auto-logged activity.

Plan §🟢 #10. Sends via the EmailOutboundPort (MS Graph) and then writes an
Activity row of type=email so the email shows up in the company timeline. The
two writes happen in sequence: if the send succeeds but the activity write
fails, we still consider the call successful — the email was delivered, the
activity log is best-effort. The reverse (activity-without-send) never happens
because we only write the activity AFTER the Graph 202 returns.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.db import Activity, ActivityType
from api.ports.driven.email_outbound_port import EmailOutboundPort
from api.services.audit import log_audit


class EmailComposeService:
    def __init__(self, db: Session, email_port: EmailOutboundPort) -> None:
        self.db = db
        self.email_port = email_port

    def compose_and_send(
        self,
        orgnr: str,
        firm_id: int,
        to: str,
        subject: str,
        body_html: str,
        author_email: str,
    ) -> Activity:
        """Send the email AND log it as an Activity. Raises on Graph failures
        so the route returns a real 5xx (vs silently logging the activity)."""
        message_id = self.email_port.send_email(to=to, subject=subject, body_html=body_html)
        # Trim long bodies for the activity preview — full HTML is in the
        # Sent items folder of the service mailbox.
        preview = (body_html[:300] + "…") if len(body_html) > 300 else body_html
        activity = Activity(
            orgnr=orgnr,
            firm_id=firm_id,
            created_by_email=author_email,
            activity_type=ActivityType.email,
            subject=f"📧 {subject}",
            body=preview,
            completed=True,  # an email is "done" the moment it's sent
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(activity)
        try:
            self.db.commit()
            self.db.refresh(activity)
        except Exception:
            self.db.rollback()
            raise
        log_audit(
            self.db,
            "email.send",
            orgnr=orgnr,
            actor_email=author_email,
            detail={"to": to, "subject": subject, "message_id": message_id},
        )
        return activity
