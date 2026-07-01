"""Master inventory aggregation logic"""

from typing import List, Dict, Optional, Tuple, Callable, Any
from src.models import Project, MasterItem, MasterItemMech, MasterItemPcb, MasterItemPrn3D


class Aggregator:
    """Aggregates BOMs from all projects into master inventory"""

    def __init__(self, company_prefix: str):
        self.company_prefix = company_prefix.upper()

    # ── Electrical ──────────────────────────────────────────────

    def aggregate(
        self,
        projects: List[Project],
        existing_items: Optional[List[MasterItem]] = None,
        next_id_fn: Optional[Callable[[], int]] = None,
    ) -> List[MasterItem]:
        """Aggregate all project electrical BOMs into master inventory."""
        items_map: Dict[str, MasterItem] = {}

        stock_levels = {}
        existing_ids = {}
        if existing_items:
            for item in existing_items:
                key = f"{item.value}|{item.footprint}"
                stock_levels[key] = item.current_stock
                existing_ids[key] = item.internal_id

        for project in projects:
            for bom_row in project.bom:
                if not bom_row.is_active():
                    continue

                key = bom_row.get_aggregation_key()

                if key not in items_map:
                    internal_id = existing_ids.get(key)
                    if not internal_id:
                        id_num = next_id_fn() if next_id_fn else 0
                        internal_id = f"{self.company_prefix}-ELE-{id_num:05d}"

                    items_map[key] = MasterItem(
                        internal_id=internal_id,
                        value=bom_row.value,
                        footprint=bom_row.footprint,
                        total_required=0,
                        current_stock=stock_levels.get(key, 0),
                        used_in_projects=[],
                        associated_mpns=[],
                    )

                items_map[key].total_required += bom_row.qty

                if project.name not in items_map[key].used_in_projects:
                    items_map[key].used_in_projects.append(project.name)

                if (
                    bom_row.manufacturer_part_number
                    and bom_row.manufacturer_part_number
                    not in items_map[key].associated_mpns
                ):
                    items_map[key].associated_mpns.append(
                        bom_row.manufacturer_part_number
                    )

        items = list(items_map.values())
        # Sort by footprint first, then value
        items.sort(key=lambda x: (x.footprint.lower(), x.value.lower()))
        return items

    # ── Mechanical ──────────────────────────────────────────────

    def aggregate_mechanical(
        self,
        project_rows: List[Tuple[str, dict]],
        existing_items: Optional[List[MasterItemMech]] = None,
        next_id_fn: Optional[Callable[[], int]] = None,
    ) -> List[MasterItemMech]:
        """Aggregate mechanical BOM rows across projects."""
        items_map: Dict[str, MasterItemMech] = {}

        stock_levels = {}
        existing_ids = {}
        if existing_items:
            for item in existing_items:
                key = item.get_aggregation_key()
                stock_levels[key] = item.current_stock
                existing_ids[key] = item.internal_id

        for project_name, row in project_rows:
            key = f"{row.get('part_name', '')}|{row.get('value', '')}"
            if not key.strip("|"):
                continue

            if key not in items_map:
                internal_id = existing_ids.get(key)
                if not internal_id:
                    id_num = next_id_fn() if next_id_fn else 0
                    internal_id = f"{self.company_prefix}-MEC-{id_num:05d}"

                items_map[key] = MasterItemMech(
                    internal_id=internal_id,
                    part_name=row.get("part_name", ""),
                    value=row.get("value", ""),
                    total_required=0,
                    current_stock=stock_levels.get(key, 0),
                    used_in_projects=[],
                )

            qty = row.get("quantity", 0)
            if isinstance(qty, (int, float)):
                items_map[key].total_required += int(qty)

            if project_name not in items_map[key].used_in_projects:
                items_map[key].used_in_projects.append(project_name)

        items = list(items_map.values())
        items.sort(key=lambda x: (x.part_name.lower(), x.value.lower()))
        return items

    # ── PCB ─────────────────────────────────────────────────────

    def aggregate_pcb(
        self,
        project_rows: List[Tuple[str, dict]],
        existing_items: Optional[List[MasterItemPcb]] = None,
        next_id_fn: Optional[Callable[[], int]] = None,
    ) -> List[MasterItemPcb]:
        """Aggregate PCB BOM rows across projects."""
        items_map: Dict[str, MasterItemPcb] = {}

        stock_levels = {}
        existing_ids = {}
        if existing_items:
            for item in existing_items:
                key = item.get_aggregation_key()
                stock_levels[key] = item.current_stock
                existing_ids[key] = item.internal_id

        for project_name, row in project_rows:
            key = row.get("board_name", "").strip()
            if not key:
                continue

            if key not in items_map:
                internal_id = existing_ids.get(key)
                if not internal_id:
                    id_num = next_id_fn() if next_id_fn else 0
                    internal_id = f"{self.company_prefix}-PCB-{id_num:05d}"

                items_map[key] = MasterItemPcb(
                    internal_id=internal_id,
                    board_name=key,
                    total_required=0,
                    current_stock=stock_levels.get(key, 0),
                    used_in_projects=[],
                )

            qty = row.get("quantity", 0)
            if isinstance(qty, (int, float)):
                items_map[key].total_required += int(qty)

            if project_name not in items_map[key].used_in_projects:
                items_map[key].used_in_projects.append(project_name)

        items = list(items_map.values())
        items.sort(key=lambda x: x.board_name.lower())
        return items

    # ── 3D Print ────────────────────────────────────────────────

    def aggregate_print3d(
        self,
        project_rows: List[Tuple[str, dict]],
        existing_items: Optional[List[MasterItemPrn3D]] = None,
        next_id_fn: Optional[Callable[[], int]] = None,
    ) -> List[MasterItemPrn3D]:
        """Aggregate 3D-print BOM rows across projects."""
        items_map: Dict[str, MasterItemPrn3D] = {}

        stock_levels = {}
        existing_ids = {}
        if existing_items:
            for item in existing_items:
                key = item.get_aggregation_key()
                stock_levels[key] = item.current_stock
                existing_ids[key] = item.internal_id

        for project_name, row in project_rows:
            key = row.get("part_name", "").strip()
            if not key:
                continue

            if key not in items_map:
                internal_id = existing_ids.get(key)
                if not internal_id:
                    id_num = next_id_fn() if next_id_fn else 0
                    internal_id = f"{self.company_prefix}-PRN-{id_num:05d}"

                items_map[key] = MasterItemPrn3D(
                    internal_id=internal_id,
                    part_name=key,
                    material=row.get("material", ""),
                    total_required=0,
                    current_stock=stock_levels.get(key, 0),
                    used_in_projects=[],
                )

            qty = row.get("quantity", 0)
            if isinstance(qty, (int, float)):
                items_map[key].total_required += int(qty)

            if project_name not in items_map[key].used_in_projects:
                items_map[key].used_in_projects.append(project_name)

        items = list(items_map.values())
        items.sort(key=lambda x: x.part_name.lower())
        return items