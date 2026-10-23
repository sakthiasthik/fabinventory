"""BOM file parsing for CSV and Excel formats"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Union
from src.models import BomRow


class BOMParser:
    """Parses BOM files in CSV or Excel format"""
    COLUMN_ALIASES = {

        # ====================================
        # ELECTRICAL BOM
        # ====================================

        "electrical": {

            "si_no": ["si.no", "s.no", "no", "index"],

            "reference": ["reference", "ref", "designator"],

            "value": ["value", "component value"],

            "footprint": ["footprint", "package"],

            "manufacturer_part_number": [
                "manufacturer_part_number",
                "mpn",
                "part number"
            ],

            "manufacturer_name": [
                "manufacturer_name",
                "manufacturer",
                "brand"
            ],

            "manufacturer_part_number_lcsc": [
                "manufacturer_part_number_lcsc"
            ],

            "manufacturer_name_lcsc": [
                "manufacturer_name_lcsc"
            ],

            "lcsc_sku": [
                "lcsc sku code",
                "lcsc",
                "sku"
            ],

            "qty": ["qty", "quantity"],

            # DNP-style columns: a marker means DO NOT populate
            "dnp": [
                "dnp",
                "do not populate",
                "dnf",
                "no pop",
                "no stuff",
                "n/f",
                "not fitted",
                "not populated"
            ],

            # Populate-style columns: a marker means the part IS populated
            # (the opposite convention — handled by inverting the check)
            "populate": [
                "populate",
                "placement",
                "fitted",
                "populated",
                "mounted",
                "stuff"
            ]
        },

        # ====================================
        # 3D PRINT BOM
        # ====================================

        "3dprint": {

            "si_no": ["si.no", "s.no", "no", "index"],

            "part_name": [
                "component name / 3d print part name",
                "part name"
            ],

            "material": [
                "3d printing material",
                "material"
            ],

            "quantity": [
                "quantity",
                "qty"
            ],

            "file_link": [
                "file link (github link ) / location",
                "file link"
            ]
        },

        # ====================================
        # PCB BOM
        # ====================================

        "pcb": {

            "si_no": [
                "si.no",
                "s.no",
                "no"
            ],

            "board_name": [
                "board name",
                "pcb name"
            ],

            "layer": [
                "layer",
                "layers"
            ],

            "material": [
                "material"
            ],

            "quantity": [
                "quantity",
                "qty"
            ],

            "manufacturer": [
                "manufacturer"
            ],

            "file_link": [
                "file link",
                "gerber link"
            ]
        },

        # ====================================
        # MECHANICAL BOM
        # ====================================

        "mechanical": {

            "si_no": [
                "si.no",
                "s.no",
                "no"
            ],

            "part_name": [
                "mechanical part description",
                "mechnical part description",
                "part description",
                "part name"
            ],

            "value": [
                "value",
                "size"
            ],

            "quantity": [
                "quantity",
                "qty",
                "qunatity"
            ],

            "purchase_site": [
                "purchase site"
            ],

            "purchase_link": [
                "purchase link",
                "purchase link "
            ]
        }
    }
    # COLUMN_ALIASES = {
    #     "si_no": ["si.no", "s.no", "no", "index"],
    #     "reference": ["reference", "ref", "designator"],
    #     "value": ["value", "component value"],
    #     "footprint": ["footprint", "package"],
    #     "manufacturer_part_number": ["manufacturer_part_number", "mpn", "part number"],
    #     "manufacturer_name": ["manufacturer_name", "manufacturer", "brand"],
    #     "manufacturer_part_number_lcsc": ["manufacturer_part_number_lcsc"],
    #     "manufacturer_name_lcsc": ["manufacturer_name_lcsc"],
    #     "lcsc_sku": ["lcsc sku code", "lcsc", "sku"],
    #     "qty": ["qty", "quantity"],
    #     "dnp": ["dnp", "do not populate"]
    # }
    
    @staticmethod
    def normalize_column(col):
        return ''.join(
            ch.lower()
            for ch in col
            if ch.isalnum()
        )

    # Values that mean "do not populate" in a DNP-style column
    # (already normalized: uppercase, letters/digits only)
    DNP_MARKERS = {
        '1', 'YES', 'TRUE', 'X', 'DNP', 'DNF',
        'NOPOP', 'NF', 'NOTFITTED', 'NOTPOPULATED',
    }

    # Values that mean "this part IS populated" in a Populate-style column
    FITTED_MARKERS = {
        '1', 'YES', 'TRUE', 'Y',
        'FITTED', 'POPULATED', 'MOUNTED', 'STUFFED', 'STUFF',
    }

    @staticmethod
    def _normalize_marker(value: str) -> str:
        """Uppercase a marker and strip everything but letters/digits."""
        return ''.join(ch for ch in str(value).upper() if ch.isalnum())

    @classmethod
    def _is_dnp(cls, dnp_raw: str, populate_raw: str) -> bool:
        """True when the row is Do-Not-Populate.

        BOMs use two opposite conventions:
        - DNP-style columns (DNP / Do Not Populate / DNF):
          a marker means the part is NOT populated.
        - Populate-style columns (Populate / Placement / Fitted):
          a marker (1 / YES / FITTED …) means the part IS populated,
          so anything that is not a fitted marker counts as DNP.
          An empty cell is treated as populated (the safer default —
          blank populate columns must not drop parts from the order).
        If both columns exist, the explicit DNP column wins.
        """
        d = cls._normalize_marker(dnp_raw)
        p = cls._normalize_marker(populate_raw)
        if d:
            return d in cls.DNP_MARKERS
        if p:
            return p not in cls.FITTED_MARKERS
        return False


    @classmethod
    def parse_file(
        cls,
        file_path: str,
        bom_type: str = "electrical"
    ):
        """Parse BOM from CSV or Excel file"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Read based on file extension
        if file_path.suffix.lower() in ['.csv']:
            df = pd.read_csv(file_path)
        elif file_path.suffix.lower() in ['.xlsx', '.xls', '.xlsm']:
            df_raw = pd.read_excel(file_path, engine='openpyxl', header=None)

            
            # Find header row dynamically
            header_row = None

            search_keywords = []

            for aliases in cls.COLUMN_ALIASES[bom_type].values():
                search_keywords.extend(aliases)

            for i, row in df_raw.iterrows():

                row_values = [
                    str(cell).strip().lower()
                    for cell in row.values
                    if pd.notna(cell)
                ]

                match_count = 0

                for keyword in search_keywords:

                    keyword_norm = cls.normalize_column(keyword)

                    for cell in row_values:

                        cell_norm = cls.normalize_column(cell)

                        if keyword_norm == cell_norm:

                            match_count += 1
                            break

                # Require at least 3 matching headers
                if match_count >= 3:

                    header_row = i
                    break

            if header_row is None:
                raise ValueError("Could not detect BOM header row")

            # Reload with correct header
            df = pd.read_excel(file_path, engine='openpyxl', header=header_row)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")
        
        # Validate required columns
        # Normalize dataframe columns
        df.columns = [col.strip() for col in df.columns]

        mapped_columns = {}

        aliases_map = cls.COLUMN_ALIASES[bom_type]

        for std_key, aliases in aliases_map.items():
            for col in df.columns:
                norm_col = cls.normalize_column(col)
                if any(cls.normalize_column(alias) == norm_col for alias in aliases):
                    mapped_columns[std_key] = col
                    break

        # Only enforce minimal required fields
        if bom_type == "electrical":

            required_fields = ["reference", "qty"]

        elif bom_type == "3dprint":

            required_fields = ["part_name", "quantity"]

        elif bom_type == "mechanical":

            required_fields = [
                "part_name",
                "value"
            ]

        elif bom_type == "pcb":

            required_fields = [
                "board_name",
                "quantity"
            ]

        else:

            required_fields = []
        missing = [field for field in required_fields if field not in mapped_columns]

        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        # Parse rows
        bom_rows = []

        for idx, row in df.iterrows():
            # Skip completely empty rows
            if row.isnull().all():
                continue
            
            try:
                def get(field, default=None):
                    col = mapped_columns.get(field)
                    return row[col] if col and pd.notna(row[col]) else default

                raw_dnp_value = str(
                    get("dnp", "")
                ).strip()

                raw_populate_value = str(
                    get("populate", "")
                ).strip()

                # DNP columns say "skip me"; Populate columns say "fit me"
                # (inverted). _is_dnp handles both conventions.
                is_dnp = cls._is_dnp(raw_dnp_value, raw_populate_value)

                if bom_type == "electrical":

                    qty = int(get("qty", 0))

                else:

                    qty = int(get("quantity", 0))

                if bom_type == "electrical":

                    bom_row = BomRow(

                        si_no=int(get("si_no", idx + 1)),

                        reference=str(get("reference", "")),

                        value=str(get("value", "")),

                        footprint=str(get("footprint", "")),

                        manufacturer_part_number=str(
                            get("manufacturer_part_number", "")
                        ),

                        manufacturer_name=str(
                            get("manufacturer_name", "")
                        ),

                        manufacturer_part_number_lcsc=str(
                            get("manufacturer_part_number_lcsc", "")
                        ),

                        manufacturer_name_lcsc=str(
                            get("manufacturer_name_lcsc", "")
                        ),

                        lcsc_sku=str(get("lcsc_sku", "")),

                        qty=qty,

                        dnp=is_dnp,
                        dnp_raw=raw_dnp_value
                    )

                elif bom_type == "3dprint":

                    bom_row = {

                        "si_no": int(get("si_no", idx + 1)),

                        "part_name": str(get("part_name", "")),

                        "material": str(get("material", "")),

                        "quantity": int(get("quantity", 0)),

                        "file_link": str(get("file_link", ""))
                    }

                elif bom_type == "mechanical":

                    bom_row = {

                        "si_no": int(get("si_no", idx + 1)),

                        "part_name": str(get("part_name", "")),

                        "value": str(get("value", "")),

                        "quantity": int(get("quantity", 0)),

                        "purchase_site": str(get("purchase_site", "")),

                        "purchase_link": str(get("purchase_link", ""))
                    }

                elif bom_type == "pcb":

                    bom_row = {

                        "si_no": int(get("si_no", idx + 1)),

                        "board_name": str(get("board_name", "")),

                        "layer": str(get("layer", "")),

                        "material": str(get("material", "")),

                        "quantity": int(get("quantity", 0)),

                        "manufacturer": str(get("manufacturer", "")),

                        "file_link": str(get("file_link", ""))
                    }

                bom_rows.append(bom_row)

            except Exception as e:
                print(f"Warning: Error parsing row {idx}: {e}")
                continue
        
        return bom_rows
       