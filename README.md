# fabinventory
FabInventory is a local-first, Git-powered inventory and BOM tracker for makers — automatically syncing all changes to your GitHub repository.

[What is FabInventory & How It Works](./WhatsFabInventory.md)

Folder Structure Here
```
fabinventory/
│
├── .gitignore
├── README.md
├── WhatsFabInventory.md
├── LICENSE
├── requirements.txt
├── start.sh
├── start.bat
│
├── main/
│   ├── app.py              # FastAPI entry point
│   │
│   ├── core/               # Pure business logic
│   │   ├── aggregator.py
│   │   ├── parser.py
│   │   └── models.py
│   │
│   ├── services/           # Git & system services
│   │   └── git_manager.py
│   │
│   ├── templates/          # HTML files
│   │   ├── dashboard.html
│   │   ├── projects.html
│   │   └── inventory.html
│   │
│   └── static/             # CSS / JS (if needed)
│
├── data/                   # VERY IMPORTANT (tracked)
│   ├── projects/
│   ├── master_inventory.json
│   └── config.json

```