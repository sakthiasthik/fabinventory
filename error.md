# 🐛 FabInventory — Bug Tracker

> Fix one by one. Each bug has a checkbox, severity, file location, and fix suggestion.

---

## 🔴 CRITICAL (Fix First)

### [x] BUG-001 — Hardcoded Secret Key in Source Code ✅ FIXED
- **File**: `src/app.py:26`
- **Severity**: 🔴 Critical
- **Category**: Security

```python
app.secret_key = os.environ.get('SECRET_KEY', 'fabinventory-secret-key-change-this')
```

**Problem**: The fallback secret key is publicly visible in the git repo. Anyone who sees this source can forge Flask session cookies → session hijacking + arbitrary data tampering.

**Fix**:
```python
secret = os.environ.get('SECRET_KEY')
if not secret:
    raise RuntimeError("SECRET_KEY environment variable must be set")
app.secret_key = secret
```

---

### [x] BUG-002 — Dead/Unreachable Code (Export Function) ✅ FIXED
- **File**: `src/app.py:366-413`
- **Severity**: 🔴 Critical
- **Category**: Logic Bug

```python
@app.route('/project/<name>/export')
def export_bom(name):
    ...
    return "Export not implemented yet"   # <-- RETURNS HERE

    # 👇 LINES 382-413: NEVER EXECUTED — dead code
    import io
    import pandas as pd
    from flask import Response
    ...
    return Response(...)
```

**Problem**: The `return` on line 366 short-circuits the entire function. The CSV export implementation on lines 382–413 is completely dead code.

**Fix**: Delete lines 382–413 (the dead code). If you want CSV export, move the implementation before the return.

---

### [x] BUG-003 — Race Condition in ID Generation ✅ FIXED
- **File**: `src/file_manager.py:193-198`
- **Severity**: 🔴 Critical
- **Category**: Data Integrity

```python
def get_next_id(self) -> int:
    current_id = int(next_id_file.read_text().strip())
    next_id_file.write_text(str(current_id + 1))  # NO LOCK
    return current_id
```

**Problem**: Read → increment → write with zero synchronization. Under any concurrent load, this **will** produce duplicate IDs, corrupting inventory and order data.

**Fix**: Add a thread lock:
```python
import threading

class FileManager:
    def __init__(self, ...):
        ...
        self._id_lock = threading.Lock()

    def get_next_id(self) -> int:
        with self._id_lock:
            next_id_file = self.master_dir / "next_id.txt"
            current_id = int(next_id_file.read_text().strip())
            next_id_file.write_text(str(current_id + 1))
            return current_id
```

---

### [x] BUG-004 — No CSRF Protection on Any Form ✅ FIXED
- **File**: All POST routes in `src/app.py`
- **Severity**: 🔴 Critical
- **Category**: Security

**Problem**: Not a single endpoint has CSRF protection. Flask-WTF is in `requirements.txt` but never used. Every state-changing POST is vulnerable:

- `POST /project/create` — No CSRF
- `POST /project/<name>/delete` — No CSRF
- `POST /project/<name>/upload` — No CSRF
- `POST /inventory/update-stock` — No CSRF
- `POST /order/<order_id>/receive` — No CSRF
- `POST /git-settings` — No CSRF (can change remotes!)
- `POST /api/create-order` — No CSRF

An attacker can trick any user into creating projects, modifying stock, or pushing to arbitrary git remotes.

**Fix**: Initialize CSRF globally in `app.py`:
```python
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect(app)
```
Then add `{{ csrf_token() }}` to all `<form>` tags in templates. For AJAX calls, include the CSRF token in headers.

---

### [x] BUG-005 — Stored XSS via innerHTML from BOM Data ✅ FIXED
- **File**: `templates/create_order.html:333-371`
- **Severity**: 🔴 Critical
- **Category**: Security (XSS)

```javascript
tbody.innerHTML = components.map(comp => `
    <tr>
        <td><strong>${comp.value}</strong></td>    <!-- UNSANITIZED -->
        <td>${comp.footprint}</td>                   <!-- UNSANITIZED -->
        <td><code>${comp.mpn || '—'}</code></td>    <!-- UNSANITIZED -->
    </tr>
`).join('');
```

**Problem**: Component data from BOM files (user-uploaded Excel/CSV) is injected into the DOM via `innerHTML` with zero escaping. A malicious BOM row with `value = <img src=x onerror=stealCookies()>` executes in every user's browser.

Same pattern exists in:
- `displayAdditionalComponents()` at line 387
- `renderSelectedProjects()` at line 833
- `orders.html` component display

**Fix**: Escape HTML before insertion:
```javascript
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
// Use: <td><strong>${escapeHtml(comp.value)}</strong></td>
```
Or use `textContent` instead of `innerHTML` where possible.

---

### [x] BUG-006 — Path Traversal via Project Names ✅ FIXED
- **File**: `src/file_manager.py` (all file operations), `src/app.py` (all project routes)
- **Severity**: 🔴 Critical
- **Category**: Security

```python
# file_manager.py:56
project_dir = self.projects_dir / project.name
# If project.name = "../../../etc" → writes outside data dir
```

**Problem**: Project names from URLs (`/project/<name>/...`) are used directly in filesystem paths with no sanitization. An attacker could create a project named `../../../.ssh` and write arbitrary files.

**Fix**: Validate project names at creation:
```python
import re

PROJECT_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{1,63}$')

def create_project(self, name, description=""):
    if not PROJECT_NAME_RE.match(name):
        raise ValueError(f"Invalid project name: {name}")
    ...
```

---

### [x] BUG-007 — `github_links` Saved in Memory but Never Persisted ✅ FIXED
- **File**: `src/app.py:1113-1129` vs `src/file_manager.py:78-102` vs `src/models.py:27-77`
- **Severity**: 🔴 Critical
- **Category**: Data Loss

```python
# app.py : adds to dynamically-created attribute
if not hasattr(project, "github_links"):
    project.github_links = []       # NOT in the Project dataclass!
project.github_links.append({...})

# file_manager.py save_project() : never saves github_links
meta_data = {
    ...
    "pcb_repo_link": project.pcb_repo_link  # saves pcb_repo_link instead
}

# models.py : github_links does NOT exist on Project class
```

**Problem**: PCB repo links appear to save (flash message says "saved"), but vanish on app restart because `github_links` is never serialized to disk.

**Fix**:
1. Add `github_links: List[Dict] = field(default_factory=list)` to `Project` dataclass in `models.py`
2. Add `"github_links": project.github_links` in `save_project()` meta_data
3. Load `github_links` back in `load_project()`

---

## 🟠 HIGH

### [x] BUG-008 — Order ID Collision (Duplicate PO Numbers) ✅ FIXED
- **File**: `src/inventory_manager.py:52-56`
- **Severity**: 🟠 High
- **Category**: Data Integrity

```python
def create_order(self, supplier, items, notes=""):
    existing_orders = self.file_manager.list_orders()
    order_num = len(existing_orders) + 1
    order_id = f"PO-{datetime.now().strftime('%Y%m')}-{order_num:03d}"
```

**Problem**: Uses `len(existing_orders) + 1` for sequence number. If you have 5 orders (PO-001 to PO-005) and delete PO-002, the next order will be PO-005 again — overwriting the existing PO-005.

**Fix**: Scan for the actual max sequence number:
```python
existing = self.file_manager.list_orders()
max_num = 0
for o in existing:
    try:
        num = int(o.order_id.split('-')[-1])
        max_num = max(max_num, num)
    except (ValueError, IndexError):
        pass
order_num = max_num + 1
```

---

### [x] BUG-009 — No Input Validation on update_stock ✅ FIXED
- **File**: `src/app.py:425-441`
- **Severity**: 🟠 High
- **Category**: Data Integrity

```python
new_stock = int(request.form.get('stock', 0))
updated = state.inventory_manager.update_stock(internal_id, new_stock)
```

**Problems**:
1. Negative stock values accepted (e.g., `stock=-9999`)
2. `internal_id` is never validated — any string accepted
3. No authorization check

**Fix**:
```python
new_stock = int(request.form.get('stock', 0))
if new_stock < 0:
    flash('Stock cannot be negative', 'error')
    return redirect(url_for('inventory'))

item = state.inventory_manager.update_stock(internal_id, new_stock)
if not item:
    flash(f'Item {internal_id} not found', 'error')
    return redirect(url_for('inventory'))
```

---

### [x] BUG-010 — `/api/orders` Returns Non-Serializable Objects ✅ FIXED
- **File**: `src/app.py:766`
- **Severity**: 🟠 High
- **Category**: Runtime Error

```python
@app.route('/api/orders')
def api_orders():
    ...
    return jsonify([o.__dict__ for o in orders])  # ❌ BROKEN
```

**Problem**: `Order.__dict__` contains `line_items` as `OrderLineItem` objects (not dicts). Flask's `jsonify` will raise `TypeError: Object of type OrderLineItem is not JSON serializable` when this endpoint is called.

**Fix**:
```python
return jsonify([o.to_dict() for o in orders])
```

---

### [x] BUG-011 — Bare `except: pass` Silently Swallows All Exceptions ✅ FIXED
- **File**: `src/inventory_manager.py:25-28`
- **Severity**: 🟠 High
- **Category**: Error Handling

```python
try:
    id_num = int(item.internal_id.split('-')[-1])
    max_id = max(max_id, id_num)
except:
    pass  # Swallows KeyboardInterrupt, SystemExit, EVERYTHING
```

**Problem**: A bare `except:` catches even `KeyboardInterrupt` and `SystemExit`. Any bug in the ID parsing is silently hidden.

**Fix**:
```python
try:
    id_num = int(item.internal_id.split('-')[-1])
    max_id = max(max_id, id_num)
except (ValueError, IndexError):
    pass
```

---

## 🟡 MEDIUM

### [ ] BUG-012 — Broken HTML: Triple Backticks in login.html
- **File**: `templates/login.html:7,93`
- **Severity**: 🟡 Medium
- **Category**: UI Bug

```html
<title>FabInventory Login</title>

```       <!-- ← Renders as visible text on page -->
<style>
```

**Problem**: Markdown-style triple backticks inside an HTML file render as literal text on the login page.

**Fix**: Delete the ` ``` ` markers on lines 7 and 93.

---

### [ ] BUG-013 — `datetime` Import at Bottom of File
- **File**: `src/git_manager.py:214`
- **Severity**: 🟡 Medium
- **Category**: Code Quality

```python
# ... all class definitions ...

from datetime import datetime  # ← At the VERY BOTTOM (line 214)
```

**Problem**: Import is at the bottom of the file but used inside `get_commit_history()` on line 191. Only works because Python has already executed the function's `def` statement before reaching the import. Fragile and violates PEP 8.

**Fix**: Move `from datetime import datetime` to the top of the file (line 1).

---

### [ ] BUG-014 — `MasterItem.from_dict()` Crashes on Missing Fields
- **File**: `src/models.py:106-108`
- **Severity**: 🟡 Medium
- **Category**: Error Handling

```python
@classmethod
def from_dict(cls, data):
    return cls(**data)  # KeyError/TypeError if fields missing from old JSON
```

**Problem**: If stored JSON is from an older version and missing fields like `associated_mpns` or `used_in_projects`, the app crashes on startup.

**Fix**: Provide defaults:
```python
@classmethod
def from_dict(cls, data):
    defaults = {
        'value': '', 'footprint': '', 'total_required': 0,
        'current_stock': 0, 'used_in_projects': [],
        'associated_mpns': [], 'last_updated': ''
    }
    defaults.update(data)
    return cls(**{k: v for k, v in defaults.items() if k in cls.__dataclass_fields__})
```

---

### [ ] BUG-015 — Inconsistent `to_order` Calculation in API
- **File**: `src/app.py:654`
- **Severity**: 🟡 Medium
- **Category**: Logic Bug

```python
to_order = max(0, bom_row.qty - stock_info.get('current_stock', 0))
```

**Problem**: Uses a single project's `bom_row.qty` against the **global** master `current_stock`. The master inventory uses `total_required` (summed across all projects). This per-project number doesn't match what the master inventory shows, confusing users.

**Fix**: Either use the aggregated `total_required` from the stock lookup, or clearly label this as "shortage for this project only."

---

### [ ] BUG-016 — Empty Test Files
- **File**: `test/test_aggregator.py`, `test/test_inventory.py`, `test/test_parser.py`
- **Severity**: 🟡 Medium
- **Category**: Testing

**Problem**: All three test files exist but are completely empty (0 bytes). Zero test coverage for critical logic like `Aggregator.aggregate()`, `BOMParser.parse_file()`, and `create_order()`.

**Fix**: Write tests starting with `test_aggregator.py` and `test_parser.py`.

---

### [x] BUG-017 — `Order.estimated_cost` Returns Hardcoded Values ✅ FIXED
- **File**: `src/models.py:132-137`
- **Severity**: 🟡 Medium
- **Category**: Logic Bug

```python
@property
def estimated_cost(self):
    return sum(
        getattr(item, "qty_ordered", 0) * 10  # assume ₹10 per item
        for item in self.line_items
    )
```

**Problem**: Hardcodes ₹10 per item regardless of `unit_price`. If `unit_price` is set on any `OrderLineItem`, it's completely ignored. This is misleading in the UI.

**Fix**:
```python
return sum(
    (item.unit_price or 10) * item.qty_ordered
    for item in self.line_items
)
```

---

### [ ] BUG-018 — Uploaded Files Stored Outside Project Folder
- **File**: `src/app.py:298-336`, `src/app.py:777-1084`
- **Severity**: 🔴 Critical
- **Category**: Architecture Violation

```python
# All upload routes save to static/uploads/ instead of the project folder
upload_folder = os.path.join('static', 'uploads', 'projects')
os.makedirs(upload_folder, exist_ok=True)
file_path = os.path.join(upload_folder, filename)
file.save(file_path)
```

**Problem**: The vision doc states: *"All files uploaded for a project must be stored only inside that project's folder."* But every upload route (images, BOMs, Gerbers, 3D models, mechanical files) saves to `static/uploads/` — completely outside `fabinventory_data/projects/<name>/`. This means:
- Uploaded files are **not tracked by Git** alongside project data
- Collaborators pulling the repo get JSON metadata but **no project files**
- Project folder only contains `bom.json` and `meta.json`, nothing else

The correct location should be `fabinventory_data/projects/<name>/files/` or similar.

**Fix**: Route all project file uploads into `fabinventory_data/projects/<project_name>/` subdirectories. Update `file_manager.py` to create a `files/` directory per project on init.

---

### [x] BUG-019 — Incomplete Order Status Workflow ✅ FIXED
- **File**: `src/models.py:118-169`, `src/inventory_manager.py:78-95`
- **Severity**: 🟠 High
- **Category**: Missing Business Logic

```python
# models.py:122
status: str = "pending"

# inventory_manager.py:90
order.status = "received"

# That's it — only two statuses exist in the code
```

**Problem**: The vision defines a 5-stage order workflow: **Draft → Ordered → Shipped → Received → Cancelled**. But the code only implements two statuses: `"pending"` (used as Draft) and `"received"`. Missing entirely:
- `"ordered"` — order placed with supplier
- `"shipped"` — tracking info, in transit
- `"cancelled"` — cancelled orders

The `receive_order()` function in `inventory_manager.py` doesn't validate that the order is in `"shipped"` state before marking received. It only checks `status != "pending"` — meaning a cancelled order could accidentally be marked received.

**Fix**:
1. Add proper status constants or enum
2. Add state transition validation (`draft→ordered→shipped→received`, `*→cancelled`)
3. Add routes for each status transition
4. Add `tracking_info`, `shipping_info` fields to `Order` model

---

### [x] BUG-020 — No Authentication Despite Login Pages Existing ✅ FIXED
- **File**: `templates/login.html`, `templates/register.html`, `src/app.py`
- **Severity**: 🟠 High
- **Category**: Security / Missing Feature

**Problem**: The vision doc states: *"Users authenticate using their Git provider credentials rather than creating a separate application account."* The app has:
- `login.html` — references GitHub login (`/github`) but no route exists
- `register.html` — has a registration form but no corresponding route
- `user_details.html` — referenced in login but no route exists
- **Zero authentication code** in `app.py` — no login required, no session management, no OAuth flow

The entire app is wide open. Anyone with network access to the local server can modify inventory, delete projects, change git remotes.

**Fix**: Implement GitHub OAuth (or at minimum a simple local password) to protect the app. Flask-Dance or Authlib for OAuth. At bare minimum, protect POST routes with a session check.

---

### [ ] BUG-021 — Dummy/Development Data in Repository
- **File**: `fabinventory_data/` directory
- **Severity**: 🟡 Medium
- **Category**: Release Hygiene

**Problem**: The vision states: *"before every production release, all development-only data, testing records, dummy projects, temporary files, and sample inventory must be completely removed."* Currently the repo contains:
- Sample projects: `Raven`, `Turtle`, `octopus`
- Test orders: `PO-202605-001`, `PO-202605-002`, `PO-202606-001` through `PO-202606-007`
- Pre-populated `electronics.json` inventory
- `next_id.txt` with a non-zero value

These are already committed and tracked in Git.

**Fix**: Create a `make clean` or setup script option that purges all sample data. Add `.gitignore` rules for `fabinventory_data/`. Provide a `--demo` flag in `run.py` to seed sample data for demo purposes, defaulting to empty state.

---

### [ ] BUG-022 — No Supplier Entity / Supplier Management
- **File**: `src/models.py`, `src/inventory_manager.py`
- **Severity**: 🟡 Medium
- **Category**: Missing Data Model

**Problem**: The vision says: *"The system should also maintain supplier information and allow purchase links for components, mechanical parts, PCB fabrication services, and 3D printing materials."* Currently:
- Supplier is just a free-text string in `Order.supplier`
- No `Supplier` model exists
- No supplier list, contact info, purchase links stored anywhere
- No way to reuse suppliers across orders

**Fix**: Create a `Supplier` dataclass with fields like `name`, `contact`, `website`, `component_categories`, etc. Store suppliers in `fabinventory_data/suppliers/`. Add supplier management UI.

---

## 📊 Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 8 |
| 🟠 High | 6 |
| 🟡 Medium | 8 |
| **Total** | **22** |

**Recommended fix order**:
1. BUG-001 — Secret key (fast security win)
2. BUG-005 — XSS (user data safety)
3. BUG-004 — CSRF (form security)
4. BUG-006 — Path traversal (file safety)
5. BUG-018 — File storage location (architectural — do before you add more features)
6. BUG-003 — ID race condition (data integrity)
7. BUG-007 — github_links data loss
8. BUG-010 — Broken API serialization
9. BUG-008 — Order ID collision
10. BUG-009 — Stock validation
11. BUG-011 — Bare except
12. BUG-020 — Authentication
13. BUG-019 — Order workflow
14. BUG-012 → BUG-013 → BUG-014 → BUG-002 → BUG-015 → BUG-021 → BUG-022 → BUG-016 → BUG-017
