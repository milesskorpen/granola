"""ProseMirror document to Markdown/plain text conversion."""

import re
from typing import Optional

from granola.api.models import ProseMirrorDoc, ProseMirrorNode


def to_markdown(doc: Optional[ProseMirrorDoc]) -> str:
    """Convert a ProseMirror document to Markdown format.

    Args:
        doc: The ProseMirror document to convert.

    Returns:
        Markdown string representation.
    """
    if doc is None or doc.type != "doc" or not doc.content:
        return ""

    output: list[str] = []
    for node in doc.content:
        output.append(_process_node(node, indent_level=0, is_top_level=True))

    result = "".join(output)

    # Replace multiple consecutive newlines with double newlines
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip() + "\n"


def _process_node(node: ProseMirrorNode, indent_level: int, is_top_level: bool) -> str:
    """Recursively process a ProseMirror node and convert it to Markdown.

    Args:
        node: The node to process.
        indent_level: Current indentation level for nested lists.
        is_top_level: Whether this is a top-level node.

    Returns:
        Markdown string for this node.
    """
    text_content = ""

    # Process child content
    if node.content:
        if node.type == "bulletList":
            items = [_process_node(child, indent_level, False) for child in node.content]
            text_content = "".join(items)
        elif node.type == "listItem":
            child_contents = []
            for child in node.content:
                if child.type == "bulletList":
                    child_contents.append(_process_node(child, indent_level + 1, False))
                else:
                    child_contents.append(_process_node(child, indent_level, False))
            text_content = "".join(child_contents)
        else:
            contents = [_process_node(child, indent_level, False) for child in node.content]
            text_content = "".join(contents)
    elif node.text:
        text_content = node.text

    # Format based on node type
    if node.type == "heading":
        level = 1
        if node.attrs and "level" in node.attrs:
            lvl = node.attrs["level"]
            if isinstance(lvl, (int, float)):
                level = int(lvl)

        suffix = "\n\n" if is_top_level else "\n"
        return "#" * level + " " + text_content.strip() + suffix

    elif node.type == "paragraph":
        suffix = "\n\n" if is_top_level else ""
        return text_content + suffix

    elif node.type == "bulletList":
        if not node.content:
            return ""

        items: list[str] = []
        for item_node in node.content:
            if item_node.type == "listItem":
                child_contents: list[str] = []
                nested_lists: list[str] = []

                for child in item_node.content:
                    if child.type == "bulletList":
                        nested_lists.append("\n" + _process_node(child, indent_level + 1, False))
                    else:
                        child_contents.append(_process_node(child, indent_level, False))

                # Find the first non-bulletList content as the main item text
                first_text = ""
                for c in child_contents:
                    if not c.startswith("\n"):
                        first_text = c
                        break

                indent = "\t" * indent_level
                rest = "".join(nested_lists)
                items.append(f"{indent}- {first_text.strip()}{rest}")

        suffix = "\n\n" if is_top_level else ""
        return "\n".join(items) + suffix

    elif node.type == "text":
        return node.text

    else:
        return text_content


def to_plain_text(doc: Optional[ProseMirrorDoc]) -> str:
    """Convert a ProseMirror document to plain text (no formatting).

    Args:
        doc: The ProseMirror document to convert.

    Returns:
        Plain text string representation.
    """
    if doc is None or doc.type != "doc" or not doc.content:
        return ""

    output: list[str] = []
    for node in doc.content:
        text = _extract_text(node)
        if text:
            output.append(text)

    return "\n\n".join(output).strip()


def _extract_text(node: ProseMirrorNode) -> str:
    """Recursively extract plain text from a ProseMirror node.

    Args:
        node: The node to extract text from.

    Returns:
        Plain text content.
    """
    if node.text:
        return node.text

    if not node.content:
        return ""

    texts: list[str] = []
    for child in node.content:
        text = _extract_text(child)
        if text:
            texts.append(text)

    # Join with space for inline content, newline for block content
    separator = " "
    if node.type in ("paragraph", "heading", "listItem"):
        separator = "\n"

    return separator.join(texts)
