#!/usr/bin/env python3
"""Run FabInventory web application."""

import subprocess
import sys
import os
import webbrowser


def _is_frozen():
    """True when running as a PyInstaller bundle."""
    return getattr(sys, 'frozen', False)


# ── Auto-install dependencies (skip when frozen) ──────────────
if not _is_frozen():
    required_packages = {
        "pandas": "pandas",
        "openpyxl": "openpyxl",
        "git": "gitpython",
        "dotenv": "python-dotenv",
        "requests": "requests",
        "flask": "flask",
        "flask_wtf": "flask-wtf",
        "wtforms": "wtforms",
        "markdown": "markdown",
        "pydantic": "pydantic",
    }

    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        print("\nChecking required dependencies...\n")
        for import_name, pip_name in required_packages.items():
            try:
                __import__(import_name)
                print(f"[OK] {pip_name}")
            except ImportError:
                print(f"[INSTALLING] {pip_name}")
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", pip_name,
                ])
        print("\nAll dependencies are ready.\n")

# ── Path setup ────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

# ── Start ─────────────────────────────────────────────────────
if __name__ == '__main__':
    # Auto-open browser after Flask starts
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        webbrowser.open("http://localhost:9000")

    from src.app import main
    main()
