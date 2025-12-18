"""Granola API client."""

import ssl

import certifi
import httpx

from granola.api.models import Document, DocumentList, DocumentListsResponse, GranolaResponse

# Constants matching the Go implementation
USER_AGENT = "Granola/5.354.0"
X_CLIENT_VERSION = "5.354.0"
API_URL = "https://api.granola.ai/v2/get-documents"
DOCUMENT_LISTS_URL = "https://api.granola.ai/v2/get-document-lists"


def _get_ssl_context() -> ssl.SSLContext:
    """Create an SSL context using certifi's CA bundle."""
    ctx = ssl.create_default_context(cafile=certifi.where())
    return ctx


class APIError(Exception):
    """Raised when an API request fails."""

    pass


class GranolaClient:
    """Client for the Granola API."""

    def __init__(self, access_token: str, timeout: int = 120):
        """Initialize the client.

        Args:
            access_token: Bearer token for authentication.
            timeout: Request timeout in seconds.
        """
        self.access_token = access_token
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": USER_AGENT,
            "X-Client-Version": X_CLIENT_VERSION,
            "Content-Type": "application/json",
            "Accept": "*/*",
        }

    def get_documents(self) -> list[Document]:
        """Fetch all documents from the API with pagination.

        Returns:
            List of all documents.

        Raises:
            APIError: If the API request fails.
        """
        documents: list[Document] = []
        offset = 0
        limit = 100

        with httpx.Client(timeout=self.timeout, verify=_get_ssl_context()) as client:
            while True:
                try:
                    response = client.post(
                        API_URL,
                        headers=self.headers,
                        json={
                            "limit": limit,
                            "offset": offset,
                            "include_last_viewed_panel": True,
                        },
                    )
                    response.raise_for_status()

                except httpx.HTTPStatusError as e:
                    body_preview = e.response.text[:200] if e.response.text else ""
                    raise APIError(
                        f"API request failed: status={e.response.status_code}, body={body_preview}"
                    ) from e

                except httpx.RequestError as e:
                    raise APIError(f"API request failed: {e}") from e

                # Parse response
                try:
                    data = response.json()
                    granola_response = GranolaResponse.model_validate(data)
                except Exception as e:
                    raise APIError(f"Failed to parse API response: {e}") from e

                documents.extend(granola_response.docs)

                # If we got fewer documents than the limit, we've reached the end
                if len(granola_response.docs) < limit:
                    break

                # Move to the next page
                offset += limit

        return documents

    def get_document_lists(self) -> list[DocumentList]:
        """Fetch all document lists (folders) from the API.

        Returns:
            List of document lists with their document IDs.

        Raises:
            APIError: If the API request fails.
        """
        with httpx.Client(timeout=self.timeout, verify=_get_ssl_context()) as client:
            try:
                response = client.post(
                    DOCUMENT_LISTS_URL,
                    headers=self.headers,
                    json={},
                )
                response.raise_for_status()

            except httpx.HTTPStatusError as e:
                body_preview = e.response.text[:200] if e.response.text else ""
                raise APIError(
                    f"API request failed: status={e.response.status_code}, body={body_preview}"
                ) from e

            except httpx.RequestError as e:
                raise APIError(f"API request failed: {e}") from e

            # Parse response
            try:
                data = response.json()
                lists_response = DocumentListsResponse.model_validate(data)
            except Exception as e:
                raise APIError(f"Failed to parse document lists response: {e}") from e

            return lists_response.lists

    def get_doc_folder_mapping(self) -> tuple[dict[str, str], dict[str, list[str]]]:
        """Get folder information and document-to-folder mapping from API.

        Returns:
            Tuple of:
                - folders: dict mapping folder_id -> folder_title
                - doc_folders: dict mapping doc_id -> list of folder_titles
        """
        lists = self.get_document_lists()

        folders: dict[str, str] = {}
        doc_folders: dict[str, list[str]] = {}

        for lst in lists:
            folder_id = lst.id
            folder_title = lst.title or "Unnamed"
            folders[folder_id] = folder_title

            # Map each document to this folder
            for doc in lst.documents:
                doc_id = doc.get("id", "")
                if doc_id:
                    if doc_id not in doc_folders:
                        doc_folders[doc_id] = []
                    doc_folders[doc_id].append(folder_title)

        return folders, doc_folders
