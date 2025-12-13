"""Granola API client."""

import httpx

from granola.api.models import Document, GranolaResponse

# Constants matching the Go implementation
USER_AGENT = "Granola/5.354.0"
X_CLIENT_VERSION = "5.354.0"
API_URL = "https://api.granola.ai/v2/get-documents"


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

        with httpx.Client(timeout=self.timeout) as client:
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
