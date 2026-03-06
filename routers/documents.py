import io
import json
import os
import re
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import pdfplumber
from google import genai as google_genai
from google.genai import types as genai_types

from db import InsuranceDocument
from services import _llm_answer_raw
from schemas import DocChatRequest, DocCompareRequest
from dependencies import get_db
from constants import GEMINI_MODEL

router = APIRouter()


@router.post("/insurance-documents")
async def upload_insurance_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form("annet"),
    insurer: str = Form(""),
    year: Optional[int] = Form(None),
    period: str = Form("aktiv"),
    orgnr: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Upload and store an insurance document PDF."""
    pdf_bytes = await file.read()
    extracted = ""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = pdf.pages[:40]
            extracted = "\n".join(p.extract_text() or "" for p in pages)
    except Exception:
        pass

    doc = InsuranceDocument(
        title=title,
        category=category,
        insurer=insurer,
        year=year,
        period=period,
        orgnr=orgnr or None,
        filename=file.filename,
        pdf_content=pdf_bytes,
        extracted_text=extracted or None,
        uploaded_at=datetime.utcnow().isoformat(),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {
        "id": doc.id,
        "title": doc.title,
        "filename": doc.filename,
        "category": doc.category,
        "insurer": doc.insurer,
        "year": doc.year,
        "period": doc.period,
    }


@router.get("/insurance-documents")
def list_insurance_documents(
    category: Optional[str] = None,
    year: Optional[int] = None,
    period: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all insurance documents (no PDF bytes)."""
    q = db.query(InsuranceDocument)
    if category:
        q = q.filter(InsuranceDocument.category == category)
    if year:
        q = q.filter(InsuranceDocument.year == year)
    if period:
        q = q.filter(InsuranceDocument.period == period)
    docs = q.order_by(InsuranceDocument.uploaded_at.desc()).all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "filename": d.filename,
            "category": d.category,
            "insurer": d.insurer,
            "year": d.year,
            "period": d.period,
            "orgnr": d.orgnr,
            "uploaded_at": d.uploaded_at,
        }
        for d in docs
    ]


@router.get("/insurance-documents/{doc_id}/pdf")
def download_insurance_document_pdf(doc_id: int, db: Session = Depends(get_db)):
    """Serve the raw PDF bytes for an insurance document."""
    doc = db.query(InsuranceDocument).filter(InsuranceDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    safe_name = (doc.filename or f"document_{doc_id}.pdf").replace(" ", "_")
    return StreamingResponse(
        io.BytesIO(doc.pdf_content),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )


@router.get("/insurance-documents/{doc_id}/keypoints")
def get_document_keypoints(doc_id: int, db: Session = Depends(get_db)):
    """Extract key points from an insurance document using LLM or heuristics."""
    doc = db.query(InsuranceDocument).filter(InsuranceDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    keypoints_prompt = (
        "Du er en norsk forsikringsekspert. Analyser dette forsikringsdokumentet grundig og trekk ut ALLE viktige punkter.\n\n"
        "Returner KUN gyldig JSON i dette eksakte formatet (alle lister skal ha 5-8 punkter der det er mulig):\n"
        '{\n'
        '  "om_dokumentet": "1-2 setninger: hva slags forsikring er dette, hvem er tilbyder/forsikringsselskap",\n'
        '  "hva_dekkes": ["dekning 1", "dekning 2", "dekning 3", "dekning 4", "dekning 5"],\n'
        '  "forsikringssum": "beløp eller grense for dekning",\n'
        '  "egenandel": "egenandelbeløp og eventuelle varianter",\n'
        '  "forsikringsperiode": "dekningsperiode (fra–til eller løpende)",\n'
        '  "viktige_vilkaar": ["vilkår 1", "vilkår 2", "vilkår 3", "vilkår 4", "vilkår 5"],\n'
        '  "unntak": ["unntak 1", "unntak 2", "unntak 3"],\n'
        '  "kontaktinfo": "skadenummer, kontaktperson eller nettside",\n'
        '  "sammendrag": "3-4 setninger som beskriver hva dokumentet dekker, hvem det gjelder for, og viktigste betingelser"\n'
        '}'
    )

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            client = google_genai.Client(api_key=gemini_key, http_options={"timeout": 120})
            pdf_part = genai_types.Part.from_bytes(data=doc.pdf_content, mime_type="application/pdf")
            for model in ["gemini-2.5-flash", "gemini-1.5-flash", GEMINI_MODEL]:
                try:
                    resp = client.models.generate_content(
                        model=model,
                        contents=[pdf_part, keypoints_prompt],
                    )
                    import re as _re
                    m = _re.search(r"\{.*\}", resp.text, _re.DOTALL)
                    data = json.loads(m.group(0)) if m else json.loads(resp.text)
                    return {"doc_id": doc_id, "title": doc.title, **data}
                except Exception:
                    continue
        except Exception:
            pass

    # Fallback: heuristic extraction from extracted_text
    text = doc.extracted_text or ""
    if text:
        fallback = (
            f"{keypoints_prompt}\n\nDokument:\n{text[:8000]}"
        )
        raw = _llm_answer_raw(fallback)
        if raw:
            try:
                import re as _re
                m = _re.search(r"\{.*\}", raw, _re.DOTALL)
                data = json.loads(m.group(0)) if m else json.loads(raw)
                return {"doc_id": doc_id, "title": doc.title, **data}
            except Exception:
                pass

    return {
        "doc_id": doc_id,
        "title": doc.title,
        "sammendrag": (text[:400] + "…") if text else "Ingen tekstinnhold tilgjengelig",
        "viktige_vilkaar": [],
        "unntak": [],
    }


@router.delete("/insurance-documents/{doc_id}")
def delete_insurance_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(InsuranceDocument).filter(InsuranceDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    db.commit()
    return {"deleted": doc_id}


@router.post("/insurance-documents/{doc_id}/chat")
def chat_with_document(doc_id: int, body: DocChatRequest, db: Session = Depends(get_db)):
    """Ask a question about an insurance document using Gemini native PDF understanding."""
    doc = db.query(InsuranceDocument).filter(InsuranceDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    prompt = (
        f"Du er en norsk forsikringsrådgiver. Svar alltid på norsk. "
        f"Svar kun basert på innholdet i dette forsikringsdokumentet. "
        f"Vær presis og konkret. Oppgi sidetall eller avsnitt hvis relevant.\n\n"
        f"Spørsmål: {body.question}"
    )

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            client = google_genai.Client(api_key=gemini_key)
            pdf_part = genai_types.Part.from_bytes(data=doc.pdf_content, mime_type="application/pdf")
            for model in ["gemini-2.5-flash", "gemini-1.5-flash", GEMINI_MODEL]:
                try:
                    resp = client.models.generate_content(
                        model=model,
                        contents=[pdf_part, prompt],
                    )
                    return {"doc_id": doc_id, "question": body.question, "answer": resp.text}
                except Exception:
                    continue
        except Exception:
            pass

    # Fallback: use extracted text + LLM
    if doc.extracted_text is not None:
        fallback_prompt = (
            f"Du er en norsk forsikringsrådgiver. Svar alltid på norsk. "
            f"Svar kun basert på dette forsikringsdokumentets innhold:\n\n"
            f"{doc.extracted_text[:12000]}\n\n"
            f"Spørsmål: {body.question}"
        )
        answer = _llm_answer_raw(fallback_prompt)
        if answer:
            return {"doc_id": doc_id, "question": body.question, "answer": answer}

    raise HTTPException(status_code=503, detail="Ingen LLM tilgjengelig")


@router.post("/insurance-documents/compare")
def compare_insurance_documents(body: DocCompareRequest, db: Session = Depends(get_db)):
    """Compare two insurance documents using Gemini native PDF understanding."""
    if len(body.doc_ids) != 2:
        raise HTTPException(status_code=400, detail="Oppgi nøyaktig 2 dokument-IDer")

    docs = db.query(InsuranceDocument).filter(InsuranceDocument.id.in_(body.doc_ids)).all()
    if len(docs) != 2:
        raise HTTPException(status_code=404, detail="Ett eller begge dokumenter ikke funnet")

    # Sort to match input order
    id_order = {v: i for i, v in enumerate(body.doc_ids)}
    docs_sorted = sorted(docs, key=lambda d: id_order.get(d.id, 0))
    a, b = docs_sorted[0], docs_sorted[1]

    compare_prompt = (
        f"Du er en norsk forsikringsrådgiver som sammenligner to forsikringsdokumenter. "
        f"Svar alltid på norsk.\n\n"
        f"Dokument A: {a.title} ({a.insurer}, {a.year})\n"
        f"Dokument B: {b.title} ({b.insurer}, {b.year})\n\n"
        f"Returner KUN gyldig JSON (ingen markdown, ingen tekst utenfor JSON):\n"
        f'{{\n'
        f'  "doc_a_summary": "3-4 setninger om hva Dokument A dekker, for hvem og viktigste betingelser",\n'
        f'  "doc_b_summary": "3-4 setninger om hva Dokument B dekker, for hvem og viktigste betingelser",\n'
        f'  "pros_a": ["fordel 1", "fordel 2", "fordel 3"],\n'
        f'  "cons_a": ["ulempe 1", "ulempe 2"],\n'
        f'  "pros_b": ["fordel 1", "fordel 2", "fordel 3"],\n'
        f'  "cons_b": ["ulempe 1", "ulempe 2"],\n'
        f'  "comparison": [\n'
        f'    {{"area": "Dekningsomfang", "doc_a": "hva A sier", "doc_b": "hva B sier", "winner": "A|B|Lik"}}\n'
        f'  ],\n'
        f'  "conclusion": "Samlet konklusjon for forsikringstaker — 3-4 setninger"\n'
        f'}}\n\n'
        f'Inkluder i comparison: Dekningsomfang, Selvrisiko, Forsikringssum, Unntak/begrensninger, '
        f'Særlige vilkår, Forsikringsperiode, og andre viktige punkter. '
        f'winner=A betyr at A er bedre for forsikringstaker, B=B er bedre, Lik=ingen vesentlig forskjell.'
    )

    text_a = str(a.extracted_text) if a.extracted_text is not None else ""
    text_b = str(b.extracted_text) if b.extracted_text is not None else ""
    gemini_key = os.getenv("GEMINI_API_KEY")

    def _parse_compare_result(raw: str) -> dict:
        """Try to parse structured JSON from LLM response. Falls back to raw text."""
        if not raw:
            return {}
        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned)
            return json.loads(cleaned)
        except Exception:
            return {"raw_text": raw}

    def _build_response(raw: Optional[str]) -> dict:
        base = {"doc_a": {"id": a.id, "title": a.title}, "doc_b": {"id": b.id, "title": b.title}}
        if raw:
            base["structured"] = _parse_compare_result(raw)
        return base

    # Fast path: both docs have pre-cached text
    if text_a and text_b:
        fast_prompt = (
            f"{compare_prompt}\n\n"
            f"--- DOKUMENT A: {a.title} ---\n{text_a[:10000]}\n\n"
            f"--- DOKUMENT B: {b.title} ---\n{text_b[:10000]}"
        )
        result = _llm_answer_raw(fast_prompt)
        if result:
            return _build_response(result)

    # Slow path: Gemini native PDF understanding
    if gemini_key:
        try:
            client = google_genai.Client(api_key=gemini_key, http_options={"timeout": 280})
            pdf_a = genai_types.Part.from_bytes(data=a.pdf_content, mime_type="application/pdf")
            pdf_b = genai_types.Part.from_bytes(data=b.pdf_content, mime_type="application/pdf")
            for model in ["gemini-2.5-flash", "gemini-1.5-flash", GEMINI_MODEL]:
                try:
                    resp = client.models.generate_content(
                        model=model,
                        contents=[pdf_a, pdf_b, compare_prompt],
                    )
                    return _build_response(resp.text)
                except Exception:
                    continue
        except Exception:
            pass

    # Last resort: partial text fallback
    if text_a or text_b:
        fallback_prompt = (
            f"{compare_prompt}\n\n"
            f"--- DOKUMENT A: {a.title} ---\n{text_a[:8000]}\n\n"
            f"--- DOKUMENT B: {b.title} ---\n{text_b[:8000]}"
        )
        result = _llm_answer_raw(fallback_prompt)
        if result:
            return _build_response(result)

    raise HTTPException(
        status_code=503,
        detail="Ingen LLM tilgjengelig — legg til GEMINI_API_KEY i .env og restart appen"
    )
