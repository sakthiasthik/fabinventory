from __future__ import annotations

from pathlib import Path
from typing import List

from .models import BOMRow


def parse_bom(file_path: Path) -> List[BOMRow]:
    """Parse a CSV/Excel BOM file into a list of :class:`BOMRow`.

    This is a placeholder; real parsing logic will be added when the upload
    endpoint is implemented.
    """
    raise NotImplementedError("BOM parsing not yet implemented")
