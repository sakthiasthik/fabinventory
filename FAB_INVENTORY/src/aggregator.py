"""Master inventory aggregation logic"""

from typing import List, Dict, Optional
from src.models import Project, MasterItem


class Aggregator:
    """Aggregates BOMs from all projects into master inventory"""
    
    def __init__(self, company_prefix: str):
        self.company_prefix = company_prefix.upper()
        self.next_id_counter = 1
    
    def set_next_id(self, next_id: int):
        self.next_id_counter = next_id
    
    def aggregate(self, projects: List[Project], existing_items: Optional[List[MasterItem]] = None) -> List[MasterItem]:
        """Aggregate all projects into master inventory"""
        items_map: Dict[str, MasterItem] = {}
        
        # Preserve existing stock levels
        stock_levels = {}
        existing_ids = {}
        if existing_items:
            for item in existing_items:
                key = f"{item.value}|{item.footprint}"
                stock_levels[key] = item.current_stock
                existing_ids[key] = item.internal_id
        
        # Aggregate all projects
        for project in projects:
            for bom_row in project.bom:
                if not bom_row.is_active():
                    continue
                
                key = bom_row.get_aggregation_key()
                
                if key not in items_map:
                    internal_id = existing_ids.get(key)
                    if not internal_id:
                        internal_id = self._generate_internal_id()
                    
                    items_map[key] = MasterItem(
                        internal_id=internal_id,
                        value=bom_row.value,
                        footprint=bom_row.footprint,
                        total_required=0,
                        current_stock=stock_levels.get(key, 0),
                        used_in_projects=[],
                        associated_mpns=[]
                    )
                
                # Update totals
                items_map[key].total_required += bom_row.qty
                
                # Track projects
                if project.name not in items_map[key].used_in_projects:
                    items_map[key].used_in_projects.append(project.name)
                
                # Track MPNs
                if bom_row.manufacturer_part_number and bom_row.manufacturer_part_number not in items_map[key].associated_mpns:
                    items_map[key].associated_mpns.append(bom_row.manufacturer_part_number)
        
        items = list(items_map.values())
        items.sort(key=lambda x: x.internal_id)
        return items
    
    def _generate_internal_id(self) -> str:
        id_num = self.next_id_counter
        self.next_id_counter += 1
        return f"{self.company_prefix}-ELE-{id_num:05d}"