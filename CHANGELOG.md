# Changelog

> **How to use this file:** every work session adds a new `## YYYY-MM-DD` section at the **top**.
> Each entry records: ✅ what changed, ❌ what mistakes we made, 🔧 how we fixed them, 🐛 errors we hit.
> This is our memory — if it's not here, it didn't happen.

---

## 2026-10-23 — UI round 2: galleries & lightbox, paged BOM blocks, vendor IDs/edit, consolidation editing

### ✅ What changed

- **Projects page** — bigger project blocks, bigger image area (250px) showing the **full image** (`object-fit: contain`, never cropped); clicking an image opens it in a **lightbox overlay** (arrow keys / Esc, counter, caption).
- **Project detail** — the image box is now a big (300px, contain) **slideshow** of all project images (cover + PCB gallery, indicators + arrows). Clicking any slide opens the lightbox at that slide; the PCB tab preview is wired to the same lightbox.
- **Fixed-length BOM blocks with in-block pagination** — project BOM (electrical), mechanical, 3D print, master inventory, purchase orders and consolidation detail tables now live in a fixed-height scrollable block with sticky headers and a pager (25 / 50 / 100 / All rows, Prev/Next, "Showing x–y of n"). Search and order filters re-run the pager. Default 50 rows per page.
- **Inventory** — ID column is now wide and non-wrapping (`min-width: 130px`) so internal IDs are easy to read.
- **Vendors** — every vendor gets a **Vendor ID** (`VEN-001…`, auto-assigned, editable, unique; existing vendors are backfilled); **Edit** button opens a modal (name, ID, contact, email, website, notes) posting to the new `/vendors/update` route; renames follow through into saved consolidations that reference the vendor by name; adding a duplicate name is refused with a warning.
- **Consolidation detail** — quantities are now **editable per line** (`to_order` inputs). Saved quantities are applied by *both* Save and Create Orders, so a quantity changed right before ordering is never silently dropped. **Bulk vendor assignment**: tick multiple lines (or Select all), pick one vendor, click "Apply & Save" — one vendor on many lines at once.
- Search boxes on the BOM and inventory pages switched from `keyup` to `input`, so paste / clear / autofill also filter.

### ❌ Mistakes we made (and learned from)

1. **Jinja `{% set %}` inside a `{% for %}` loop does not persist outside the loop** — the gallery list I accumulated that way silently kept only the first image, so the slideshow rendered a single image. Fixed with `namespace(gallery=[])` + `{% set ns.gallery = ... %}`. *The test client caught the HTML; the browser check caught the symptom. Loop accumulation in Jinja always needs a namespace object.*
2. I tried to syntax-check JavaScript with Python's `ast.parse` — obviously wrong tool; the real JS validator is the browser pass.
3. Hit the template-cache lesson again: the first re-run of browser checks still showed the old gallery because the temp server (non-debug Flask) cached the pre-fix template. Restarting the port owner fixed it.

### 🔧 Fixes done

- Gallery list built via Jinja `namespace` (main gallery + PCB tab gallery).
- `_apply_line_edits()` helper shared by Save Vendors and Create Orders; `_ensure_vendor_ids()` helper + `/vendors/update` route with name/id uniqueness checks.
- New regression tests: `test_vendor_ids_are_assigned_uniquely`, `test_line_edits_apply_vendors_and_quantities`, `test_line_edits_ignore_junk_quantities`.

### ✅ Verification

- **56 unit tests pass** · **29/29 browser checks pass** on a seeded temp data folder (64-row BOM so pagination really paginates, 3-image gallery, one order per lifecycle status) · 13 page renders 200 · 9-page phone sweep at 400px: zero console errors, zero page errors, zero horizontal scroll · lightbox keyboard/close, pager next/page-size, qty edit persistence, bulk vendor, vendor edit round-trip, order filter pills all exercised in Chromium.

---

## 2026-10-23 — Visible UI refresh (design system) + order-status display fix

### ✅ What changed

- **New design system** appended to `static/css/style.css`: indigo/slate palette as CSS tokens, system-font type scale, 14px cards with soft shadows, pill tabs, rounded inputs/buttons, refined tables, badges, alerts, modals, empty states and a small footer. Legacy hover-lift-on-every-card and harsh `!important` table headers overridden.
- **Navbar**: sticky dark navy bar, gradient brand tile, pill links with a clear active state, rounded sync button.
- **Dashboard**: page header with subtitle, four icon stat cards (accent rail, icon tile, arrow on hover), styled "needs ordering" table, new empty state.
- **Projects**: responsive card grid — image/placeholder, description, component/qty chips, full-width Open button, icon-only delete with confirmation.
- **Inventory**: pill category tabs, toolbar card (actions + search), table card, friendly empty state.
- **Order pages**: `/orders` gets a page header, lifecycle filters (Draft / Ordered / Shipped / Received / Cancelled) and correct status badges; Order Tracking gets page header, status-accent cards and a proper empty state.
- **BOM Consolidation**: neutral "Select Project" card header (was a loud cyan block), quieter quick-action buttons, shared header/chip styling; saved-consolidation cards inherit the new look.
- **Consolidation detail**: summary chips instead of plain badges.
- **Vendors**: page header, table card, empty state; mailto links preserved.
- **Login**: matched the dark indigo theme with the brand tile and primary Sign In button.
- **Status fix**: the Purchase Orders page displayed every status other than `received` as **Cancelled** (including real draft/ordered/shipped orders). It now renders the actual lifecycle status and filters by it. Dashboard "Pending Orders" counted only the legacy `pending` status (never written by current code); it now counts `draft`, `ordered`, `shipped` (and legacy `pending`).
- **Verification:** 53 unit tests pass · 13 page loads (9 desktop at 1440px + 4 phone at 400px) with zero console/page errors and zero horizontal page scroll · computed styles confirm the new tokens (navbar `rgb(11,18,32)`, stat radius `14px`, pill tabs `rgb(238,241,247)`).

### ❌ Mistakes we made (and learned from)

1. **My first CSS append silently did nothing.** `.pcb-image-placeholder` was missing its closing `}` in the legacy file; the new section was parsed as declarations inside that rule, so browsers dropped it. The template render check passed because it only proves HTML/Jinja. *Caught only by asserting computed styles in Playwright (`body` background was `none`, stat radius `0px`). CSS changes need a computed-style assertion, not a screenshot alone.*
2. **`kill <shell pid>` did not kill the dev server.** The Bash wrapper PID exited while its Python child kept port 9123; the next "restarted" server could not bind, so I re-ran checks against the old process and stale templates. *Kill the listening PID (or the process group) and verify the port is free before restarting.*
3. The `/orders` "everything is Cancelled" bug had been there since the new lifecycle statuses were introduced; only the seeded screenshots exposed it. *Seed realistic statuses in UI checks, not just empty pages.*

### 🔧 Fixes done

- Closed the missing `.pcb-image-placeholder` brace — CSS now parses as one balanced sheet (194 `{` / 194 `}`).
- `/orders`: correct status chain + filters; filter pills styled via `.filter-btn` and a one-line `.active` toggle; detail-modal badge mapping updated.
- `InventoryManager.get_order_summary()`: active-status set replaces the legacy `pending`-only check; regression test `test_order_summary_counts_active_statuses`.
- Temporary UI server now started detached, with the port-owner PID verified before checks.

### 🐛 Errors hit & solved

| Error | Cause | Fix |
|---|---|---|
| Entire new CSS section ignored (navbar old colour, no stat cards) | missing `}` before the new section nested it inside `.pcb-image-placeholder` | closed the rule; re-ran computed-style checks |
| Browser checks showed old UI after "restart" | killed the nohup wrapper, Python child kept port 9123 | killed the listening PID, verified `port free`, restarted |

### ⏳ Still open (found while styling)

- No UI action moves an order `draft → ordered → shipped`; `receive_order` only accepts `shipped → received` and the Receive button only appears for legacy `pending`. Real orders therefore cannot reach "received" from the UI yet. Recorded in `BUG.md`.

---

## 2026-10-23 — Max-effort code review (12 findings) + fixes + UI/UX pass

### ✅ What changed

- Ran the `code-review` skill at max effort over the **entire uncommitted changeset** (~2,000-line diff): 10 finder angles → one verifier per candidate → final sweep. ~25 min, 8 sub-agents.
- **12 findings survived verification, and I re-read all 12 in the code — all real.** Top 3 were money/data bugs: fully stocked lines ordered at full quantity, the PCB gallery dropped on restart, and a second "Create Orders" click duplicating every PO.
- **All 12 are now fixed locally** (not committed — commit gate), each with a regression test where testable. Per-finding fix table in `BUG.md`.
- **Verification:** 52 unit tests pass · 26 automated browser checks pass against a **temporary** data folder · 14-page headless crawl clean (the `/git-settings` 500 in that crawl is the harness only: `git_manager` was deliberately disabled so verification could never commit into the source repo).
- **UI/UX pass:** active navbar highlighting; success/info flashes auto-dismiss after 5s (warnings/errors stay); consolidation detail gained summary chips (lines / units / Draft-Ordered); ordered consolidations show a banner, disabled controls and a Track button; PCB delete is per-image with confirmation; vendor rows show mailto links and `—` instead of blanks.

### ❌ Mistakes we made (and learned from)

1. **I claimed the per-tab stats fix was "verified" — it wasn't.** The swap script sits at `project_details.html:167-179`, *before* `#projectTabs` exists at line 188, so zero listeners attach and the cards never change. My test-client check only proved the page renders; it cannot catch JS execution-order bugs. *Lesson: a UI feature is not verified until the JS is exercised in a browser.*
2. `save_project` hand-builds `meta_data` and omitted `pcb_images` — the same class of bug as `save_order` dropping fields earlier today. *Dataclass `to_dict()` must be the single serializer.*
3. Splitting the consolidation page into three separate `<form>`s created a hidden dependency: vendor dropdowns live in "Save Vendors" while "Create Orders" posts its own form, so unsaved vendor changes are silently ignored.
4. **The app's `GitManager` still targets the source repo**, so verification had to run with `git_manager` disabled by hand — otherwise every test order would have created a real commit. That is the 2026-10-16 bug, still open, and it means testing the app can never be done naively against the repo checkout.

### 🔧 Fixes done

- **#1** `_order_qty()` — only a *missing* `to_order` falls back to `total_required`; `0` stays `0`. Manual qty edits now write back to `currentProjectComponents`; the same falsy-zero bug in `createOrderFromConsolidation` (JS) fixed too.
- **#2** `save_project` persists `pcb_images` — the gallery survives restarts.
- **#3** Create Orders writes `status` / `order_id` / `ordered_at` back and refuses to run twice; the button disappears once ordered.
- **#4** Per-image PCB delete (`image` form field, membership-checked) with a confirm per slide.
- **#5** `_component_fields()` gives every category a readable name/spec/MPN in the detail table **and** the CSV.
- **#6** Vendor selects and Create Orders share one form; the route applies posted vendors before splitting.
- **#7** Custom line items are included in saved consolidations; save failures surface instead of failing silently.
- **#8** Stats-swap script now runs on `DOMContentLoaded` (it sat before `#projectTabs`).
- **#9** Vendor delete uses `data-name` + a listener (apostrophes work, no injection).
- **#10** Consolidation id is validated before any PO is created; `FileManager` rejects bad ids on load/save.
- **#11** `_merge_tree()` merges setup leftovers recursively and keeps clashes as `-migrated-N`.
- **#12** `FileManager.create_consolidation()` assigns the sequence under the id lock.

### 🐛 Errors hit & solved

| Error | Cause | Fix |
|---|---|---|
| Background "wait for review" shell never exited | `pgrep -f 'code-review'` matched its own command line → infinite spin loop | killed via TaskStop; wait on the task notification instead |

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

### ✅ Full-site audit with Playwright (same session — local)

- Every page crawled headlessly (14 pages): all 200, **zero** JS errors, zero broken images; auth verified (302→login, APIs 401); phone-width (400px) responsive checks
- Fixed 3 findings: `/setup` re-runnable after configuration (locked now), Werkzeug debugger exposed on 0.0.0.0 (now opt-in via `FLASK_DEBUG=1`), inventory search box overflow at phone width
- Audit findings + method recorded in `BUG.md` ("Full-site audit" section)

### ✅ Vendors + per-vendor orders + consolidation download (same session — local)

- **Vendors page** (navbar): add/edit/delete suppliers with contact, email, website (auto `https://`), notes — stored in `vendors/vendors.json`
- **Consolidation detail page**: every saved consolidation opens to a line-item table (component, footprint, MPN, per-project references, to-order) with a **vendor dropdown per line**. "Create Orders (one per vendor)" splits the consolidation and creates **one PO per vendor**, each carrying that vendor's website link automatically
- **Download CSV** on every saved consolidation — same per-project reference columns as the page export, plus a Vendor column
- Order Tracking shows each split PO with its vendor link + CON badge — that's the multi-vendor answer: one order per vendor, tracked separately

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
