# Changelog

> **How to use this file:** every work session adds a new `## YYYY-MM-DD` section at the **top**.
> Each entry records: ✅ what changed, ❌ what mistakes we made, 🔧 how we fixed them, 🐛 errors we hit.
> This is our memory — if it's not here, it didn't happen.

---

## 2026-10-23 — Order-flow bug fixes (all 4 bugs from BUG.md)

### ✅ What changed

- **Bug 1 fixed** — `/api/project/<name>/components` now SUMS all BOM rows per part key (it kept only the first row, so order qty showed 1 instead of 10). Applied to all four categories (elec/mech/PCB/3D); references + MPNs collected.
- **Bug 2 fixed** — DNP detection split into DNP-style vs Populate-style columns: `Populate = YES/1` now correctly means *populated* (was inverted → fitted parts silently vanished from orders). Added `DNF` / `NO POP` / `N/F` markers; empty cells default to populated; explicit DNP column wins when both exist.
- **Bug 3 fixed** — quantities parse tolerantly (`2.5` → 3 half-up, `1,000`, `10 pcs`, `5 nos`); bad rows are no longer silently dropped — all four upload pages now flash row warnings, and unparseable files are rejected with a message.
- **Bug 4 fixed** — one `normalize_part_key` helper (collapse whitespace + lowercase) used everywhere: `100nF 0603` and `100nf  0603 ` now merge into ONE master item with shared stock.

### ❌ Mistakes we made (and learned from)

1. The original components endpoint de-duplicated by *dropping* rows instead of summing them — "keep the first row" is never a safe de-duplication.
2. DNP aliases mixed two opposite column conventions under one key — column *names* carry meaning; parse `DNP` and `Populate` semantics separately.

### 🔧 Fixes done

- Each fix has unit tests (30 → 34 tests, all passing) and its own commit: `a40da3c`, `1df296f`, `698d9e9`, `cd0b8fa`.

### 🐛 Errors hit & solved

| Error | Cause | Fix |
|---|---|---|
| `pytest: No module named pytest` in venv | dev dependency missing | installed pytest into `.venv` |
| `round(2.5) == 2` in quantity parsing | Python banker's rounding | half-up via `floor(x + 0.5)` |
| Marker set mismatch (`NO POP` vs normalized `NOPOP`) | markers stored un-normalized | marker sets stored pre-normalized |

---

## 2026-10-16 — Repo cleanup, history rewrite, fresh data start

### ✅ What changed

- **Order-page investigation done** — 4 bugs found (quantity mismatch on duplicate BOM rows, inverted DNP detection, silent row dropping, case-sensitive aggregation key). All documented in **[BUG.md](BUG.md)** — fixes planned one by one.
- **Branches simplified**: only `main`, `dev`, `dev-sakthi` remain. Old branches preserved as `archive/*` tags (`archive/dev-sneha`, `archive/test`, …)
- **Sync workflow fixed** (`.github/workflows/sync-dev-branches.yml`):
  - the branch that triggers a push now *also* receives `dev` back (it was excluded before)
  - pushes directly to `dev` now trigger a sync down to all `dev-*` branches
  - merge conflicts abort cleanly with clear error messages
- **Git history rewritten**: stripped all usage data & build artifacts from every commit and tag
  (`fabinventory_data/`, `instance/`, `error.md`, `check_import.py`, `dist/`, `build/`, old `FAB_INVENTORY/`, `Fab_Inventory/`). Repo went from ~100 MB to ~350 KB — source code only.
- **App data moved out of the repo** → `~/fabinventory-data` (pointed by `DATA_PATH` in `.env`)
- **Fresh data start**: old projects archived to `~/fabinventory-data-archive-20261016/`, app reset to first-run setup state
- **Dependency fix**: system python pandas `2.0.3` → `2.3.3` (compatible with numpy 2.x)

### ❌ Mistakes we made (and learned from)

1. **The app auto-committed usage data into the SOURCE repo.** `GitManager` targets the source repo root, so every stock update / BOM upload became a commit in the public code history — including gerbers, KiCad files, and a built `.env` with secrets. *Lesson: end-user data must never live inside the source repo.* (Proper code fix planned — git manager should version the user's data folder.)
2. **Sync workflow excluded the pushed branch** — so `dev-sakthi` drifted 3 commits behind `dev` and stayed behind forever until another branch pushed.
3. **Deleted all 3 projects via the web UI by accident** — the delete button has no confirmation and no undo. *Lesson: the app needs a confirm dialog and/or soft-delete (planned).*
4. **Ran a verification script against LIVE data** — `init_app()` wrote empty master inventory files over the real ones. *Lesson: never run app-init scripts against real data; make a backup first.*
5. **Old changelog only listed features, never mistakes.** That's why this format now exists.

### 🔧 Fixes done

- Backup bundle created **before** any destructive step: `~/fabinventory-pre-clean.bundle` (full old history)
- Projects + master inventory restored from the bundle after mistake #3/#4
- Full `git filter-repo` rewrite + force-push on all 3 branches + all tags; verified with a fresh clone (zero data files in history)
- Workflow re-verified after the rewrite (bot sync ran successfully on the new history)

### 🐛 Errors hit & solved

| Error | Cause | Fix |
|---|---|---|
| `ValueError: numpy.dtype size changed` | pandas 2.0.3 built against old numpy, system had numpy 2.2.6 | upgraded pandas to 2.3.3 |
| `Port 9000 is in use` | a stale app instance was already running | killed stale instance, restarted cleanly |
| Login POST → `400` | CSRF protection — form needs `csrf_token` | fetch token from the login page first, send it in the POST |
| `308` on `/inventory` | route redirects to `/inventory/` | follow redirects (`curl -L`) |

---

## [Unreleased] — feature backlog (old format, kept for history)

### Added

* Bootstrap-based project details page
* Electrical BOM upload and export
* Mechanical BOM upload support
* PCB BOM upload support
* 3D Print BOM upload support
* Project image upload and persistence
* 3D STL model upload and interactive viewer using Three.js
* Gerber ZIP upload and automatic extraction
* PCB repository link support (GitHub/GitLab)
* Dashboard statistics cards
* BOM search functionality
* CSV export support
* Dependency auto-installer in `run.py`
* Project category tabs: Electrical / Mechanical / PCB / 3D Print
* Print Information card for 3D projects
* Gerber ZIP upload success notifications
* Support for `.stl`, `.obj`, `.zip`, `.csv`, `.xlsx`, `.xls`

### Changed

* Improved BOM table responsiveness and readability
* Reorganized project details page into modular tabs
* Moved upload actions inside category tabs
* Standardized Mechanical and PCB upload layouts
* Updated Mechanical BOM schema (added `Mechanical Part Description`, `Value`)
* Updated PCB BOM workflow to support both Gerber ZIPs and repository links
* Improved STL viewer camera positioning and scaling
* Improved file path handling using normalized forward slashes

### Fixed

* BOM table text overlap / header truncation / manufacturer column visibility
* Duplicate dependency installation logs
* Project image persistence after restart
* Windows path separator issues in saved metadata
* STL model not rendering after reload
* Gerber ZIP upload persistence issues
* Broken file references after restart

### Security

* Safer dependency checking before startup
* Secure filename handling for uploads

---

## [0.1.0] - Initial Development

### Added

* Flask-based FabInventory application
* BOM parsing from CSV and Excel
* Inventory calculation system
* Project management support
* Git integration support
* Basic Bootstrap UI
