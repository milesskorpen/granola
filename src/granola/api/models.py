"""Pydantic models for Granola API responses."""

from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class ProseMirrorNode(BaseModel):
    """A node in the ProseMirror document structure."""

    type: str
    content: list[ProseMirrorNode] = Field(default_factory=list)
    text: str = ""
    attrs: dict[str, Any] = Field(default_factory=dict)


class ProseMirrorDoc(BaseModel):
    """ProseMirror document structure."""

    type: str = "doc"
    content: list[ProseMirrorNode] = Field(default_factory=list)


class LastViewedPanel(BaseModel):
    """Contains ProseMirror content and metadata for a document panel."""

    document_id: str
    id: str
    title: str = ""
    content: Optional[ProseMirrorDoc] = None
    original_content: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    content_updated_at: Optional[str] = None
    deleted_at: Optional[str] = None
    template_slug: Optional[str] = None
    last_viewed_at: Optional[str] = None
    affinity_note_id: Optional[str] = None
    suggested_questions: Any = None
    generated_lines: Optional[list[Any]] = None

    @field_validator("content", mode="before")
    @classmethod
    def parse_content(cls, v: Any) -> Optional[ProseMirrorDoc]:
        """Handle content as either JSON object or double-encoded JSON string."""
        if v is None:
            return None

        # If it's already a dict (JSON object), parse directly
        if isinstance(v, dict):
            return ProseMirrorDoc.model_validate(v)

        # If it's a string, check if it's HTML or JSON
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None

            # HTML content starts with '<' - skip it (use original_content instead)
            if v.startswith("<"):
                return None

            # Try to parse as JSON string (double-encoded)
            try:
                parsed = json.loads(v)
                if isinstance(parsed, dict):
                    return ProseMirrorDoc.model_validate(parsed)
            except (json.JSONDecodeError, ValueError):
                return None

        return None


class Document(BaseModel):
    """A meeting document from the Granola API."""

    id: str
    title: Optional[str] = None
    content: Optional[str] = None
    created_at: str
    updated_at: str
    tags: Optional[list[str]] = None
    last_viewed_panel: Optional[LastViewedPanel] = None
    notes: Optional[ProseMirrorDoc] = None
    notes_plain: Optional[str] = None

    @field_validator("notes", mode="before")
    @classmethod
    def parse_notes(cls, v: Any) -> Optional[ProseMirrorDoc]:
        """Handle notes as either JSON object or double-encoded JSON string."""
        if v is None:
            return None

        # If it's already a dict (JSON object), parse directly
        if isinstance(v, dict):
            return ProseMirrorDoc.model_validate(v)

        # If it's a string, try to parse as JSON
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None

            try:
                parsed = json.loads(v)
                if isinstance(parsed, dict):
                    return ProseMirrorDoc.model_validate(parsed)
            except (json.JSONDecodeError, ValueError):
                return None

        return None


class GranolaResponse(BaseModel):
    """API response containing documents."""

    docs: list[Document] = Field(default_factory=list)
