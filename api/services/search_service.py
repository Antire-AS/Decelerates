"""Azure AI Search integration for vector chunk storage and retrieval."""

import logging
import os
import uuid

logger = logging.getLogger(__name__)

_ENDPOINT_ENV = "AZURE_SEARCH_ENDPOINT"
_API_KEY_ENV = "AZURE_SEARCH_API_KEY"
_INDEX_NAME_ENV = "AZURE_SEARCH_INDEX_NAME"
_DEFAULT_INDEX = "company-chunks"
_EMBEDDING_DIMS = 512


def _is_configured() -> bool:
    endpoint = os.getenv(_ENDPOINT_ENV, "")
    key = os.getenv(_API_KEY_ENV, "")
    return bool(
        endpoint and key and endpoint != "your_endpoint_here" and key != "your_key_here"
    )


def _get_index_name() -> str:
    return os.getenv(_INDEX_NAME_ENV, _DEFAULT_INDEX)


def _build_index_schema(index_name: str):
    from azure.search.documents.indexes.models import (
        SearchIndex,
        SimpleField,
        SearchableField,
        SearchField,
        VectorSearch,
        HnswAlgorithmConfiguration,
        VectorSearchProfile,
    )
    from azure.search.documents.indexes import SearchIndexClient  # noqa: F401 (type hint only)
    from azure.search.documents import SearchClient  # noqa: F401

    fields = [
        SimpleField(name="id", type="Edm.String", key=True),
        SimpleField(name="orgnr", type="Edm.String", filterable=True),
        SimpleField(name="source", type="Edm.String", filterable=True),
        SearchableField(name="chunk_text", type="Edm.String"),
        SearchField(
            name="embedding",
            type="Collection(Edm.Single)",
            searchable=True,
            vector_search_dimensions=_EMBEDDING_DIMS,
            vector_search_profile_name="hnsw-profile",
        ),
    ]
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw-algo")],
        profiles=[
            VectorSearchProfile(
                name="hnsw-profile", algorithm_configuration_name="hnsw-algo"
            )
        ],
    )
    return SearchIndex(name=index_name, fields=fields, vector_search=vector_search)


class SearchService:
    def is_configured(self) -> bool:
        return _is_configured()

    def _index_client(self):
        from azure.search.documents.indexes import SearchIndexClient
        from azure.core.credentials import AzureKeyCredential

        endpoint = os.getenv(_ENDPOINT_ENV)
        key = os.getenv(_API_KEY_ENV)
        return SearchIndexClient(endpoint=endpoint, credential=AzureKeyCredential(key))

    def _search_client(self):
        from azure.search.documents import SearchClient
        from azure.core.credentials import AzureKeyCredential

        endpoint = os.getenv(_ENDPOINT_ENV)
        key = os.getenv(_API_KEY_ENV)
        return SearchClient(
            endpoint=endpoint,
            index_name=_get_index_name(),
            credential=AzureKeyCredential(key),
        )

    def ensure_index(self) -> None:
        """Create the search index if it does not already exist."""
        if not self.is_configured():
            return
        try:
            from azure.core.exceptions import ResourceNotFoundError

            client = self._index_client()
            index_name = _get_index_name()
            try:
                client.get_index(index_name)
            except ResourceNotFoundError:
                schema = _build_index_schema(index_name)
                client.create_index(schema)
                logger.info("Azure AI Search: created index '%s'", index_name)
        except Exception as exc:
            logger.warning("Azure AI Search: ensure_index failed — %s", exc)

    def index_chunk(
        self, orgnr: str, source: str, chunk_text: str, embedding: list
    ) -> str:
        """Upload a single chunk document. Returns the document id."""
        if not self.is_configured():
            return ""
        try:
            doc_id = str(uuid.uuid4())
            document = {
                "id": doc_id,
                "orgnr": orgnr,
                "source": source,
                "chunk_text": chunk_text,
                "embedding": embedding or [],
            }
            self._search_client().upload_documents(documents=[document])
            return doc_id
        except Exception as exc:
            logger.warning("Azure AI Search: index_chunk failed — %s", exc)
            return ""

    def search_chunks(
        self, orgnr: str, question_embedding: list, limit: int = 5
    ) -> list[str]:
        """Vector search filtered by orgnr. Returns list of chunk_text strings."""
        if not self.is_configured():
            return []
        try:
            from azure.search.documents.models import VectorizedQuery

            vector_query = VectorizedQuery(
                vector=question_embedding,
                k_nearest_neighbors=limit,
                fields="embedding",
            )
            results = self._search_client().search(
                search_text=None,
                vector_queries=[vector_query],
                filter=f"orgnr eq '{orgnr}'",
                top=limit,
            )
            return [r["chunk_text"] for r in results if r.get("chunk_text")]
        except Exception as exc:
            logger.warning("Azure AI Search: search_chunks failed — %s", exc)
            return []

    def delete_chunks(self, orgnr: str) -> int:
        """Delete all index documents for a given orgnr. Returns count deleted."""
        if not self.is_configured():
            return 0
        try:
            client = self._search_client()
            results = client.search(
                search_text="*", filter=f"orgnr eq '{orgnr}'", select=["id"]
            )
            docs = [{"id": r["id"]} for r in results]
            if not docs:
                return 0
            client.delete_documents(documents=docs)
            return len(docs)
        except Exception as exc:
            logger.warning("Azure AI Search: delete_chunks failed — %s", exc)
            return 0
