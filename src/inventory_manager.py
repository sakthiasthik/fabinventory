"""Inventory and order management"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from src.models import MasterItem, MasterItemMech, MasterItemPcb, MasterItemPrn3D, Order, OrderLineItem
from src.file_manager import FileManager
from src.aggregator import Aggregator


class InventoryManager:
    """Manages inventory and purchase orders"""

    def __init__(self, file_manager: FileManager, aggregator: Aggregator):
        self.file_manager = file_manager
        self.aggregator = aggregator

        # Electronics
        self.inventory: List[MasterItem] = []

        # Non-electrical
        self.mech_inventory: List[MasterItemMech] = []
        self.pcb_inventory: List[MasterItemPcb] = []
        self.print3d_inventory: List[MasterItemPrn3D] = []

        self._load_inventory()

    # ── Load & initialise ───────────────────────────────────────

    def _load_inventory(self):
        self.inventory = self.file_manager.load_master_inventory()
        self.mech_inventory = self.file_manager.load_mechanical_inventory()
        self.pcb_inventory = self.file_manager.load_pcb_inventory()
        self.print3d_inventory = self.file_manager.load_print3d_inventory()

    # ── Electrical ──────────────────────────────────────────────

    def update_inventory(self, projects) -> List[MasterItem]:
        existing_items = self.inventory if self.inventory else None
        self.inventory = self.aggregator.aggregate(
            projects, existing_items, self.file_manager.get_next_id
        )
        self.file_manager.save_master_inventory(self.inventory)
        return self.inventory

    def update_stock(self, internal_id: str, new_stock: int) -> Optional[MasterItem]:
        for item in self.inventory:
            if item.internal_id == internal_id:
                item.current_stock = new_stock
                item.last_updated = datetime.now().isoformat()
                self.file_manager.save_master_inventory(self.inventory)
                return item
        return None

    def get_inventory(self) -> List[MasterItem]:
        return self.inventory

    def get_items_to_order(self) -> List[MasterItem]:
        return [item for item in self.inventory if item.to_order > 0]

    # ── Non‑electrical update helpers ───────────────────────────

    def update_non_elec_inventory(self, projects):
        self._update_mechanical(projects)
        self._update_pcb(projects)
        self._update_print3d(projects)

    # ── Mechanical ──────────────────────────────────────────────

    def _update_mechanical(self, projects):
        from src.bom_parser import BOMParser

        all_rows = []
        for project in projects:
            if not project.mechanical_bom:
                continue
            project_dir = self.file_manager._project_dir(project.name)
            full_path = project_dir / project.mechanical_bom
            if not full_path.exists():
                continue
            try:
                rows = BOMParser.parse_file(str(full_path), bom_type="mechanical")
                for row in rows:
                    all_rows.append((project.name, row))
            except Exception as e:
                print(f"Error parsing mechanical BOM for {project.name}: {e}")

        self.mech_inventory = self.aggregator.aggregate_mechanical(
            all_rows, self.mech_inventory, self.file_manager.get_next_id
        )
        self.file_manager.save_mechanical_inventory(self.mech_inventory)

    def update_mechanical_stock(
        self, internal_id: str, new_stock: int
    ) -> Optional[MasterItemMech]:
        for item in self.mech_inventory:
            if item.internal_id == internal_id:
                item.current_stock = new_stock
                item.last_updated = datetime.now().isoformat()
                self.file_manager.save_mechanical_inventory(self.mech_inventory)
                return item
        return None

    # ── PCB ─────────────────────────────────────────────────────

    def _update_pcb(self, projects):
        """Build PCB inventory from projects that have Gerber files.
        Each project with Gerber data counts as one board entry.
        If a PCB BOM is also uploaded, those rows are included too."""
        from src.bom_parser import BOMParser

        all_rows = []
        for project in projects:
            board_found = False

            # Check for Gerber files — each project with Gerbers = 1 board
            if project.pcb_gerber_folder or project.pcb_gerber_zip:
                board_name = project.name  # default

                # Try to get a meaningful name from the Gerber path
                path = (project.pcb_gerber_folder or project.pcb_gerber_zip or "")
                parts = path.replace("\\", "/").rstrip("/").split("/")
                # Skip generic folder names like "gerbers", "extracted"
                skip = {"gerbers", "extracted"}
                meaningful = [p for p in parts if p.lower() not in skip]
                if meaningful:
                    # Take the last meaningful part, clean it up
                    name = meaningful[-1]
                    # Strip common suffixes
                    for suffix in ("Completed", "_gerber_x2", "_gerber", "-gerber"):
                        if name.endswith(suffix):
                            name = name[:-len(suffix)]
                    board_name = name

                all_rows.append((project.name, {
                    "board_name": board_name,
                    "quantity": 1,
                }))
                board_found = True

            # Also check for PCB BOM (additional/alternative)
            if project.pcb_bom:
                project_dir = self.file_manager._project_dir(project.name)
                full_path = project_dir / project.pcb_bom
                if full_path.exists():
                    try:
                        rows = BOMParser.parse_file(str(full_path), bom_type="pcb")
                        for row in rows:
                            all_rows.append((project.name, row))
                        board_found = True
                    except Exception as e:
                        print(f"Error parsing PCB BOM for {project.name}: {e}")

        self.pcb_inventory = self.aggregator.aggregate_pcb(
            all_rows, self.pcb_inventory, self.file_manager.get_next_id
        )
        self.file_manager.save_pcb_inventory(self.pcb_inventory)

    def update_pcb_stock(
        self, internal_id: str, new_stock: int
    ) -> Optional[MasterItemPcb]:
        for item in self.pcb_inventory:
            if item.internal_id == internal_id:
                item.current_stock = new_stock
                item.last_updated = datetime.now().isoformat()
                self.file_manager.save_pcb_inventory(self.pcb_inventory)
                return item
        return None

    # ── 3D Print ────────────────────────────────────────────────

    def _update_print3d(self, projects):
        from src.bom_parser import BOMParser

        all_rows = []
        for project in projects:
            if not project.print3d_bom:
                continue
            project_dir = self.file_manager._project_dir(project.name)
            full_path = project_dir / project.print3d_bom
            if not full_path.exists():
                continue
            try:
                rows = BOMParser.parse_file(str(full_path), bom_type="3dprint")
                for row in rows:
                    all_rows.append((project.name, row))
            except Exception as e:
                print(f"Error parsing 3D print BOM for {project.name}: {e}")

        self.print3d_inventory = self.aggregator.aggregate_print3d(
            all_rows, self.print3d_inventory, self.file_manager.get_next_id
        )
        self.file_manager.save_print3d_inventory(self.print3d_inventory)

    def update_print3d_stock(
        self, internal_id: str, new_stock: int
    ) -> Optional[MasterItemPrn3D]:
        for item in self.print3d_inventory:
            if item.internal_id == internal_id:
                item.current_stock = new_stock
                item.last_updated = datetime.now().isoformat()
                self.file_manager.save_print3d_inventory(self.print3d_inventory)
                return item
        return None

    # ── Common ──────────────────────────────────────────────────

    def find_item(self, internal_id: str) -> Optional[MasterItem]:
        """Find an electronics inventory item by its internal ID."""
        for item in self.inventory:
            if item.internal_id == internal_id:
                return item
        return None

    # ── Orders ──────────────────────────────────────────────────

    def create_order(self, supplier: str, items: List[Dict[str, Any]], notes: str = "") -> Optional[Order]:
        existing_orders = self.file_manager.list_orders()
        max_num = 0
        for o in existing_orders:
            try:
                num = int(o.order_id.split('-')[-1])
                max_num = max(max_num, num)
            except (ValueError, IndexError):
                pass
        order_num = max_num + 1
        order_id = f"PO-{datetime.now().strftime('%Y%m')}-{order_num:03d}"

        line_items = []
        for item_data in items:
            line_item = OrderLineItem(
                internal_id=item_data['internal_id'],
                qty_ordered=item_data['qty'],
                unit_price=item_data.get('unit_price'),
                manufacturer_part_number=item_data.get('mpn')
            )
            line_items.append(line_item)

        order = Order(
            order_id=order_id,
            supplier=supplier,
            line_items=line_items,
            notes=notes
        )

        if self.file_manager.save_order(order):
            return order
        return None

    def receive_order(self, order_id: str) -> bool:
        order = self.file_manager.load_order(order_id)
        if not order:
            return False

        if not order.transition_to(order.STATUS_RECEIVED):
            return False

        for line_item in order.line_items:
            for inventory_item in self.inventory:
                if inventory_item.internal_id == line_item.internal_id:
                    inventory_item.current_stock += line_item.qty_ordered
                    inventory_item.last_updated = datetime.now().isoformat()
                    break

        self.file_manager.save_master_inventory(self.inventory)
        self.file_manager.save_order(order)
        return True

    def get_order_summary(self) -> Dict[str, Any]:
        orders = self.file_manager.list_orders()

        pending_orders = [o for o in orders if o.status == "pending"]
        received_orders = [o for o in orders if o.status == "received"]

        total_pending_items = sum(o.total_items for o in pending_orders)
        total_received_items = sum(o.total_items for o in received_orders)

        supplier_summary = {}
        for order in pending_orders:
            if order.supplier not in supplier_summary:
                supplier_summary[order.supplier] = {
                    'orders': [],
                    'total_items': 0,
                    'estimated_cost': 0
                }
            supplier_summary[order.supplier]['orders'].append(order)
            supplier_summary[order.supplier]['total_items'] += order.total_items
            if order.estimated_cost:
                supplier_summary[order.supplier]['estimated_cost'] += order.estimated_cost

        return {
            'total_orders': len(orders),
            'pending_orders': len(pending_orders),
            'received_orders': len(received_orders),
            'total_pending_items': total_pending_items,
            'total_received_items': total_received_items,
            'supplier_summary': supplier_summary,
            'pending_orders_list': pending_orders,
            'received_orders_list': received_orders
        }

    def get_inventory_summary(self) -> Dict[str, Any]:
        items_to_order = self.get_items_to_order()

        footprint_counts = {}
        for item in self.inventory:
            if item.footprint not in footprint_counts:
                footprint_counts[item.footprint] = 0
            footprint_counts[item.footprint] += 1

        return {
            'total_components': len(self.inventory),
            'total_required': sum(item.total_required for item in self.inventory),
            'total_stock': sum(item.current_stock for item in self.inventory),
            'total_to_order': sum(item.to_order for item in self.inventory),
            'components_to_order': len(items_to_order),
            'footprint_distribution': footprint_counts
        }
