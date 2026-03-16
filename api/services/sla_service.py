"""SLA agreement creation service."""
from datetime import datetime, timezone
from typing import Dict, Any

from sqlalchemy.orm import Session

from api.db import SlaAgreement, BrokerSettings
from api.schemas import SlaIn


class SlaService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_agreement(self, body: SlaIn) -> SlaAgreement:
        """Create and persist a new SLA agreement, embedding a broker snapshot."""
        fd = body.form_data
        broker_row = self.db.query(BrokerSettings).filter(BrokerSettings.id == 1).first()
        broker_snap: Dict[str, Any] = {}
        if broker_row:
            broker_snap = {
                "firm_name": broker_row.firm_name,
                "orgnr": broker_row.orgnr,
                "address": broker_row.address,
                "contact_name": broker_row.contact_name,
                "contact_email": broker_row.contact_email,
                "contact_phone": broker_row.contact_phone,
            }

        agreement = SlaAgreement(
            created_at=datetime.now(timezone.utc).isoformat(),
            broker_snapshot=broker_snap,
            client_orgnr=fd.get("client_orgnr"),
            client_navn=fd.get("client_navn"),
            client_adresse=fd.get("client_adresse"),
            client_kontakt=fd.get("client_kontakt"),
            start_date=fd.get("start_date"),
            account_manager=fd.get("account_manager"),
            insurance_lines=fd.get("insurance_lines", []),
            fee_structure=fd.get("fee_structure", {}),
            status="active",
            form_data=fd,
        )
        self.db.add(agreement)
        self.db.commit()
        self.db.refresh(agreement)
        return agreement
