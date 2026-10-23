# 🐛 Known Bugs

> Found: 2026-10-16 — order page investigation (multi-project / multi-board orders)
> Status: **ALL 4 FIXED** on 2026-10-23 (see each bug + `CHANGELOG.md` 2026-10-23)
> Related session notes: see `CHANGELOG.md`

---

## 🔍 Code review — 2026-10-23 (max effort, 12 findings — ALL FIXED)

**Method:** `code-review` skill at max effort — 10 finder angles, one adversarial verifier per candidate, one final sweep. Scope: the whole uncommitted changeset (~2,000-line diff: setup rework, project page, BOM Consolidation, vendors, consolidation records, order tracking).
**Status:** ✅ ALL 12 FIXED on 2026-10-23 (local only, not committed). Every finding was re-read in the code first; per-finding fixes + regression tests are listed at the end of this section.

### 🔴 Critical

1. **Fully-stocked parts get ordered at full quantity** — `src/routes/orders.py:275`
   `comp.get('to_order') or comp.get('total_required')` treats a legitimate `to_order = 0` as "missing" and falls back to the whole required quantity. A part needing 100 with 100 in stock → a PO for 100. Also: edits to the per-line qty input are never written back, so a line the user zeroes is still ordered at its old qty.
   **Fix:** read `to_order` with an explicit `is None` check, not `or`.

2. **PCB image gallery is lost on restart** — `src/file_manager.py:117`
   `save_project` builds `meta_data` without `pcb_images`, while `load_project` reads it. After any restart every gallery image except the first disappears from the UI, and the orphaned files can no longer be deleted from the app.
   **Fix:** persist `pcb_images` (ideally serialize through the dataclass, not a hand-built dict).

3. **Second "Create Orders" click duplicates every PO** — `src/routes/orders.py:302`
   `consolidation_create_orders` never writes `status` / `order_id` back to the record (unlike `api.py:322-328`). The record stays Draft, the button stays visible, and clicking again creates a fresh set of POs for the same line items.
   **Fix:** write status + created order ids back, and refuse to re-run on an ordered record.

### 🟠 High

4. **One click deletes the entire PCB image set** — `src/routes/projects.py:896`
   `remove_pcb_image` deletes every file in `pcb_images` + `pcb_image` and clears both, while the page shows a single unconfirmed "Remove Image" button.
   **Fix:** per-image delete (with confirm), keeping the rest.

5. **PCB / mechanical / 3D lines are anonymous in consolidation + CSV** — `templates/consolidation_detail.html:49`, `src/routes/orders.py:344-348`
   These read only `value` / `footprint` / `mpn`, but the components API emits `board_name` for PCB and `part_name` / `material` for mechanical and 3D. Those lines show blank cells; the CSV gets rows like `,,,,,1,1,LCSC`.
   **Fix:** render a category-aware label (same logic as the consolidation page).

6. **Unsaved vendor picks are silently ignored** — `templates/consolidation_detail.html:81`
   Vendor dropdowns live in the "Save Vendors" form; "Create Orders" is a separate form that posts only `csrf_token`. Pick vendors → click Create Orders → "Assign vendors…" error. After saving once, changing a dropdown and clicking Create Orders orders from the *old* vendor.
   **Fix:** one form (or submit vendor values with the Create Orders request).

7. **Custom line items vanish from saved consolidations** — `templates/create_order.html:377`
   `saveConsolidation` posts only `currentProjectComponents`; `additionalComponents` (added by hand) are dropped from the record and from any orders made from it. The live order path includes them. No try/catch either, so a failed save is silent.
   **Fix:** append `additionalComponents` before posting; wrap fetch in try/catch.

### 🟡 Medium

8. **Per-tab stats never switch** — `templates/project_details.html:176`
   The swapping script runs at lines 167-179, before `#projectTabs` exists (line 188) → zero listeners attach. Electrical stats stay visible on every tab. *(Regression of today's own feature — my earlier "verified" claim covered rendering only, not JS.)*
   **Fix:** move the script after the tabs markup or wrap in `DOMContentLoaded`.

9. **Vendor name injected into inline JS** — `templates/vendors.html:81`
   `onsubmit="return confirm('Remove {{ v.name }}?')"` — HTML entity decoding restores quotes: `O'Brien` breaks the confirm (delete submits unconfirmed); a crafted name can execute script on click.
   **Fix:** `data-name` + delegated listener, or `{{ v.name|tojson }}`.

10. **Unvalidated `consolidation_id` can 500 after creating a PO** — `src/routes/api.py:322`
    `POST /api/create-order` with `consolidation_id='../master/electronics'` creates the order, then loads the wrong JSON; `record['status'] = 'ordered'` on a list raises → 500. The PO exists; the user retries and duplicates it.
    **Fix:** validate the id (`^CON-\\d{6}-\\d{3}$`) before creating anything.

### 🟢 Low

11. **Setup folder merge can silently skip or crash** — `src/routes/main.py:213`
    When both folders have a same-named project dir it is skipped entirely (its BOM/meta stay in the abandoned folder), the merge is one level deep, and a file-vs-dir name clash raises `NotADirectoryError` despite the "never crash" comment.

12. **Consolidation id race** — `src/routes/api.py:366`
    Read-then-write with no lock: two simultaneous saves compute the same `CON-YYYYMM-NNN` and the second overwrites the first. Unlikely for one local user, but cheap to fix (reuse `FileManager._id_lock`).

### ✅ Fix summary (all applied locally — not committed)

| # | Fix | Regression test |
|---|---|---|
| 1 | `_order_qty()` — only a *missing* `to_order` falls back; a real `0` stays 0. Page qty edits write back to `currentProjectComponents`; the same falsy-zero bug in `createOrderFromConsolidation` (JS) fixed too | `test_order_qty_*` |
| 2 | `save_project` now persists `pcb_images` — gallery survives restarts | `test_pcb_images_survive_save_load` |
| 3 | Create Orders writes `status` / `order_id` / `ordered_at` back and refuses to re-run an ordered record; button hidden when ordered | browser check (no duplicate PO) |
| 4 | Per-image PCB delete (`image` field, membership-checked) + per-slide confirm buttons; one click no longer wipes the gallery | browser check (only clicked file removed) |
| 5 | `_component_fields()` renders PCB / mechanical / 3D / custom lines in both the detail table and the CSV | `test_component_fields_per_category` |
| 6 | Vendor selects and Create Orders share one form; the route applies posted vendors before splitting | browser check (vendor picks used) |
| 7 | Custom line items included in saved consolidations; save failures now surface (try/catch) | manual/browser |
| 8 | Stats-swap script runs on `DOMContentLoaded` (it sat before `#projectTabs`) | browser check (tab stats swap) |
| 9 | Vendor delete uses `data-name` + a listener — apostrophes work, no script injection | browser check (`O'Brien`) |
| 10 | Consolidation id validated before the PO is created; `FileManager` rejects invalid ids on load/save | `test_consolidation_*_rejects_bad_ids` |
| 11 | `_merge_tree()` merges setup leftovers recursively; name clashes are kept as `-migrated-N`, never skipped or crashing | `test_merge_tree_keeps_colliding_project` |
| 12 | `FileManager.create_consolidation()` assigns the sequence under the id lock | `test_create_consolidation_sequence` |

**Verification:** 52 unit tests pass; 26 Playwright checks pass against a **temporary** data folder; 14-page crawl clean (the `/git-settings` 500 there is the harness only — `git_manager` was deliberately disabled).

### ⏳ Still open (not part of this review)

- **`GitManager` still targets the source repo root** (known since 2026-10-16). In-app actions can commit usage data into the code repo. Verification must therefore run with git disabled; the real fix is to point GitManager at the user's data folder.

---

## 🎨 UI round 2 findings — 2026-10-23

**Method:** seeded temp data folder (64-row BOM, 3-image project gallery, one order per lifecycle status), Playwright at 1440×900 + 400×850, computed-style + interaction assertions.

### ✅ Fixed this session

1. **Gallery slideshow showed only the first image** — the image list was accumulated with `{% set x = x + [...] %}` inside a Jinja `for` loop; Jinja does not persist `set` across loop iterations. Rebuilt with `namespace()` objects. (The bug never reached the user — caught by the browser check on the same day.)
2. **Search ignored paste/clear/autofill** — BOM and inventory search listened on `keyup` only. Switched to `input`.

### ✅ Verified clean

- 29/29 feature checks pass (lightbox open/next/keys/close, pagination across pages and page sizes, qty edit persistence, bulk vendor assignment, vendor edit round-trip, order filter pills, ID column width)
- 13 page renders 200; 9-page phone sweep: zero console/page errors, zero horizontal scroll
- 56 unit tests pass
- No commits created during verification (temp data + git manager disabled)

### ⏳ Still open (unchanged)

1. No UI action moves an order through `draft → ordered → shipped`; `receive_order` only accepts `shipped → received`. Orders therefore cannot reach "received" from the UI yet. (Recorded 2026-10-23, design pass.)

---

## 🎨 UI refresh findings — 2026-10-23

**Method:** seeded temporary data folder, Playwright at 1440×900 and 400×850, screenshots of every page, computed-style assertions (tokens, navbar, tabs, tables), console/page-error capture, horizontal-overflow checks.

### ✅ Fixed this session

1. **`/orders` called every non-received order "Cancelled"** — the template only knew `pending` and `received`; anything else (including real `draft` / `ordered` / `shipped` orders) fell into the `else` branch. Fixed the badge chain and replaced the Pending/Received filters with the full lifecycle: Draft, Ordered, Shipped, Received, Cancelled.
2. **Dashboard "Pending Orders" was always 0** — `get_order_summary()` counted only status `pending`, which current order creation never writes (orders start `draft`). Now counts `draft`, `ordered`, `shipped` and legacy `pending`. Regression test added.

### ⏳ Still open

1. **No way to advance an order through its lifecycle in the UI.** `Order.VALID_TRANSITIONS` requires `draft → ordered → shipped → received`, and `receive_order()` only succeeds from `shipped`. Nothing in the app sets `ordered` or `shipped`, and the Receive button is rendered only for legacy `pending`. So a normal order can never be marked received from the UI. Next step: transition controls on Order Tracking (Mark Ordered / Mark Shipped / Mark Received), with the existing transition guard.

### ✅ Verified clean

- 13 page loads across desktop (9 pages) and phone width (4 pages): zero console errors, zero page errors, zero horizontal page scroll
- All 53 unit tests pass
- No commits created during verification (temp data folder + `git_manager = None`)

---

## 🕵️ Full-site audit — 2026-10-23 (Playwright crawl)

**Method:** Playwright headless Chromium. Every page crawled with console/page-error capture, broken-image check, 400px phone-width check, and unauthenticated-access check.

### 🐛 Found & fixed in this session (status: ✅ FIXED locally)

1. **`/setup` was re-runnable forever** — a public route that renames the data folder and overwrites the company config, even when logged out. Now redirects once the app is configured.
2. **Werkzeug debugger exposed on the network** — `app.run(debug=True)` on `0.0.0.0` means anyone on the LAN could use the debug console (the PIN is printed in the log). Debug is now opt-in via `FLASK_DEBUG=1`.
3. **Inventory search box overflowed at phone width** (`min-width:220px`) → page scrolled horizontally. Fixed with `max-width`.

### ✅ Verified clean (no action)

- All 14 pages: HTTP 200, zero console errors, zero page errors, zero broken images
- All protected pages redirect (302) to login when logged out; APIs return 401
- No horizontal scroll at phone width on any page (after fix #3)
- Bootstrap icons render correctly (font + glyphs verified)
- Consolidation flow works in a real browser (73 rows loaded after adding a project)

### ⏳ Known, non-blocking

- Old `.pyc` files exist in past commit history (cosmetic — strip later if desired)
- `main` branch is behind `dev` (manual PR pending — user's rule)

---

## Bug 1 — Order page quantity mismatch: duplicate BOM rows are dropped

**Severity:** 🔴 Critical (wrong quantities on orders)
**Where:** `src/routes/api.py` — `/api/project/<name>/components` (electrical block, ~lines 48-69)

**What happens:**
The endpoint keeps only the FIRST row of each `value + footprint` pair and uses only that row's qty:

```python
if cid in seen_ids:
    continue          # 2nd, 3rd, … row of the same part is thrown away
...
'qty': bom_row.qty,   # only the first row's qty survives
```

A normal BOM with one row per reference:

```
R1  100nF  0603  qty 1
R2  100nF  0603  qty 1
…10 rows
```

- Master inventory (aggregator sums all rows) → total_required = **10** ✓
- Order page → shows **qty = 1** ❌

**Effect:** "to order" column and board-quantity multiplication are all based on the wrong number.
This is the exact cause of the reported *quantity mismatch* when ordering multiple boards.

**Fix:**
Sum qty across ALL rows per `value|footprint` (collect references too), compute `to_order` on the total sum, not per row.

**Status:** ✅ FIXED — commit `a40da3c` (helpers `_elec/_mech/_pcb/_prn_components` in `src/routes/api.py`, 7 unit tests)

---

## Bug 2 — Missing line items: DNP detected INVERTED for Populate/Placement/Fitted columns

**Severity:** 🔴 Critical (populated parts silently excluded from orders)
**Where:** `src/bom_parser.py:55-61` (column aliases) + `:324-333` (DNP check)

**What happens:**
Columns named `populate`, `placement`, `fitted` are treated as DNP columns, then any value
`1 / YES / TRUE / X / DNP` marks the row as DNP. But in most BOMs **"Populate = 1/YES" means the part IS fitted** — the opposite!

- Part that IS populated → marked DNP → **silently missing from the order page** ❌
- Common real DNP markers not recognized: `DNF`, `NO POP`, `N/F`, and `0` in a Populate column → genuinely unpopulated parts wrongly INCLUDED (opposite error)

**Fix:**
Split the semantics:
- DNP-named columns (`dnp`, `do not populate`): `1 / YES / TRUE / X / DNP / DNF / NO POP / N/F` = DNP
- Populate-named columns (`populate`, `placement`, `fitted`): **invert** — `1 / YES / TRUE` = populated (NOT DNP), `0 / NO / empty` = DNP

**Status:** ✅ FIXED — commit `1df296f` (`_is_dnp` helper in `src/bom_parser.py`; empty populate cells default to populated; 5 new tests)

---

## Bug 3 — Silent row dropping: one bad quantity cell = one missing part, no warning

**Severity:** 🟠 High (silent data loss on upload)
**Where:** `src/bom_parser.py:337,345` (`int(get("qty", 0))`) + `except: continue` at line 432

**What happens:**
Any qty cell like `2.5`, `10 pcs`, `1,000`, or a non-numeric `SI.No` → `int()` raises →
the row is silently skipped (only a console `print`). Upload 50 lines, get 47 parts, and nothing tells you why.

**Fix:**
Tolerant quantity parsing (float → rounded int, strip commas/units) AND collect all row warnings
and show them to the user after upload instead of dropping silently.

**Status:** ✅ FIXED — commit `698d9e9` (`parse_quantity`/`parse_int_fallback` + `parse_file_with_warnings`; all 4 upload routes flash warnings and reject unparseable files; 4 new tests)

---

## Bug 4 — Same part split into multiple master items by case/whitespace

**Severity:** 🟡 Medium (split stock, duplicate line items)
**Where:** `src/aggregator.py:28,37` — aggregation key is exact `value|footprint` match

**What happens:**
`100nF` vs `100nf` vs `100nF ` (trailing space) become THREE separate master items →
stock split across them, and two projects spelling the same part differently create duplicate line items.

**Fix:**
Normalize the key: `strip()` + `lower()` on both value and footprint everywhere the key is built (aggregator + the stock lookup in the components API).

**Status:** ✅ FIXED — commit `cd0b8fa` (single `normalize_part_key` helper in `src/models.py` used by models, aggregator, components API; 4 new tests)

---

## ✅ Checked and CORRECT (no action needed)

- Board-quantity multiplication in `templates/create_order.html` JS (`qty × boards`, merge, `to_order` recalc) — math is right; it inherits the wrong base from Bug 1
- DNP exclusion in `src/aggregator.py` (`is_active()`) — consistent with the API (both wrong together only because of Bug 2's inversion)
- `/order/create` POST route in `src/routes/orders.py` is dead code (the form posts to `/api/create-order`) — confusing but harmless; remove later

---

## Fix order (completed 2026-10-23)

1. ✅ API endpoint: sum all rows per `value|footprint` → `a40da3c`
2. ✅ DNP logic: separate DNP-column vs Populate-column semantics → `1df296f`
3. ✅ Parser: tolerant qty parsing + surface row warnings → `698d9e9`
4. ✅ Normalize aggregation key (lowercase + strip) → `cd0b8fa`

Each fix has its own commit + its own CHANGELOG entry (2026-10-23).
