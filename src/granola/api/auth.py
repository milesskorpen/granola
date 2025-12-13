"""Token extraction from supabase.json."""

import json
from pathlib import Path


class AuthError(Exception):
    """Raised when authentication fails."""

    pass


def get_access_token(supabase_path: Path) -> str:
    """Extract access token from supabase.json.

    The supabase.json file contains a nested JSON structure:
    {
        "workos_tokens": "<json-string containing access_token>"
    }

    Args:
        supabase_path: Path to the supabase.json file.

    Returns:
        The access token string.

    Raises:
        AuthError: If the token cannot be extracted.
        FileNotFoundError: If the file doesn't exist.
    """
    try:
        content = supabase_path.read_text()
        wrapper = json.loads(content)

        # workos_tokens is itself a JSON string that needs to be parsed
        tokens_str = wrapper.get("workos_tokens", "")
        if not tokens_str:
            raise AuthError("workos_tokens not found in supabase.json")

        tokens = json.loads(tokens_str)
        token = tokens.get("access_token", "").strip()

        if not token:
            raise AuthError("access_token not found in workos_tokens")

        return token

    except json.JSONDecodeError as e:
        raise AuthError(f"Failed to parse supabase.json: {e}") from e
    except KeyError as e:
        raise AuthError(f"Missing key in supabase.json: {e}") from e
