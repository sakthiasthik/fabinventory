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

### ✅ Project page & create-project fixes (same session — local, not yet committed)

- **Unified create-project**: dashboard and projects page had two *different* modals (dashboard lacked the image field); both POST to the same route, which *ignored* the image. Now one shared `_create_project_modal.html` include + the route saves `project_image` — identical behavior everywhere
- **Screenshot upload fixed**: after a successful image upload, the "Export Image" link used `url_for('static', filepath=…)` → `BuildError` → 500. Now uses `serve_project_file` (verified: page renders 200 with the image)
- **Per-tab stats**: the cards under the project name showed electronics numbers on every tab. Now each tab has its own block — Electrical shows line-item breakdown (Total / DNP / Placement) and quantity breakdown (Total / DNP / Placement); Mechanical/PCB/3D show their own line-item + quantity counts. A small JS swaps the block with the active tab
- **Junk BOM rows skipped**: electrical BOM rows with no designator, no value AND no footprint are silently dropped instead of polluting the BOM (unit test added)

### ❌ Mistakes we made (and learned from)

1. Duplicating the create-project form in two templates with different fields — one modal must be a shared include, or the two will drift apart.
2. Jinja: `tab_stats.print3d` fails — dict keys must use `tab_stats['3dprint']` when the key isn't an exact identifier; caught by the isolated verification run, not the unit tests.

### ✅ Consolidation workflow (same session — local, not yet committed)

- **Create Order button moved to the TOP** of the BOM Consolidation page (also fixed 400 diagnostics: the API now logs rejected items and returns clearer error messages)
- **Save Consolidation**: the consolidated list can be saved as a record with a sequence number (`CON-YYYYMM-NNN`) — separate from projects on purpose, so the master inventory never double-counts. Saved records show on the page with their projects × board quantities, line count and to-order totals
- **Create Order FROM a saved consolidation**: prompts vendor + vendor website link → order stores `consolidation_id` + `vendor_link`; the consolidation record flips to "Ordered → PO-…"
- **Order Tracking page** shows the CON badge + clickable vendor site per order
- `Order` model gained `consolidation_id` + `vendor_link` (old order files load fine); `save_order` also now persists `shipped_at`/`tracking_info`/`shipping_info` which it silently dropped before

### ❌ Mistakes we made (and learned from)

1. `save_order` hand-built its dict and silently dropped fields — dataclass `to_dict()` is the single source of serialization; adding a field in two places is how fields get lost.
2. AJAX posts read the CSRF token from a `csrf_token` **cookie** that Flask-WTF never sets → every save/order click returned 400 "The CSRF token is missing" with no visible explanation. The token must come from the page's hidden `input[name="csrf_token"]` (cookie only as fallback). This was also the user's earlier "JSON error".

### ✅ Setup page reworked (same session)

- Setup now collects **company name** (required) + **optional prefix** — blank prefix auto-derives from the name (`Sakthi Electronics` → `SA`), with a live preview in the form
- Data folder now carries the prefix on disk: `fabinventory-data` → `fabinventory-data-SA`, and the new path is persisted into `.env` so restarts keep using it
- Optional **website** and **git/bitbucket** links collected (https:// auto-prepended); stored in config for later editing from profile settings (planned)
- **Fixed the stuck-setup bug**: the form's stray `data_path` field saved config into a relative in-repo folder while the app read config from the env data path → dashboard bounced back to setup forever. The route now uses the app's own data path, the field is gone, and the flow was verified end-to-end (setup → login → dashboard)
- `.gitignore` hardened: every `fabinventory_data*` / `fabinventory-data*` variant is ignored — verified no test data can reach the public repo

### ❌ Mistakes we made (and learned from)

1. The original components endpoint de-duplicated by *dropping* rows instead of summing them — "keep the first row" is never a safe de-duplication.
2. DNP aliases mixed two opposite column conventions under one key — column *names* carry meaning; parse `DNP` and `Populate` semantics separately.
3. The setup form let the user edit the storage path — a text box for data paths is a trap: the form saved config to `./fabinventory_data` (in-repo!) while the app looked at the env `DATA_PATH`. The app must own its data path.

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
