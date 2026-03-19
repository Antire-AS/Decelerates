"""Azure Document Intelligence service — PDF layout analysis."""
import os
from typing import Optional


def _di_endpoint() -> Optional[str]:
    return os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")


def _di_key() -> Optional[str]:
    return os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")


class DocumentIntelligenceService:
    """Wraps Azure Document Intelligence for PDF text extraction."""

    def __init__(self) -> None:
        self._client = None
        endpoint = _di_endpoint()
        if not endpoint:
            return
        try:
            from azure.ai.documentintelligence import DocumentIntelligenceClient
            key = _di_key()
            if key:
                from azure.core.credentials import AzureKeyCredential
                self._client = DocumentIntelligenceClient(
                    endpoint=endpoint,
                    credential=AzureKeyCredential(key),
                )
            else:
                from azure.identity import DefaultAzureCredential
                self._client = DocumentIntelligenceClient(
                    endpoint=endpoint,
                    credential=DefaultAzureCredential(),
                )
        except Exception:
            self._client = None

    def is_configured(self) -> bool:
        """Return True if the Document Intelligence endpoint env var is set."""
        return bool(_di_endpoint())

    def analyze_pdf(self, pdf_bytes: bytes) -> Optional[str]:
        """Analyze a PDF using the prebuilt-layout model. Returns extracted text or None."""
        if not self.is_configured() or self._client is None:
            return None
        try:
            poller = self._client.begin_analyze_document(
                "prebuilt-layout",
                analyze_request=pdf_bytes,
                content_type="application/octet-stream",
            )
            result = poller.result()
            return _extract_text_from_result(result)
        except Exception:
            return None


def _extract_text_from_result(result) -> str:
    """Pull page content and table cells out of a Document Intelligence result."""
    parts = []
    if hasattr(result, "pages") and result.pages:
        for page in result.pages:
            if hasattr(page, "lines") and page.lines:
                parts.extend(line.content for line in page.lines if line.content)
    if hasattr(result, "tables") and result.tables:
        for table in result.tables:
            if hasattr(table, "cells") and table.cells:
                parts.extend(
                    cell.content for cell in table.cells if cell.content
                )
    return "\n".join(parts)
