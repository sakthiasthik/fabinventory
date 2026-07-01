"""File system management for FabInventory"""

import json
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import shutil
from src.models import validate_project_name


class FileManager:  # Make sure this is exactly "FileManager" (capital F, capital M)
    """Handles all file system operations"""

    def __init__(self, repo_path: str = "./fabinventory_data"):
        self.repo_path = Path(repo_path)
        self.projects_dir = self.repo_path / "projects"
        self.master_dir = self.repo_path / "master"
        self.orders_dir = self.repo_path / "orders"
        self.config_file = self.repo_path / "config.json"
        self._id_lock = threading.Lock()

        # Ensure directory structure exists
        self._init_structure()

    def _project_dir(self, project_name: str) -> Path:
        """Get project directory with path-traversal protection."""
        validate_project_name(project_name)
        return self.projects_dir / project_name

    def project_subdir(self, project_name: str, subdir: str) -> Path:
        """Get (and create) a subdirectory within a project folder."""
        d = self._project_dir(project_name) / subdir
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_project_file(self, project_name: str, subdir: str, filename: str, content: bytes) -> Path:
        """Save an uploaded file into the project's folder. Returns the saved path."""
        dest_dir = self.project_subdir(project_name, subdir)
        dest_path = dest_dir / filename
        dest_path.write_bytes(content)
        return dest_path

    def _init_structure(self):
        """Create necessary directories if they don't exist"""
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.master_dir.mkdir(parents=True, exist_ok=True)
        self.orders_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize master inventory files if not exists
        for filename in ("electronics.json", "mechanical.json", "pcb.json", "print3d.json"):
            master_file = self.master_dir / filename
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
            project_dir = self._project_dir(project.name)
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
                    'dnp': row.dnp,
                    'dnp_raw': row.dnp_raw
                })
            self._save_json(bom_file, bom_data)
            
            # Save metadata
            meta_file = project_dir / "meta.json"
            meta_data = {
                "name": project.name,
                "description": project.description,
                "created_at": project.created_at,
                "updated_at": datetime.now().isoformat(),
                "image": project.image,
                "mechanical_bom": project.mechanical_bom,
                "pcb_bom": project.pcb_bom,
                "print3d_bom": project.print3d_bom,
                "model_3d_file": project.model_3d_file,
                "pcb_image": project.pcb_image,
                "pcb_gerber_zip": project.pcb_gerber_zip,
                "pcb_gerber_folder": project.pcb_gerber_folder,
                "pcb_repo_link": project.pcb_repo_link,
                "github_links": project.github_links
            }
            self._save_json(meta_file, meta_data)
            
            return True
        except Exception as e:
            print(f"Error saving project: {e}")
            return False
    
    def load_project(self, project_name: str):
        """Load project from disk"""
        try:
            project_dir = self._project_dir(project_name)
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
                image=meta_data.get("image", ""),
                bom=bom_rows,
                mechanical_bom=meta_data.get("mechanical_bom"),
                pcb_image=meta_data.get("pcb_image", ""),
                print3d_bom=meta_data.get("print3d_bom"),
                model_3d_file=meta_data.get("model_3d_file", ""),
                pcb_gerber_zip=meta_data.get("pcb_gerber_zip"),
                pcb_gerber_folder=meta_data.get("pcb_gerber_folder"),
                pcb_repo_link=meta_data.get("pcb_repo_link", ""),
                github_links=meta_data.get("github_links", [])
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
            project_dir = self._project_dir(project_name)
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
        """Get and increment next available ID counter (thread-safe)."""
        with self._id_lock:
            next_id_file = self.master_dir / "next_id.txt"
            current_id = int(next_id_file.read_text().strip())
            next_id_file.write_text(str(current_id + 1))
            return current_id

    # ── Mechanical master inventory ──────────────────────────────

    def save_mechanical_inventory(self, items) -> bool:
        try:
            master_file = self.master_dir / "mechanical.json"
            data = [item.to_dict() for item in items]
            self._save_json(master_file, data)
            return True
        except Exception as e:
            print(f"Error saving mechanical inventory: {e}")
            return False

    def load_mechanical_inventory(self):
        master_file = self.master_dir / "mechanical.json"
        data = self._load_json(master_file) or []
        from src.models import MasterItemMech
        return [MasterItemMech.from_dict(item) for item in data]

    # ── PCB master inventory ────────────────────────────────────

    def save_pcb_inventory(self, items) -> bool:
        try:
            master_file = self.master_dir / "pcb.json"
            data = [item.to_dict() for item in items]
            self._save_json(master_file, data)
            return True
        except Exception as e:
            print(f"Error saving PCB inventory: {e}")
            return False

    def load_pcb_inventory(self):
        master_file = self.master_dir / "pcb.json"
        data = self._load_json(master_file) or []
        from src.models import MasterItemPcb
        return [MasterItemPcb.from_dict(item) for item in data]

    # ── 3D Print master inventory ────────────────────────────────

    def save_print3d_inventory(self, items) -> bool:
        try:
            master_file = self.master_dir / "print3d.json"
            data = [item.to_dict() for item in items]
            self._save_json(master_file, data)
            return True
        except Exception as e:
            print(f"Error saving 3D print inventory: {e}")
            return False

    def load_print3d_inventory(self):
        master_file = self.master_dir / "print3d.json"
        data = self._load_json(master_file) or []
        from src.models import MasterItemPrn3D
        return [MasterItemPrn3D.from_dict(item) for item in data]

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