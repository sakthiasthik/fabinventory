"""Project management operations"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from src.models import Project, BomRow
from src.file_manager import FileManager
from src.bom_parser import BOMParser


class ProjectManager:
    """Manages project CRUD operations"""
    
    def __init__(self, file_manager: FileManager):
        self.file_manager = file_manager
        self.projects: Dict[str, Project] = {}
        self._load_all_projects()
    
    def _load_all_projects(self):
        """Load all projects from disk"""
        project_names = self.file_manager.list_projects()
        for name in project_names:
            project = self.file_manager.load_project(name)
            if project:
                self.projects[name] = project
    
    def create_project(self, name: str, description: str = "") -> Optional[Project]:
        """Create a new project"""
        if name in self.projects:
            raise ValueError(f"Project '{name}' already exists")
        
        project = Project(name=name, description=description)
        
        if self.file_manager.save_project(project):
            self.projects[name] = project
            return project
        
        return None
    
    def get_project(self, name: str) -> Optional[Project]:
        """Get a project by name"""
        return self.projects.get(name)
    
    def update_project_bom(self, name: str, bom_file_path: str) -> Optional[Project]:
        """Update project BOM from file"""
        if name not in self.projects:
            raise ValueError(f"Project '{name}' not found")
        
        # Parse BOM file
        bom_rows = BOMParser.parse_file(bom_file_path)
        
        # Update project
        project = self.projects[name]
        project.bom = bom_rows
        project.updated_at = datetime.now().isoformat()
        
        # Save to disk
        if self.file_manager.save_project(project):
            return project
        
        return None
    
    def delete_project(self, name: str) -> bool:
        """Delete a project"""
        if name not in self.projects:
            return False
        
        if self.file_manager.delete_project(name):
            del self.projects[name]
            return True
        
        return False
    
    def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects with metadata"""
        projects_info = []
        for name, project in self.projects.items():
            projects_info.append({
                "name": project.name,
                "description": project.description,
                "created_at": project.created_at,
                "updated_at": project.updated_at,
                "component_count": len(project.bom),
                "total_quantity": sum(row.qty for row in project.bom if not row.dnp)
            })
        return projects_info
    
    def get_project_summary(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed summary of a project"""
        project = self.get_project(name)
        if not project:
            return None
        
        # Count components by footprint
        footprint_counts = {}
        for row in project.bom:
            if row.is_active():
                footprint_counts[row.footprint] = footprint_counts.get(row.footprint, 0) + row.qty
        
        return {
            "name": project.name,
            "description": project.description,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
            "total_components": len([r for r in project.bom if r.is_active()]),
            "total_quantity": sum(r.qty for r in project.bom if r.is_active()),
            "dnp_components": len([r for r in project.bom if r.dnp]),
            "footprint_summary": footprint_counts
        }
    
    def export_project_bom(self, name: str, output_path: str, format: str = "csv") -> bool:
        """Export project BOM to file"""
        project = self.get_project(name)
        if not project:
            return False
        
        import pandas as pd
        
        # Prepare data
        data = []
        for row in project.bom:
            data.append({
                "SI.No": row.si_no,
                "Reference": row.reference,
                "Value": row.value,
                "Footprint": row.footprint,
                "Manufacturer_Part_Number": row.manufacturer_part_number,
                "Manufacturer_Name": row.manufacturer_name,
                "Manufacturer_Part_Number_LCSC": row.manufacturer_part_number_lcsc or "",
                "Manufacturer_Name_LCSC": row.manufacturer_name_lcsc or "",
                "LCSC SKU code": row.lcsc_sku or "",
                "Qty": row.qty,
                "DNP": "X" if row.dnp else ""
            })
        
        df = pd.DataFrame(data)
        
        # Export
        if format.lower() == "csv":
            df.to_csv(output_path, index=False)
        elif format.lower() in ["xlsx", "excel"]:
            df.to_excel(output_path, index=False, engine='openpyxl')
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        return True