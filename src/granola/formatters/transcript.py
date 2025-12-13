"""Transcript formatting with timestamps and speaker identification."""

from datetime import datetime

from granola.cache.reader import CacheDocument, TranscriptSegment


def format_transcript(doc: CacheDocument, segments: list[TranscriptSegment]) -> str:
    """Format transcript segments into a readable text format.

    Args:
        doc: The document metadata.
        segments: List of transcript segments.

    Returns:
        Formatted transcript string.
    """
    if not segments:
        return ""

    lines: list[str] = []

    # Header
    lines.append("=" * 80)

    if doc.title:
        lines.append(doc.title)

    lines.append(f"ID: {doc.id}")

    if doc.created_at:
        lines.append(f"Created: {doc.created_at}")

    if doc.updated_at:
        lines.append(f"Updated: {doc.updated_at}")

    lines.append(f"Segments: {len(segments)}")
    lines.append("=" * 80)
    lines.append("")

    # Transcript segments
    for segment in segments:
        timestamp = _parse_timestamp(segment.start_timestamp)
        speaker = "You" if segment.source == "microphone" else "System"
        lines.append(f"[{timestamp}] {speaker}: {segment.text}")

    return "\n".join(lines)


def _parse_timestamp(timestamp: str) -> str:
    """Convert ISO 8601 timestamp to HH:MM:SS format.

    Args:
        timestamp: ISO 8601 timestamp string.

    Returns:
        Formatted time string or original on error.
    """
    try:
        # Handle both 'Z' suffix and timezone offsets
        ts = timestamp.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%H:%M:%S")
    except ValueError:
        return timestamp
