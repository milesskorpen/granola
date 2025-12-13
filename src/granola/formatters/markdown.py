"""Document to Markdown conversion with YAML frontmatter."""

import yaml

from granola.api.models import Document
from granola.prosemirror.converter import to_markdown


def to_markdown_file(doc: Document) -> str:
    """Convert a Document to Markdown format with YAML frontmatter.

    Content priority:
    1. Notes (new API structure)
    2. LastViewedPanel.Content (ProseMirror)
    3. LastViewedPanel.OriginalContent (HTML)
    4. Content (raw)

    Args:
        doc: The Document to convert.

    Returns:
        Markdown string with YAML frontmatter.
    """
    # Build metadata
    metadata: dict[str, str | list[str]] = {
        "id": doc.id,
        "created": doc.created_at,
        "updated": doc.updated_at,
    }
    if doc.tags:
        metadata["tags"] = doc.tags

    # Build output
    parts: list[str] = [
        "---",
        yaml.dump(metadata, default_flow_style=False, allow_unicode=True).strip(),
        "---",
        "",
    ]

    # Add title as heading
    if doc.title:
        parts.extend([f"# {doc.title}", ""])

    # Get content with priority fallback
    content = ""

    # Priority 1: Notes (new API)
    if doc.notes:
        content = to_markdown(doc.notes).strip()

    # Priority 2: LastViewedPanel.Content (ProseMirror)
    if not content and doc.last_viewed_panel and doc.last_viewed_panel.content:
        content = to_markdown(doc.last_viewed_panel.content).strip()

    # Priority 3: LastViewedPanel.OriginalContent (HTML)
    if not content and doc.last_viewed_panel and doc.last_viewed_panel.original_content:
        content = doc.last_viewed_panel.original_content

    # Priority 4: Content (raw)
    if not content and doc.content:
        content = doc.content

    if content:
        parts.append(content)
        if not content.endswith("\n"):
            parts.append("")

    return "\n".join(parts)
