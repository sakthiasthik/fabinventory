# FabInventory

FabInventory is a lightweight, Git-backed inventory and BOM management tool for hardware engineers.

It is designed to be simple, local-first, and fully version-controlled using Git.  
No cloud hosting. No heavy database. Just clone and run.

---

## 🚀 What is FabInventory?

FabInventory helps hardware teams manage:

- Multiple project BOMs
- Aggregated master inventory
- Existing stock tracking
- Git-based multi-user collaboration

The system automatically generates a master electronics inventory from all uploaded project BOMs.

---

## 🎯 Core Philosophy

- Local-first
- Git-synced
- Human-readable data (JSON)
- Simple aggregation logic
- No ERP complexity
- MIT licensed

---

## 🏗️ How It Works

### Workflow

```
Run App
→ Login with GitHub
→ View Master Dashboard
→ Create / Select Project
→ Upload BOM (CSV / Excel)
→ Master Inventory Auto-Recalculated
→ Auto Commit & Push to GitHub
```

All changes are committed to a shared GitHub repository.  
If multiple users use the same repository, each commit reflects their GitHub identity.

---

## 📁 Project Types

FabInventory supports:

- Electronics BOM
- Mechanical BOM (future phase)
- 3D Printing BOM (future phase)

Version 1 focuses on Electronics BOM.

---

## 📄 Electronics BOM Format

The BOM must follow a predefined format:

```
SI.No
Reference
Value
Footprint
Manufacturer_Part_Number
Manufacturer_Name
Manufacturer_Part_Number_LCSC
Manufacturer_Name_LCSC
LCSC SKU code
Qty
DNP
```

### Notes:

- `Qty` = Quantity per PCB
- `DNP` rows are ignored in aggregation
- Aggregation is based on:
  
  Value + Footprint

---

## 🔄 Aggregation Logic

FabInventory automatically aggregates components across all projects.

Example:

Project 1:
```100nF 0603 → 13 pcs```
Project 2:
```100nF 0603 → 7 pcs```
Master Inventory:
```100nF 0603 → 20 pcs```
If value differs:
```
100nF 6.3V 0603
100nF 25V 0603
```

These are treated as separate items.

---

## 🆔 Internal Part Numbering

On first setup, the user defines a 2-letter prefix  
(example: company name "Sakthi" → `SA`).

Electronics items are assigned internal IDs:
SA-ELE-00001
SA-ELE-00002

This ID remains stable across projects.

---

## 📊 Master Electronics Inventory

Each master item contains:

- Internal ID
- Value
- Footprint
- Total Required Quantity (auto-calculated)
- Current Stock (manual entry)
- To Order (auto-calculated)
- Used In Projects
- Associated MPNs

Total Required is always recalculated from all projects.

Stock is manually maintained.

---

## 🔁 Recalculation Model

FabInventory uses full recalculation.

Whenever:

- A project is added
- A BOM is updated
- A project is deleted

The master inventory is completely rebuilt from all project data.

This ensures consistency and prevents sync errors.

---

## 👥 Multi-User Support

FabInventory is Git-backed.

Each user:

- Logs in with GitHub
- Works locally
- Auto-commits changes
- Pushes to shared repository

Commit history shows real user identity.

---

## 📦 Data Storage

All data is stored in:

- Human-readable JSON files
- Version-controlled via Git
- No external database required

---

## 🔮 Future Plans (Phase 2)

- Smart build quantity calculation
- Order planning view
- Mechanical inventory
- 3D material tracking
- Advanced filtering & search

---

## 📜 License

MIT License

---

## 🤝 Contributing

FabInventory is open-source and designed for hardware engineers.

Contributions, suggestions, and improvements are welcome.

