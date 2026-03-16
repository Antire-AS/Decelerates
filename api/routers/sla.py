import io

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.db import SlaAgreement
from api.services import _generate_sla_pdf
from api.services.sla_service import SlaService
from api.schemas import SlaIn
from api.dependencies import get_db

router = APIRouter()


def _get_sla_service(db: Session = Depends(get_db)) -> SlaService:
    return SlaService(db)


@router.post("/sla")
def create_sla(body: SlaIn, svc: SlaService = Depends(_get_sla_service)):
    agreement = svc.create_agreement(body)
    return {"id": agreement.id, "created_at": agreement.created_at}


@router.get("/sla")
def list_slas(db: Session = Depends(get_db)):
    rows = db.query(SlaAgreement).order_by(SlaAgreement.id.desc()).all()
    return [
        {
            "id": r.id,
            "created_at": r.created_at,
            "client_navn": r.client_navn,
            "client_orgnr": r.client_orgnr,
            "start_date": r.start_date,
            "insurance_lines": r.insurance_lines,
            "status": r.status,
        }
        for r in rows
    ]


@router.get("/sla/{sla_id}")
def get_sla(sla_id: int, db: Session = Depends(get_db)):
    row = db.query(SlaAgreement).filter(SlaAgreement.id == sla_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="SLA not found")
    return {
        "id": row.id,
        "created_at": row.created_at,
        "broker_snapshot": row.broker_snapshot,
        "client_orgnr": row.client_orgnr,
        "client_navn": row.client_navn,
        "client_adresse": row.client_adresse,
        "client_kontakt": row.client_kontakt,
        "start_date": row.start_date,
        "account_manager": row.account_manager,
        "insurance_lines": row.insurance_lines,
        "fee_structure": row.fee_structure,
        "status": row.status,
        "form_data": row.form_data,
    }


@router.get("/sla/{sla_id}/pdf")
def download_sla_pdf(sla_id: int, db: Session = Depends(get_db)):
    row = db.query(SlaAgreement).filter(SlaAgreement.id == sla_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="SLA not found")
    pdf_bytes = _generate_sla_pdf(row)
    filename = f"tjenesteavtale_{row.client_orgnr or sla_id}_{(row.created_at or '')[:10]}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
