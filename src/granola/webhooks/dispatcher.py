"""Webhook dispatcher for sending events to multiple endpoints."""

import logging

from granola.webhooks.client import WebhookClient
from granola.webhooks.history import add_history_entry
from granola.webhooks.models import (
    WebhookConfig,
    WebhookHistoryEntry,
    WebhookPayload,
    WebhookResult,
)


class WebhookDispatcher:
    """Dispatches webhook events to multiple configured endpoints."""

    def __init__(
        self,
        configs: list[dict],
        logger: logging.Logger | None = None,
        record_history: bool = True,
    ):
        """Initialize the dispatcher.

        Args:
            configs: List of webhook configuration dictionaries.
            logger: Optional logger for debug output.
            record_history: Whether to record webhook calls in history.
        """
        self.logger = logger or logging.getLogger(__name__)
        self.client = WebhookClient(logger=self.logger)
        self.configs = [WebhookConfig.from_dict(c) for c in configs]
        self.record_history = record_history

    def dispatch(self, payload: WebhookPayload) -> list[WebhookResult]:
        """Send a webhook payload to all enabled endpoints that match the document's folders.

        Args:
            payload: The webhook payload to send.

        Returns:
            List of results from each webhook call.
        """
        results: list[WebhookResult] = []
        base_payload_dict = payload.to_dict()
        doc_folders = payload.document.folders

        for config in self.configs:
            if not config.enabled:
                self.logger.debug(f"Skipping disabled webhook: {config.name}")
                continue

            if not config.is_valid():
                self.logger.warning(f"Skipping invalid webhook config: {config.name}")
                continue

            # Check folder filter
            if not config.matches_folder(doc_folders):
                self.logger.debug(
                    f"Skipping webhook '{config.name}' - folder filters {config.folders} "
                    f"don't match document folders {doc_folders}"
                )
                continue

            # Add the webhook's folder filters to the payload
            payload_dict = base_payload_dict.copy()
            payload_dict["document"] = base_payload_dict["document"].copy()
            payload_dict["document"]["webhook_folder_filters"] = config.folders

            self.logger.debug(f"Sending webhook to '{config.name}': {config.url}")
            result = self.client.send(payload_dict, config)
            results.append(result)

            # Record in history
            if self.record_history:
                try:
                    entry = WebhookHistoryEntry.create(config, payload_dict, result)
                    add_history_entry(entry)
                except Exception as e:
                    self.logger.warning(f"Failed to record webhook history: {e}")

        return results

    def dispatch_test(self, payload: WebhookPayload, webhook_index: int) -> WebhookResult | None:
        """Send a test webhook to a specific endpoint (ignores folder filter).

        Args:
            payload: The webhook payload to send.
            webhook_index: Index of the webhook config to test.

        Returns:
            Result of the webhook call, or None if index is invalid.
        """
        if webhook_index < 0 or webhook_index >= len(self.configs):
            return None

        config = self.configs[webhook_index]
        if not config.is_valid():
            return WebhookResult(
                success=False,
                webhook_name=config.name,
                error_message="Invalid webhook configuration",
            )

        # Add the webhook's folder filters to the payload
        payload_dict = payload.to_dict()
        payload_dict["document"] = payload_dict["document"].copy()
        payload_dict["document"]["webhook_folder_filters"] = config.folders

        self.logger.debug(f"Sending test webhook to '{config.name}': {config.url}")
        result = self.client.send(payload_dict, config)

        # Record in history
        if self.record_history:
            try:
                entry = WebhookHistoryEntry.create(config, payload_dict, result)
                add_history_entry(entry)
            except Exception as e:
                self.logger.warning(f"Failed to record webhook history: {e}")

        return result

    def replay(self, history_entry: WebhookHistoryEntry) -> WebhookResult:
        """Replay a historical webhook call.

        Args:
            history_entry: The history entry to replay.

        Returns:
            Result of the webhook call.
        """
        # Create a temporary config from the history entry
        config = WebhookConfig(
            name=history_entry.webhook_name,
            url=history_entry.url,
            method=history_entry.method,
            enabled=True,
        )

        self.logger.debug(f"Replaying webhook '{config.name}': {config.url}")
        result = self.client.send(history_entry.payload, config)

        # Record the replay in history
        if self.record_history:
            try:
                entry = WebhookHistoryEntry.create(config, history_entry.payload, result)
                add_history_entry(entry)
            except Exception as e:
                self.logger.warning(f"Failed to record webhook history: {e}")

        return result

    def get_summary(self, results: list[WebhookResult]) -> str:
        """Generate a summary of webhook results.

        Args:
            results: List of webhook results.

        Returns:
            Human-readable summary string.
        """
        if not results:
            return "No webhooks configured"

        sent = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)

        if failed == 0:
            return f"Webhooks: {sent} sent"
        else:
            return f"Webhooks: {sent} sent, {failed} failed"
