"""
LangChain RAG module — chunk-based retrieval for company knowledge.

Uses LangChain's RecursiveCharacterTextSplitter for proper document chunking,
while keeping the existing pgvector backend (CompanyChunk table in db.py).

Architecture:
  chunk_text()      — split a document into overlapping chunks
  embed_chunks()    — embed each chunk via the app's existing _embed() function
  build_rag_chain() — compose a retriever + prompt + LLM into a callable chain
"""

from __future__ import annotations

from typing import Callable, List

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Default chunking parameters.  800 chars ≈ ~200 tokens — a good balance
# between retrieval precision and context coverage.
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def chunk_text(
    text: str,
    source: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> List[Document]:
    """Split *text* into overlapping chunks using LangChain's recursive splitter.

    Args:
        text: The raw text to split (e.g. extracted PDF text).
        source: A label stored in Document.metadata, e.g. "annual_report_2023".
        chunk_size: Max characters per chunk.
        chunk_overlap: Overlap in characters between consecutive chunks.

    Returns:
        List of LangChain ``Document`` objects ready for embedding.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    return splitter.create_documents([text], metadatas=[{"source": source}])


def embed_chunks(
    chunks: List[Document],
    embed_fn: Callable[[str], List[float]],
) -> List[tuple[str, str, List[float]]]:
    """Embed each chunk.

    Args:
        chunks: LangChain Document list from :func:`chunk_text`.
        embed_fn: Callable that takes a string and returns an embedding vector.

    Returns:
        List of ``(chunk_text, source, embedding_vector)`` tuples.
    """
    results = []
    for doc in chunks:
        vector = embed_fn(doc.page_content)
        results.append((doc.page_content, doc.metadata.get("source", ""), vector))
    return results


def build_rag_chain(
    llm_fn: Callable[[str], str],
    retriever_fn: Callable[[str], List[str]],
    system_prompt: str,
) -> Callable[[str], str]:
    """Build a simple RAG chain using LangChain prompt templates.

    This follows the standard LangChain RAG pattern:
      retrieved context → ChatPromptTemplate → LLM → answer

    We intentionally keep our own LLM and retriever adapters so we don't depend
    on langchain-openai or langchain-community.

    Args:
        llm_fn: Callable(prompt_str) → answer_str  (wraps our _llm_answer_raw).
        retriever_fn: Callable(query) → list of relevant chunk texts.
        system_prompt: System message prepended to every prompt.

    Returns:
        A callable chain: question_str → answer_str
    """
    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt + "\n\nKontekst fra selskapsdata:\n{context}"),
            ("human", "{question}"),
        ]
    )

    def chain(question: str) -> str:
        context_chunks = retriever_fn(question)
        context = (
            "\n\n---\n\n".join(context_chunks)
            if context_chunks
            else "Ingen relevant kontekst funnet."
        )
        messages = prompt_template.format_messages(context=context, question=question)
        # Flatten to a single string for our LLM adapter
        formatted = "\n".join(f"[{m.type.upper()}]: {m.content}" for m in messages)
        return llm_fn(formatted)

    return chain
