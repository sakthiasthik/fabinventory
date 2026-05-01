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

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- git

### Setup Steps

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/fabinventory.git
cd fabinventory

# 2. Create a virtual environment
python3 -m venv venv

# 3. Activate the virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Install the package in development mode
pip install -e .

# 6. Copy the environment file and configure if needed
cp .env.example .env

# 7. Run the application
python run.py
```

The application will be available at `http://localhost:5000`