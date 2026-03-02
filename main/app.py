from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .core.models import Project, MasterInventory
from .core.aggregator import Aggregator
from .services.git_manager import GitManager, GitError


BASE_DIR = Path(__file__).parent
ROOT_DIR = BASE_DIR.parent
DATA_DIR = ROOT_DIR / "data"
PROJECTS_DIR = DATA_DIR / "projects"
CONFIG_FILE = DATA_DIR / "config.json"
MASTER_FILE = DATA_DIR / "master_inventory.json"

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="FabInventory")


# --- configuration helpers --------------------------------------------------

def load_config() -> Dict[str, Any]:
    """Return the configuration dictionary, creating the file if necessary.

    If the prefix is missing the user is prompted on the console.  Once a
    valid prefix is obtained the config is written and committed to git.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text("{}")
    conf: Dict[str, Any] = json.loads(CONFIG_FILE.read_text() or "{}")

    prefix = conf.get("prefix")
    if not prefix:
        # interactive prompt on startup; acceptable for a localhost app
        prefix = input("Enter two-letter internal ID prefix (e.g. YU): ").strip().upper()
        if len(prefix) != 2:
            prefix = prefix[:2].ljust(2, "X")
        conf["prefix"] = prefix
        CONFIG_FILE.write_text(json.dumps(conf, indent=2))
        try:
            GitManager.add_commit_push("Auto update config prefix")
        except GitError:
            pass
    return conf


def init_master_inventory() -> None:
    """Ensure that a master inventory file exists on disk."""
    if not MASTER_FILE.exists() or MASTER_FILE.read_text().strip() == "":
        master = MasterInventory()
        master.save(MASTER_FILE)
        try:
            GitManager.add_commit_push("Auto initialize master inventory")
        except GitError:
            pass


# --- startup event ----------------------------------------------------------

@app.on_event("startup")
async def startup_event() -> None:
    try:
        GitManager.pull()
    except GitError as exc:
        # for now just print; later we can surface in UI
        print(f"Git pull failed: {exc}")

    # create necessary directories and files
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    load_config()
    init_master_inventory()


# --- projects endpoints -----------------------------------------------------

@app.post("/projects")
def create_project(name: str) -> Dict[str, Any]:
    """Create a new project skeleton and persist it to disk.

    The request body should be a form or JSON containing ``name``.  If the
    project already exists a 400 error is returned.
    """
    clean_name = name.strip().replace(" ", "_")
    if not clean_name:
        raise HTTPException(status_code=400, detail="Invalid project name")

    file_path = PROJECTS_DIR / f"{clean_name}.json"
    if file_path.exists():
        raise HTTPException(status_code=400, detail="Project already exists")

    project = Project(name=clean_name, bom=[])
    project.save(file_path)

    try:
        GitManager.add_commit_push(f"Auto update - created project {clean_name}")
    except GitError as exc:
        # ignore git failures for now; in future surface in response
        print(f"Git commit failed: {exc}")

    # recalc master inventory after adding
    config = load_config()
    Aggregator.recalc(PROJECTS_DIR, MASTER_FILE, config.get("prefix", ""))

    return {"status": "ok", "project": clean_name}
