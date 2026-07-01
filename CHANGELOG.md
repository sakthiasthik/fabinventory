# Changelog

## [0.1.0] — Beta — 2026-07-01

### Added
- Flask Blueprint architecture (routes split by domain)
- Master inventory tabs: Electrical · Mechanical · PCB · 3D Print
- Excel/CSV bulk stock import
- Gerber ZIP upload with automatic extraction and file listing
- Gerber X2 validation on upload
- Unpushed-commit tracking in navbar widget
- Git user identity management in UI
- Auto-created `.env` on first run (no manual setup)
- Single-repo Git architecture (no nested `.git` in data folder)
- PCB image upload and preview
- GitHub/GitLab/Bitbucket remote URL support
- 3D model (STL) viewer via Three.js
- Commit author reads real Git identity from config
- Download BOM template (XLSX)

### Changed
- Electronics inventory sorted by footprint, then value
- GitManager targets project root, never auto-creates repos
- `REPO_PATH` renamed to `DATA_PATH`
- Push/pull auto-detect current branch
- Improved error messages in Git settings

### Fixed
- `add_inventory_component()` now generates proper unique IDs and saves to disk
- Removed wasted `get_next_id()` call on app init
- Gerber download path (broken by Blueprint refactor)
- Project image serving path (broken by Blueprint refactor)
- BOM template download path (broken by Blueprint refactor)
- Circular import in Blueprint registration

### Removed
- Nested `.git` repository inside `fabinventory_data/`
- Dev artifacts: `error.md`, `check_import.py`, `WhatsFabInventory.md`, `instance/users.db`
- Test project data from repository tracking
