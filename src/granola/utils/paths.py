"""Path resolution utilities."""

import os
from pathlib import Path
from typing import Optional, Union


def resolve_path(input_path: Optional[Union[str, Path]]) -> Optional[Path]:
    """Expand ~ and environment variables in paths.

    Args:
        input_path: A path string or Path object that may contain ~ or env vars.

    Returns:
        Resolved absolute Path, or None if input is None/empty.
    """
    if not input_path:
        return None

    path_str = str(input_path).strip()
    if not path_str:
        return None

    # Expand environment variables
    path_str = os.path.expandvars(path_str)

    # Expand ~ and resolve to absolute path
    path = Path(path_str).expanduser()

    return path.resolve()
