"""Filename sanitization utilities."""

import re
from typing import Dict

# Characters invalid in filenames on Windows/macOS/Linux
INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str, fallback: str = "untitled") -> str:
    """Remove invalid characters from filename and limit length.

    Args:
        name: The filename to sanitize.
        fallback: Fallback name if result is empty.

    Returns:
        Sanitized filename (max 100 characters).
    """
    name = name.strip()
    if not name:
        name = fallback

    # Replace invalid chars with underscore
    name = INVALID_CHARS.sub("_", name)

    # Collapse multiple consecutive underscores
    name = re.sub(r"_+", "_", name)

    # Trim underscores from ends
    name = name.strip("_")

    if not name:
        name = fallback

    # Limit to 100 characters
    if len(name) > 100:
        name = name[:100]

    return name


def make_unique(filename: str, used: Dict[str, int]) -> str:
    """Append counter if filename already used.

    Args:
        filename: The base filename.
        used: Dictionary tracking usage counts of filenames.

    Returns:
        Unique filename with _N suffix if needed.
    """
    count = used.get(filename, 0)
    if count > 0:
        return f"{filename}_{count + 1}"
    return filename
