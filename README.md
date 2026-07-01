# FabInventory

**Git-backed inventory & BOM management for hardware engineers.**

FabInventory helps hardware teams manage project BOMs, aggregate master inventory, track stock levels, and create purchase orders — all backed by Git for version control and collaboration. No cloud, no database server — just clone and run.

---

## Features

| | |
|---|---|
| 📋 **Multi-project BOMs** | Upload CSV/Excel BOMs for electrical, mechanical, PCB, and 3D-print projects |
| 🔄 **Auto aggregation** | Master inventory auto-calculated from all project BOMs — always consistent |
| 📦 **Stock tracking** | Track current stock per component with auto-calculated "to order" quantities |
| 📊 **Tabled inventory** | Four tabs — Electrical · Mechanical · PCB · 3D Print |
| 📥 **Bulk stock import** | Upload existing stock lists via Excel/CSV |
| 🛒 **Purchase orders** | Create orders, track status (draft → ordered → shipped → received) |
| 🔀 **Git integration** | Auto-commits on every change, push/pull via UI, full commit history |
| 👤 **Git identity** | Commits are attributed to each user's real Git identity — you know who changed what |
| 🔐 **Authentication** | Password login + optional GitHub OAuth |
| 🖥️ **Cross-platform** | Runs on Linux, macOS, and Windows |

---

## Quick Start

```bash
git clone https://github.com/sakthiasthik/fabinventory.git
cd fabinventory
python run.py
```

That's it. The app auto-creates `.env` on first run, installs any missing dependencies, and starts at **http://localhost:9000**.

Login with the default password: **`fabinventory`** (change it in `.env` after first login).

> **Requirements:** Python 3.8+, Git (optional but recommended)

---

## Installation (detailed)

### Prerequisites
- Python 3.8 or higher
- Git (optional — for version control features)

### Option 1: Run directly (recommended)
```bash
git clone https://github.com/sakthiasthik/fabinventory.git
cd fabinventory
python run.py
```
`run.py` auto-installs missing packages and starts the server.

### Option 2: pip install
```bash
git clone https://github.com/sakthiasthik/fabinventory.git
cd fabinventory
pip install -e .
fabinventory
```

### Option 3: Virtual environment
```bash
git clone https://github.com/sakthiasthik/fabinventory.git
cd fabinventory
python3 -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows
pip install -r requirements.txt
python run.py
```

---

## First Run Setup

1. Open **http://localhost:9000**
2. Log in with password **`fabinventory`**
3. On the setup page, enter your **2-letter company prefix** (e.g., `SA` for "Sakthi")
4. This prefix is used for internal part numbers: `SA-ELE-00001`, `SA-MEC-00001`, etc.

---

## Usage

### 1. Create a Project
- Go to **Projects** → **Create Project**
- Give it a name and optional BOM file
- Projects can have: Electrical, Mechanical, PCB, and 3D Print BOMs

### 2. Upload BOMs
- Open a project → choose the tab (Electrical / Mechanical / PCB / 3D Print)
- Upload CSV or Excel BOM files
- Master inventory auto-updates across all projects

### 3. Track Stock
- Go to **Inventory** → view aggregated components across all projects
- Click the ✏️ icon to update stock for any component
- Use **Import Stock** to bulk-upload existing stock from Excel

### 4. Create Orders
- Go to **Orders** → **Create Order**
- Select projects and components to order
- Track order status: draft → ordered → shipped → received
- When received, stock levels auto-update

### 5. Git Sync
- Every data change is auto-committed locally
- Use the **navbar sync widget** to commit and push
- Set up a remote in **Git Settings** — works with GitHub, GitLab, Bitbucket (SSH or HTTPS)
- The widget shows how many commits are pending push

---

## Project Structure

```
fabinventory/
├── run.py                    # Entry point (auto-installs deps)
├── requirements.txt          # Python dependencies
├── setup.py                  # pip-installable package
├── .env.example              # Environment template
├── src/
│   ├── app.py                # Flask application & routes
│   ├── models.py             # Data models (dataclasses)
│   ├── file_manager.py       # JSON file read/write
│   ├── project_manager.py    # Project CRUD
│   ├── inventory_manager.py  # Inventory & order logic
│   ├── aggregator.py         # BOM → master inventory aggregation
│   ├── bom_parser.py         # CSV/XLSX BOM parser
│   └── git_manager.py        # Git commit/push/pull
├── templates/                # Jinja2 HTML templates
├── static/                   # CSS, JS, BOM template
├── fabinventory_data/        # Your data (auto-created)
│   ├── config.json
│   ├── master/               # Aggregated inventories
│   ├── projects/             # Per-project BOMs & files
│   └── orders/               # Purchase orders
└── test/                     # Pytest test suite
```

---

## Data Storage

All data is stored as **human-readable JSON files** in `fabinventory_data/`. No database required.

| File | Contents |
|---|---|
| `master/electronics.json` | Aggregated electrical components |
| `master/mechanical.json` | Aggregated mechanical parts |
| `master/pcb.json` | Aggregated PCB boards |
| `master/print3d.json` | Aggregated 3D print parts |
| `projects/<name>/bom.json` | Project electrical BOM |
| `projects/<name>/meta.json` | Project metadata |
| `orders/PO-*.json` | Purchase orders |

The `DATA_PATH` in `.env` controls where this folder lives. Set it to an absolute path to keep data separate from code.

---

## BOM File Format

### Electrical BOM columns
| Column | Description |
|---|---|
| `SI.No` | Serial number |
| `Reference` | Designator (R1, C2, U1…) |
| `Value` | Component value (10k, 100nF…) |
| `Footprint` | Package (0603, SOT-23…) |
| `Manufacturer_Part_Number` | MPN |
| `Manufacturer_Name` | Manufacturer |
| `Qty` | Quantity per board |
| `DNP` | Do Not Populate (X/Yes/1 = skip) |

Download the template from the app: **Projects → any project → Download template**

### Aggregation key
Components are deduplicated by **value + footprint**. Two projects using `100nF 0603` get merged into one master inventory item with combined quantity.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | auto-generated | Flask session encryption key |
| `DATA_PATH` | `./fabinventory_data` | Where data JSON files are stored |
| `ADMIN_PASSWORD` | `fabinventory` | Login password |
| `GITHUB_CLIENT_ID` | _(empty)_ | Enable GitHub OAuth login |
| `GITHUB_CLIENT_SECRET` | _(empty)_ | Enable GitHub OAuth login |

The `.env` file is **auto-created on first run** — you don't need to copy `.env.example` manually.

---

## Git Workflow

FabInventory uses a **single-repo** architecture — the project repo itself is the version-controlled source of truth.

- **Auto-commit**: Every project change, BOM upload, stock update, and order creation is auto-committed
- **Push/Pull**: Use the navbar widget or Git Settings page to sync with a remote
- **Identity**: Commits use your real Git `user.name` / `user.email` from the repo config
- **Unpushed tracking**: The navbar shows exactly how many commits are pending push

For team use: set up a shared remote (GitHub/GitLab/Bitbucket) in Git Settings, and each member pushes/pulls to stay in sync.

---

## Development

```bash
# Run tests
pip install pytest
python -m pytest test/ -v

# Run the app in debug mode
python run.py
# → http://localhost:9000 (debug mode auto-reloads on code changes)
```

---

## License

MIT License — see [LICENSE](LICENSE)
