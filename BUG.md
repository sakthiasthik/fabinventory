# 🐛 Known Bugs

> Found: 2026-10-16 — order page investigation (multi-project / multi-board orders)
> Status: **OPEN** — to be fixed one by one (see fix order at the bottom)
> Related session notes: see `CHANGELOG.md` 2026-10-16 entry

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

---

## Bug 4 — Same part split into multiple master items by case/whitespace

**Severity:** 🟡 Medium (split stock, duplicate line items)
**Where:** `src/aggregator.py:28,37` — aggregation key is exact `value|footprint` match

**What happens:**
`100nF` vs `100nf` vs `100nF ` (trailing space) become THREE separate master items →
stock split across them, and two projects spelling the same part differently create duplicate line items.

**Fix:**
Normalize the key: `strip()` + `lower()` on both value and footprint everywhere the key is built (aggregator + the stock lookup in the components API).

---

## ✅ Checked and CORRECT (no action needed)

- Board-quantity multiplication in `templates/create_order.html` JS (`qty × boards`, merge, `to_order` recalc) — math is right; it inherits the wrong base from Bug 1
- DNP exclusion in `src/aggregator.py` (`is_active()`) — consistent with the API (both wrong together only because of Bug 2's inversion)
- `/order/create` POST route in `src/routes/orders.py` is dead code (the form posts to `/api/create-order`) — confusing but harmless; remove later

---

## Fix order (agreed)

1. API endpoint: sum all rows per `value|footprint` → kills the quantity mismatch
2. DNP logic: separate DNP-column vs Populate-column semantics
3. Parser: tolerant qty parsing + surface row warnings to the user
4. Normalize aggregation key (lowercase + strip)

Each fix gets its own commit + its own CHANGELOG entry.
