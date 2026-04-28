"""File system management for FabInventory"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import shutil


class FileManager:  # Make sure this is exactly "FileManager" (capital F, capital M)
    """Handles all file system operations"""
    
    def __init__(self, repo_path: str = "./fabinventory_data"):
        self.repo_path = Path(repo_path)
        self.projects_dir = self.repo_path / "projects"
        self.master_dir = self.repo_path / "master"
        self.orders_dir = self.repo_path / "orders"
        self.config_file = self.repo_path / "config.json"
        
        # Ensure directory structure exists
        self._init_structure()
    
    def _init_structure(self):
        """Create necessary directories if they don't exist"""
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.master_dir.mkdir(parents=True, exist_ok=True)
        self.orders_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize master inventory file if not exists
        master_file = self.master_dir / "electronics.json"
        if not master_file.exists():
            self._save_json(master_file, [])
        
        # Initialize next_id counter
        next_id_file = self.master_dir / "next_id.txt"
        if not next_id_file.exists():
            next_id_file.write_text("1")
    
    def _save_json(self, file_path: Path, data: Any):
        """Save data to JSON file"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _load_json(self, file_path: Path) -> Any:
        """Load data from JSON file"""
        if not file_path.exists():
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # Project operations
    def save_project(self, project) -> bool:
        """Save project to disk"""
        try:
            project_dir = self.projects_dir / project.name
            project_dir.mkdir(exist_ok=True)
            
            # Save BOM data
            bom_file = project_dir / "bom.json"
            bom_data = []
            for row in project.bom:
                bom_data.append({
                    'si_no': row.si_no,
                    'reference': row.reference,
                    'value': row.value,
                    'footprint': row.footprint,
                    'manufacturer_part_number': row.manufacturer_part_number,
                    'manufacturer_name': row.manufacturer_name,
                    'manufacturer_part_number_lcsc': row.manufacturer_part_number_lcsc,
                    'manufacturer_name_lcsc': row.manufacturer_name_lcsc,
                    'lcsc_sku': row.lcsc_sku,
                    'qty': row.qty,
                    'dnp': row.dnp
                })
            self._save_json(bom_file, bom_data)
            
            # Save metadata
            meta_file = project_dir / "meta.json"
            meta_data = {
                "name": project.name,
                "description": project.description,
                "created_at": project.created_at,
                "updated_at": datetime.now().isoformat()
            }
            self._save_json(meta_file, meta_data)
            
            return True
        except Exception as e:
            print(f"Error saving project: {e}")
            return False
    
    def load_project(self, project_name: str):
        """Load project from disk"""
        try:
            project_dir = self.projects_dir / project_name
            if not project_dir.exists():
                return None
            
            # Load metadata
            meta_file = project_dir / "meta.json"
            meta_data = self._load_json(meta_file)
            if not meta_data:
                return None
            
            # Load BOM
            bom_file = project_dir / "bom.json"
            bom_data = self._load_json(bom_file) or []
            
            from src.models import Project, BomRow
            bom_rows = []
            for row_data in bom_data:
                bom_row = BomRow(**row_data)
                bom_rows.append(bom_row)
            
            project = Project(
                name=meta_data["name"],
                description=meta_data.get("description", ""),
                created_at=meta_data.get("created_at", ""),
                updated_at=meta_data.get("updated_at", ""),
                bom=bom_rows
            )
            
            return project
        except Exception as e:
            print(f"Error loading project: {e}")
            return None
    
    def list_projects(self) -> List[str]:
        """List all project names"""
        projects = []
        if self.projects_dir.exists():
            for item in self.projects_dir.iterdir():
                if item.is_dir() and (item / "meta.json").exists():
                    projects.append(item.name)
        return projects
    
    def delete_project(self, project_name: str) -> bool:
        """Delete a project"""
        try:
            project_dir = self.projects_dir / project_name
            if project_dir.exists():
                shutil.rmtree(project_dir)
                return True
            return False
        except Exception as e:
            print(f"Error deleting project: {e}")
            return False
    
    # Master inventory operations
    def save_master_inventory(self, items) -> bool:
        """Save master inventory to disk"""
        try:
            master_file = self.master_dir / "electronics.json"
            data = [item.to_dict() for item in items]
            self._save_json(master_file, data)
            return True
        except Exception as e:
            print(f"Error saving master inventory: {e}")
            return False
    
    def load_master_inventory(self):
        """Load master inventory from disk"""
        master_file = self.master_dir / "electronics.json"
        data = self._load_json(master_file) or []
        
        from src.models import MasterItem
        return [MasterItem.from_dict(item) for item in data]
    
    def get_next_id(self) -> int:
        """Get and increment next available ID counter"""
        next_id_file = self.master_dir / "next_id.txt"
        current_id = int(next_id_file.read_text().strip())
        next_id_file.write_text(str(current_id + 1))
        return current_id
    
    # Order operations
    def save_order(self, order) -> bool:
        """Save purchase order to disk"""
        try:
            order_file = self.orders_dir / f"{order.order_id}.json"
            
            # Convert everything to pure JSON-safe dict
            order_data = {
                "order_id": order.order_id,
                "supplier": order.supplier,
                "status": order.status,
                "notes": order.notes,
                "created_at": order.created_at,
                "received_at": getattr(order, "received_at", None),
                "line_items": [
                    {
                        "internal_id": li.internal_id,
                        "qty_ordered": li.qty_ordered,
                        "unit_price": li.unit_price,
                        "manufacturer_part_number": li.manufacturer_part_number
                    }
                    for li in order.line_items
                ]
            }

            self._save_json(order_file, order_data)
            return True

        except Exception as e:
            print(f"Error saving order: {e}")
            return False
    
    def load_order(self, order_id: str):
        """Load purchase order from disk"""
        order_file = self.orders_dir / f"{order_id}.json"
        data = self._load_json(order_file)
        
        if data:
            from src.models import Order, OrderLineItem
            
            # 🔥 Convert dict → OrderLineItem objects
            line_items = [
                OrderLineItem(**li) for li in data.get("line_items", [])
            ]
            
            data["line_items"] = line_items
            
            return Order(**data)
        
        return None
    
    def list_orders(self, status: Optional[str] = None):
        from src.models import Order, OrderLineItem
        
        orders = []
        if self.orders_dir.exists():
            for file in self.orders_dir.glob("*.json"):
                data = self._load_json(file)
                if data:
                    # 🔥 FIX: convert dict → OrderLineItem
                    line_items = [
                        OrderLineItem(**li) for li in data.get("line_items", [])
                    ]
                    data["line_items"] = line_items
                    
                    order = Order(**data)
                    
                    if status is None or order.status == status:
                        orders.append(order)
        
        return sorted(orders, key=lambda x: x.created_at, reverse=True)
    
    # Configuration
    def save_config(self, config) -> bool:
        """Save configuration to disk"""
        try:
            self._save_json(self.config_file, config.__dict__)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def load_config(self):
        """Load configuration from disk"""
        data = self._load_json(self.config_file)
        if data:
            from src.models import Config
            return Config(**data)
        return None