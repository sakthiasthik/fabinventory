from __future__ import annotations

from pathlib import Path
from typing import List

from .models import Project, MasterInventory


class Aggregator:
    """Handles building the master inventory from project BOMs.

    All aggregation logic lives here so that it can be exercised independently
    of the web layer.  At the moment the implementation is a stub; later it
    will follow the rules described in the specification.
    """

    @staticmethod
    def recalc(projects_dir: Path, master_inventory_path: Path, prefix: str) -> None:
        """Recalculate the entire master inventory and write to disk.

        ``projects_dir`` is a directory containing project JSON files; each is
        loaded with :class:`~core.models.Project`.  ``master_inventory_path``
        is where the resulting inventory is written.  ``prefix`` is the
        two‑letter company prefix used for generating internal IDs.
        """
        projects: List[Project] = []
        for project_file in projects_dir.glob("*.json"):
            try:
                projects.append(Project.load(project_file))
            except Exception:  # pragma: no cover - malformed project
                continue

        # TODO: implement actual aggregation rules here
        master = MasterInventory()
        master.save(master_inventory_path)
