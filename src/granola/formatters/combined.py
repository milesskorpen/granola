"""Combined notes and transcript formatting."""

from datetime import datetime

from granola.cache.reader import TranscriptSegment


def format_combined(
    title: str,
    doc_id: str,
    created_at: str,
    updated_at: str,
    notes_content: str,
    segments: list[TranscriptSegment],
    folders: list[str],
) -> str:
    """Format notes and transcript into a single text file.

    Args:
        title: Document title.
        doc_id: Document ID.
        created_at: Creation timestamp.
        updated_at: Update timestamp.
        notes_content: Plain text notes content.
        segments: Transcript segments.
        folders: List of folder names.

    Returns:
        Combined formatted string.
    """
    lines: list[str] = []

    # Header
    lines.append("=" * 80)

    if title:
        lines.append(title)

    lines.append(f"ID: {doc_id}")

    if created_at:
        lines.append(f"Created: {created_at}")

    if updated_at:
        lines.append(f"Updated: {updated_at}")

    if folders:
        lines.append(f"Folders: {', '.join(folders)}")

    lines.append("=" * 80)

    # Notes section
    lines.append("")
    lines.append("## Notes")
    lines.append("")

    if notes_content and notes_content.strip():
        lines.append(notes_content)
    else:
        lines.append("(No notes)")

    # Transcript section
    lines.append("")
    lines.append("=" * 80)
    lines.append("")
    lines.append("## Transcript")
    lines.append("")

    if segments:
        for segment in segments:
            timestamp = _parse_timestamp(segment.start_timestamp)
            speaker = "You" if segment.source == "microphone" else "System"
            lines.append(f"[{timestamp}] {speaker}: {segment.text}")
    else:
        lines.append("(No transcript available)")

    return "\n".join(lines)


def _parse_timestamp(timestamp: str) -> str:
    """Convert ISO 8601 timestamp to HH:MM:SS format.

    Args:
        timestamp: ISO 8601 timestamp string.

    Returns:
        Formatted time string or original on error.
    """
    try:
        ts = timestamp.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%H:%M:%S")
    except ValueError:
        return timestamp
