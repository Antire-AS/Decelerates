"""
Stub out optional heavy dependencies so service modules can be imported
in tests without requiring google-genai, voyageai, anthropic, or pdfplumber.

The google.genai stub is set up so that both:
  from google import genai as google_genai   (used in services/llm.py)
  patch("google.genai.Client")               (used in test_llm.py)
refer to the SAME mock object, making patches work correctly.
"""
import sys
from unittest.mock import MagicMock

# google / google.genai — services/llm.py and services/pdf_extract.py
_google_genai = MagicMock()
_google_genai_types = MagicMock()

if "google" not in sys.modules:
    _google = MagicMock()
    sys.modules["google"] = _google
else:
    _google = sys.modules["google"]

# Ensure 'from google import genai' and sys.modules["google.genai"]
# resolve to the same object so patch("google.genai.Client") works.
_google.genai = _google_genai
sys.modules["google.genai"] = _google_genai
sys.modules["google.genai.types"] = _google_genai_types

# voyageai — services/llm.py
sys.modules.setdefault("voyageai", MagicMock())

# anthropic — services/llm.py
sys.modules.setdefault("anthropic", MagicMock())

# pdfplumber — services/pdf_extract.py
sys.modules.setdefault("pdfplumber", MagicMock())

# fpdf2 / fpdf — services/pdf_generate.py
sys.modules.setdefault("fpdf", MagicMock())

# pgvector / sqlalchemy extras — DB layer
sys.modules.setdefault("pgvector", MagicMock())
sys.modules.setdefault("pgvector.sqlalchemy", MagicMock())
