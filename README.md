# FabInventory

**Git-backed inventory and BOM management for hardware engineers**

FabInventory helps hardware teams manage multiple project BOMs, aggregate master inventory, track stock, and collaborate via Git. No cloud hosting, no heavy database - just clone and run.

## Features

- 📋 **Project BOM Management** - Upload CSV/Excel BOMs for multiple projects
- 🔄 **Automatic Aggregation** - Master inventory auto-updates from all projects
- 📦 **Stock Tracking** - Manual stock entry with auto-calculated "to order" quantities
- 🛒 **Order Management** - Create purchase orders and track receipts
- 🔀 **Git Integration** - Full version control with commit history
- 👥 **Multi-user** - Collaborate via shared Git repository
- 📊 **Reports** - Export BOMs and inventory reports

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/fabinventory.git
cd fabinventory

# Install dependencies
pip install -r requirements.txt

# Install the package
pip install -e .