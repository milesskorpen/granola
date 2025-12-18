"""Webhook support for Granola CLI."""

from granola.webhooks.models import (
    WebhookConfig,
    WebhookHistoryEntry,
    WebhookPayload,
    WebhookResult,
)
from granola.webhooks.client import WebhookClient
from granola.webhooks.dispatcher import WebhookDispatcher
from granola.webhooks.history import (
    add_history_entry,
    clear_history,
    delete_history_entry,
    get_history_entry,
    load_history,
    save_history,
)

__all__ = [
    "WebhookConfig",
    "WebhookHistoryEntry",
    "WebhookPayload",
    "WebhookResult",
    "WebhookClient",
    "WebhookDispatcher",
    "add_history_entry",
    "clear_history",
    "delete_history_entry",
    "get_history_entry",
    "load_history",
    "save_history",
]
