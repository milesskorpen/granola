"""HTTP client for sending webhooks."""

import json
import logging
import ssl
from urllib.parse import urlencode

import certifi
import httpx

from granola.webhooks.models import WebhookConfig, WebhookResult

WEBHOOK_TIMEOUT = 10  # seconds


def _get_ssl_context() -> ssl.SSLContext:
    """Create an SSL context using certifi's CA bundle."""
    return ssl.create_default_context(cafile=certifi.where())


class WebhookClient:
    """HTTP client for sending webhook requests."""

    def __init__(self, logger: logging.Logger | None = None):
        """Initialize the webhook client.

        Args:
            logger: Optional logger for debug output.
        """
        self.logger = logger or logging.getLogger(__name__)

    def send(self, payload: dict, config: WebhookConfig) -> WebhookResult:
        """Send a webhook request.

        Args:
            payload: The payload to send.
            config: Webhook configuration.

        Returns:
            WebhookResult indicating success or failure.
        """
        if not config.is_valid():
            return WebhookResult(
                success=False,
                webhook_name=config.name,
                error_message="Invalid webhook configuration",
            )

        try:
            with httpx.Client(timeout=WEBHOOK_TIMEOUT, verify=_get_ssl_context()) as client:
                if config.method == "GET":
                    # For GET, send metadata only as query params (skip large content)
                    params = self._flatten_for_query(payload)
                    response = client.get(config.url, params=params)
                else:
                    # For POST, PUT, PATCH - send full payload as JSON
                    response = client.request(
                        method=config.method,
                        url=config.url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )

                response.raise_for_status()

                self.logger.debug(
                    f"Webhook '{config.name}' sent successfully: {response.status_code}"
                )
                return WebhookResult(
                    success=True,
                    webhook_name=config.name,
                    status_code=response.status_code,
                )

        except httpx.TimeoutException:
            error_msg = f"Webhook '{config.name}' timed out after {WEBHOOK_TIMEOUT}s"
            self.logger.warning(error_msg)
            return WebhookResult(
                success=False,
                webhook_name=config.name,
                error_message=error_msg,
            )
        except httpx.HTTPStatusError as e:
            error_msg = f"Webhook '{config.name}' failed: HTTP {e.response.status_code}"
            self.logger.warning(error_msg)
            return WebhookResult(
                success=False,
                webhook_name=config.name,
                status_code=e.response.status_code,
                error_message=error_msg,
            )
        except httpx.RequestError as e:
            error_msg = f"Webhook '{config.name}' failed: {e}"
            self.logger.warning(error_msg)
            return WebhookResult(
                success=False,
                webhook_name=config.name,
                error_message=error_msg,
            )

    def _flatten_for_query(self, payload: dict, prefix: str = "") -> dict[str, str]:
        """Flatten a nested dict for use as query parameters.

        For GET requests, we only include metadata (skip markdown_content).
        """
        params = {}
        for key, value in payload.items():
            full_key = f"{prefix}.{key}" if prefix else key

            # Skip large content fields for GET requests
            if key == "markdown_content":
                continue

            if isinstance(value, dict):
                params.update(self._flatten_for_query(value, full_key))
            elif isinstance(value, list):
                params[full_key] = json.dumps(value)
            elif isinstance(value, bool):
                params[full_key] = "true" if value else "false"
            elif value is not None:
                params[full_key] = str(value)

        return params
