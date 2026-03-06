"""
Entry point for the Broker Accelerator API.

Run with:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Architecture overview:
  main.py      — this file: creates the FastAPI app and wires routers
  app.py       — core business logic, helper functions, all endpoint handlers
  prompts.py   — LLM prompt constants (imported by app.py and routers)
  rag_chain.py — LangChain RAG: chunk_text(), embed_chunks(), build_rag_chain()
  db.py        — SQLAlchemy models (Company, CompanyChunk, SlaAgreement, ...)
  risk.py      — pure risk scoring logic (derive_simple_risk, build_risk_summary)
  routers/     — future domain-specific APIRouter modules (company, sla, offers, ...)
  ui.py        — Streamlit frontend (separate process, calls this API on port 8000)
"""

# Re-export the FastAPI application from app.py.
# This lets us point uvicorn at either `app:app` (legacy) or `main:app` (new).
from app import app  # noqa: F401

__all__ = ["app"]
