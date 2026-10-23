"""Projects Flask Blueprint — /project/* routes."""
import os
import io
import re
import zipfile
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    flash,
    Response,
    send_from_directory,
    abort,
    current_app,
)
from werkzeug.utils import secure_filename
import pandas as pd

from src.core import state, login_required
from src.bom_parser import BOMParser
from src.models import BomRow

project_bp = Blueprint('project', __name__)


def _next_image_number(image_dir: Path, project_name: str) -> int:
    """Next free '<project>_img_<n>' number across ALL extensions."""
    pattern = re.compile(rf"^{re.escape(project_name)}_img_(\d+)\.[^.]+$")
    max_n = 0
    if image_dir.exists():
        for f in image_dir.iterdir():
            m = pattern.match(f.name)
            if m:
                max_n = max(max_n, int(m.group(1)))
    return max_n + 1


def _next_project_image_name(project_name: str, ext: str) -> str:
    """Return '<project>_img_<n>.<ext>' with the next free number,
    so every uploaded image gets a predictable, project-scoped name."""
    images_dir = Path(state.data_path) / "projects" / project_name / "images"
    n = _next_image_number(images_dir, project_name)
    return f"{project_name}_img_{n}{ext}"


def _next_pcb_image_name(project_name: str, ext: str) -> str:
    """Same numbering scheme, but scoped to the project's pcb_images dir."""
    pcb_dir = Path(state.data_path) / "projects" / project_name / "pcb_images"
    n = _next_image_number(pcb_dir, project_name)
    return f"{project_name}_img_{n}{ext}"


# ── Project detail ────────────────────────────────────────────────


@project_bp.route('/<name>')
@login_required
def project_detail(name):
    """View project details"""
    if not state.init_app():
        return redirect(url_for('main.setup'))

    project = state.project_manager.get_project(name)
    if not project:
        flash(f'Project "{name}" not found', 'error')
        return redirect(url_for('main.projects'))

    summary = state.project_manager.get_project_summary(name)
    print3d_rows = []
    mechanical_rows = []
    pcb_rows = []

    data_root = Path(state.data_path) / "projects" / name

    if project.print3d_bom:
        full_path = data_root / project.print3d_bom
        if full_path.exists():
            try:
                print3d_rows = BOMParser.parse_file(str(full_path), bom_type="3dprint")
            except Exception as e:
                print("3D BOM ERROR:", e)

    if project.mechanical_bom:
        full_path = data_root / project.mechanical_bom
        if full_path.exists():
            try:
                mechanical_rows = BOMParser.parse_file(str(full_path), bom_type="mechanical")
            except Exception as e:
                print("MECHANICAL BOM ERROR:", e)

    if project.pcb_bom:
        full_path = data_root / project.pcb_bom
        if full_path.exists():
            try:
                pcb_rows = BOMParser.parse_file(str(full_path), bom_type="pcb")
            except Exception as e:
                print("PCB BOM ERROR:", e)

    # ── Gerber file listing ────────────────────────────────────
    gerber_files = []
    if project.pcb_gerber_folder:
        gerber_dir = Path(state.data_path) / "projects" / name / project.pcb_gerber_folder
        if gerber_dir.exists():
            gerber_exts = (".gbr", ".gbrjob", ".drl", ".nc")
            gerber_files = sorted(
                [
                    {
                        "name": f.name,
                        "path": str(f.relative_to(Path(state.data_path) / "projects" / name)),
                    }
                    for f in gerber_dir.rglob("*")
                    if f.suffix.lower() in gerber_exts and f.is_file()
                ],
                key=lambda x: x["name"].lower(),
            )

    # ── Per-category stats for the cards under the project name ──
    # (they must follow the active tab, not always show electronics)
    def _rows_total(rows):
        return sum(int(r.get('quantity', 0)) for r in rows)

    elec_placed = [r for r in project.bom if r.is_active()]
    elec_dnp = [r for r in project.bom if r.dnp]

    tab_stats = {
        'electrical': {
            'total_lines': len(project.bom),
            'dnp_lines': len(elec_dnp),
            'placed_lines': len(elec_placed),
            'total_qty': sum(r.qty for r in project.bom),
            'dnp_qty': sum(r.qty for r in elec_dnp),
            'placed_qty': sum(r.qty for r in elec_placed),
        },
        'mechanical': {
            'lines': len(mechanical_rows),
            'qty': _rows_total(mechanical_rows),
        },
        'pcb': {
            'lines': len(pcb_rows),
            'qty': _rows_total(pcb_rows),
        },
        '3dprint': {
            'lines': len(print3d_rows),
            'qty': _rows_total(print3d_rows),
        },
    }

    return render_template(
        'project_details.html',
        project=project,
        summary=summary,
        tab_stats=tab_stats,
        print3d_rows=print3d_rows,
        mechanical_rows=mechanical_rows,
        pcb_rows=pcb_rows,
        gerber_files=gerber_files,
    )


# ── Create project ────────────────────────────────────────────────


@project_bp.route('/create', methods=['POST'])
@login_required
def create_project():
    """Create a new project"""
    if not state.init_app():
        return jsonify({'error': 'App not initialized'}), 500

    name = request.form.get('name')
    description = request.form.get('description', '')

    try:
        # Step 1: Create project
        project = state.project_manager.create_project(name, description)

        if project:
            # Step 2: Handle BOM upload (optional)
            bom_file = request.files.get('bom_file')

            if bom_file and bom_file.filename != "":
                filename = secure_filename(bom_file.filename)
                filepath = current_app.config['UPLOAD_FOLDER'] / filename
                bom_file.save(filepath)

                try:
                    # Use your existing parser system
                    state.project_manager.update_project_bom(name, str(filepath))
                except Exception as e:
                    flash(f'Error parsing BOM: {str(e)}', 'error')
                finally:
                    # Clean temp file
                    if filepath.exists():
                        filepath.unlink()

            # Step 3: Handle project image (optional)
            image_file = request.files.get('project_image')
            if image_file and image_file.filename != "":
                ext = Path(image_file.filename).suffix.lower()
                img_name = _next_project_image_name(name, ext)
                state.project_manager.file_manager.save_project_file(
                    name, 'images', img_name, image_file.read()
                )
                project.image = img_name
                state.project_manager.file_manager.save_project(project)

            # Step 4: Refresh all inventories
            projects = list(state.project_manager.projects.values())
            state.inventory_manager.update_inventory(projects)
            state.inventory_manager.update_non_elec_inventory(projects)

            # Step 4: Git commit
            if state.git_manager:
                state.git_manager.commit(f"Created project '{name}'")

            flash(f'Project "{name}" created successfully!', 'success')

        else:
            flash(f'Failed to create project "{name}"', 'error')

    except ValueError as e:
        flash(str(e), 'error')

    return redirect(url_for('main.projects'))


# ── Upload BOM (electrical) ──────────────────────────────────────


@project_bp.route('/<name>/upload', methods=['POST'])
@login_required
def upload_bom(name):
    """Upload BOM file to project"""
    if not state.init_app():
        return jsonify({'error': 'App not initialized'}), 500

    if 'bom_file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('project.project_detail', name=name))

    file = request.files['bom_file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('project.project_detail', name=name))

    if file:
        # Save uploaded file
        filename = secure_filename(file.filename)
        filepath = current_app.config['UPLOAD_FOLDER'] / filename
        file.save(filepath)

        try:
            # Parse first so problem rows are shown to the user, not swallowed
            _, parse_warnings = BOMParser.parse_file_with_warnings(str(filepath))
            for w in parse_warnings[:10]:
                flash(w, 'warning')
            if len(parse_warnings) > 10:
                flash(f'…and {len(parse_warnings) - 10} more row(s) skipped', 'warning')

            # Parse and update BOM
            updated = state.project_manager.update_project_bom(name, str(filepath))
            if updated:
                # Refresh all inventories
                projects = list(state.project_manager.projects.values())
                state.inventory_manager.update_inventory(projects)
                state.inventory_manager.update_non_elec_inventory(projects)

                # Commit to Git
                if state.git_manager:
                    state.git_manager.commit(f"Updated BOM for project '{name}'")

                flash(f'BOM uploaded successfully to "{name}"!', 'success')
            else:
                flash(f'Failed to upload BOM to "{name}"', 'error')
        except Exception as e:
            flash(f'Error parsing BOM: {str(e)}', 'error')
        finally:
            # Clean up uploaded file
            if filepath.exists():
                filepath.unlink()

    return redirect(url_for('project.project_detail', name=name))


# ── Edit BOM in place ────────────────────────────────────────────


def _parse_bom_edit_payload(bom_rows, payload):
    """Validate an in-place BOM edit payload into a fresh list of BomRow.

    Rows posted by the browser replace the current BOM. ``orig_index``
    links a row back to its old position so fields the editor does not
    show (LCSC part number / supplier / SKU) survive the edit. A row with
    no reference, value or footprint is treated as blank and dropped.
    Raises ValueError with a user-readable message.
    """
    if not isinstance(payload, dict):
        raise ValueError('Expected a JSON object')
    posted = payload.get('rows')
    if not isinstance(posted, list):
        raise ValueError('Expected a list of BOM rows')
    if len(posted) > 10000:
        raise ValueError('Too many BOM rows (max 10000)')

    def text(row, key, max_len):
        value = row.get(key, '')
        if value is None:
            return ''
        value = str(value).strip()
        if len(value) > max_len:
            raise ValueError(f'{key} is too long (max {max_len} characters)')
        return value

    def number(row, key, default):
        value = row.get(key, default)
        if value is None or value == '':
            return default
        try:
            return max(0, int(float(value)))
        except (TypeError, ValueError):
            raise ValueError(f'{key} must be a number')

    new_rows = []
    for pos, row in enumerate(posted):
        if not isinstance(row, dict):
            raise ValueError(f'Row {pos + 1} is malformed')

        orig = row.get('orig_index')
        base = None
        if isinstance(orig, int) and 0 <= orig < len(bom_rows):
            base = bom_rows[orig]

        reference = text(row, 'reference', 500)
        value = text(row, 'value', 200)
        footprint = text(row, 'footprint', 200)
        if not reference and not value and not footprint:
            continue  # blank line — same outcome as deleting it

        dnp = row.get('dnp')
        if isinstance(dnp, str):
            dnp = dnp.strip().lower() in ('1', 'true', 'yes', 'on', 'x')
        dnp = bool(dnp)

        new_rows.append(BomRow(
            si_no=number(row, 'si_no', pos + 1),
            reference=reference,
            value=value,
            footprint=footprint,
            manufacturer_part_number=text(
                row, 'manufacturer_part_number', 500
            ),
            manufacturer_name=text(row, 'manufacturer_name', 500),
            manufacturer_part_number_lcsc=(
                base.manufacturer_part_number_lcsc if base else None
            ),
            manufacturer_name_lcsc=(
                base.manufacturer_name_lcsc if base else None
            ),
            lcsc_sku=base.lcsc_sku if base else None,
            qty=number(row, 'qty', 0),
            dnp=dnp,
            dnp_raw='X' if dnp else '',
        ))

    return new_rows


@project_bp.route('/<name>/bom/edit', methods=['POST'])
@login_required
def edit_bom(name):
    """Save an edited electrical BOM without a download / re-upload cycle."""
    if not state.init_app():
        return jsonify({'success': False, 'error': 'App not initialized'}), 500

    project = state.project_manager.get_project(name)
    if not project:
        return jsonify({'success': False, 'error': 'Project not found'}), 404

    try:
        new_bom = _parse_bom_edit_payload(
            project.bom, request.get_json(silent=True)
        )
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400

    old_bom = project.bom
    project.bom = new_bom
    project.updated_at = datetime.now().isoformat()
    if not state.project_manager.file_manager.save_project(project):
        # Keep memory and disk in agreement if the write failed.
        project.bom = old_bom
        return (
            jsonify({'success': False, 'error': 'Could not save the BOM file'}),
            500,
        )

    # Keep master inventory (and therefore orders) in sync with the edit.
    projects = list(state.project_manager.projects.values())
    state.inventory_manager.update_inventory(projects)
    state.inventory_manager.update_non_elec_inventory(projects)

    if state.git_manager:
        state.git_manager.commit(f"Edited BOM for project '{name}'")

    flash(f'BOM updated — {len(project.bom)} line(s) saved', 'success')
    return jsonify({'success': True, 'count': len(project.bom)})


# ── Upload project image ─────────────────────────────────────────


@project_bp.route('/<name>/upload-image', methods=['POST'])
@login_required
def upload_project_image(name):

    project = state.project_manager.get_project(name)

    if not project:
        flash("Project not found", "danger")
        return redirect(url_for('main.projects'))

    if 'project_image' not in request.files:
        flash("No image uploaded", "danger")
        return redirect(url_for('project.project_detail', name=name))

    file = request.files['project_image']

    if file.filename == '':
        flash("No selected image", "danger")
        return redirect(url_for('project.project_detail', name=name))

    # SAVE TO PROJECT FOLDER — renamed to <project>_img_<n>.<ext>
    ext = Path(file.filename).suffix.lower()
    filename = _next_project_image_name(name, ext)
    state.project_manager.file_manager.save_project_file(
        name, 'images', filename, file.read()
    )

    # SAVE IMAGE NAME INTO PROJECT
    project.image = filename

    # SAVE PROJECT METADATA
    state.project_manager.file_manager.save_project(project)

    flash("Project image uploaded successfully!", "success")

    return redirect(url_for('project.project_detail', name=name))


# ── Delete project ────────────────────────────────────────────────


@project_bp.route('/<name>/delete', methods=['POST'])
@login_required
def delete_project(name):
    """Delete a project"""
    if not state.init_app():
        return jsonify({'error': 'App not initialized'}), 500

    if state.project_manager.delete_project(name):
        # Refresh all inventories
        projects = list(state.project_manager.projects.values())
        state.inventory_manager.update_inventory(projects)
        state.inventory_manager.update_non_elec_inventory(projects)

        # Commit to Git
        if state.git_manager:
            state.git_manager.commit(f"Deleted project '{name}'")

        flash(f'Project "{name}" deleted!', 'success')
    else:
        flash(f'Failed to delete project "{name}"', 'error')

    return redirect(url_for('main.projects'))


# ── Export BOM ────────────────────────────────────────────────────


@project_bp.route('/<name>/export')
@login_required
def export_bom(name):
    """Export project BOM as CSV"""
    if not state.init_app():
        return jsonify({'error': 'App not initialized'}), 500

    project = state.project_manager.get_project(name)
    if not project:
        flash(f'Project "{name}" not found', 'error')
        return redirect(url_for('main.projects'))

    # Build CSV from project BOM
    data = []
    for row in project.bom:
        data.append({
            'SI.No': row.si_no,
            'Reference': row.reference,
            'Value': row.value,
            'Footprint': row.footprint,
            'Manufacturer_Part_Number': row.manufacturer_part_number,
            'Manufacturer_Name': row.manufacturer_name,
            'Qty': row.qty,
            'DNP': 'X' if row.dnp else ''
        })

    df = pd.DataFrame(data)
    output = io.StringIO()
    df.to_csv(output, index=False)

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={name}_bom.csv'}
    )


# ── Upload 3D print BOM ──────────────────────────────────────────


@project_bp.route('/<name>/upload_3d_bom', methods=['POST'])
@login_required
def upload_3d_bom(name):

    project = state.project_manager.get_project(name)

    if not project:
        flash('Project not found', 'danger')
        return redirect(url_for('main.projects'))

    file = request.files.get('print3d_file')

    if not file or file.filename == '':
        flash('No file selected', 'warning')
        return redirect(
            url_for(
                'project.project_detail',
                name=name,
                tab='3dprint'
            )
        )

    filename = secure_filename(file.filename)

    saved_path = state.project_manager.file_manager.save_project_file(
        name, '3dprint', filename, file.read()
    )

    # Validate the file and surface row warnings to the user
    try:
        _, parse_warnings = BOMParser.parse_file_with_warnings(
            str(saved_path), bom_type='3dprint'
        )
    except Exception as e:
        saved_path.unlink(missing_ok=True)
        flash(f'BOM rejected — {e}', 'error')
        return redirect(url_for('project.project_detail', name=name, tab='3dprint'))

    for w in parse_warnings[:10]:
        flash(w, 'warning')
    if len(parse_warnings) > 10:
        flash(f'…and {len(parse_warnings) - 10} more row(s) skipped', 'warning')

    # SAVE RELATIVE PATH IN PROJECT (from project dir)
    project.print3d_bom = f"3dprint/{filename}"

    state.project_manager.file_manager.save_project(project)
    state.project_manager.projects[name] = project

    # Refresh non-elec inventory
    projects = list(state.project_manager.projects.values())
    state.inventory_manager.update_non_elec_inventory(projects)
    if state.git_manager:
        state.git_manager.commit(f"Updated 3D print BOM for '{name}'")

    flash('3D BOM uploaded successfully', 'success')

    return redirect(url_for('project.project_detail', name=name, tab='3dprint'))


# ── Upload mechanical BOM ────────────────────────────────────────


@project_bp.route('/<name>/upload_mechanical_bom', methods=['POST'])
@login_required
def upload_mechanical_bom(name):

    project = state.project_manager.get_project(name)

    if not project:
        flash('Project not found', 'danger')
        return redirect(url_for('main.projects'))

    file = request.files.get('mechanical_file')

    if not file or file.filename == '':
        flash('No file selected', 'warning')
        return redirect(
            url_for(
                'project.project_detail',
                name=name,
                tab='mechanical'
            )
        )

    filename = secure_filename(file.filename)

    saved_path = state.project_manager.file_manager.save_project_file(
        name, 'mechanical', filename, file.read()
    )

    # Validate the file and surface row warnings to the user
    try:
        _, parse_warnings = BOMParser.parse_file_with_warnings(
            str(saved_path), bom_type='mechanical'
        )
    except Exception as e:
        saved_path.unlink(missing_ok=True)
        flash(f'BOM rejected — {e}', 'error')
        return redirect(url_for('project.project_detail', name=name, tab='mechanical'))

    for w in parse_warnings[:10]:
        flash(w, 'warning')
    if len(parse_warnings) > 10:
        flash(f'…and {len(parse_warnings) - 10} more row(s) skipped', 'warning')

    project.mechanical_bom = f"mechanical/{filename}"

    state.project_manager.file_manager.save_project(project)
    state.project_manager.projects[name] = project

    # Refresh non-elec inventory
    projects = list(state.project_manager.projects.values())
    state.inventory_manager.update_non_elec_inventory(projects)
    if state.git_manager:
        state.git_manager.commit(f"Updated mechanical BOM for '{name}'")

    flash('Mechanical BOM uploaded successfully', 'success')

    return redirect(url_for('project.project_detail', name=name, tab='mechanical'))


# ── Upload PCB BOM ───────────────────────────────────────────────


@project_bp.route('/<name>/upload_pcb_bom', methods=['POST'])
@login_required
def upload_pcb_bom(name):

    project = state.project_manager.get_project(name)

    if not project:
        flash('Project not found', 'danger')
        return redirect(url_for('main.projects'))

    file = request.files.get('pcb_file')

    if not file or file.filename == '':
        flash('No file selected', 'warning')
        return redirect(
            url_for(
                'project.project_detail',
                name=name,
                tab='pcb'
            )
        )

    filename = secure_filename(file.filename)

    saved_path = state.project_manager.file_manager.save_project_file(
        name, 'pcb', filename, file.read()
    )

    # Validate the file and surface row warnings to the user
    try:
        _, parse_warnings = BOMParser.parse_file_with_warnings(
            str(saved_path), bom_type='pcb'
        )
    except Exception as e:
        saved_path.unlink(missing_ok=True)
        flash(f'BOM rejected — {e}', 'error')
        return redirect(url_for('project.project_detail', name=name, tab='pcb'))

    for w in parse_warnings[:10]:
        flash(w, 'warning')
    if len(parse_warnings) > 10:
        flash(f'…and {len(parse_warnings) - 10} more row(s) skipped', 'warning')

    project.pcb_bom = f"pcb/{filename}"

    state.project_manager.file_manager.save_project(project)
    state.project_manager.projects[name] = project

    # Refresh non-elec inventory
    projects = list(state.project_manager.projects.values())
    state.inventory_manager.update_non_elec_inventory(projects)
    if state.git_manager:
        state.git_manager.commit(f"Updated PCB BOM for '{name}'")

    flash('PCB BOM uploaded successfully', 'success')

    return redirect(url_for('project.project_detail', name=name, tab='pcb'))


# ── Upload 3D image ──────────────────────────────────────────────


@project_bp.route('/<name>/upload_3d_image', methods=['POST'])
@login_required
def upload_3d_image(name):

    project = state.project_manager.get_project(name)

    if not project:
        flash('Project not found', 'danger')
        return redirect(url_for('main.projects'))

    file = request.files.get('model_3d_file')

    if not file or file.filename == '':
        flash('No image selected', 'warning')

        return redirect(
            url_for(
                'project.project_detail',
                name=name,
                tab='3dprint'
            )
        )

    filename = secure_filename(file.filename)

    saved_path = state.project_manager.file_manager.save_project_file(
        name, '3d_models', filename, file.read()
    )

    project.model_3d_file = f"3d_models/{filename}"

    state.project_manager.file_manager.save_project(project)
    state.project_manager.projects[name] = project

    flash('3D preview uploaded successfully', 'success')

    return redirect(url_for('project.project_detail', name=name, tab='3dprint'))


# ── Upload Gerber ZIP ─────────────────────────────────────────────


@project_bp.route("/<name>/upload_gerber_zip", methods=["POST"])
@login_required
def upload_gerber_zip(name):

    project = state.project_manager.get_project(name)

    if not project:
        flash("Project not found", "danger")
        return redirect(url_for("main.dashboard"))

    if "gerber_zip" not in request.files:
        flash("No file uploaded", "danger")
        return redirect(url_for("project.project_detail", name=name, tab="pcb"))

    file = request.files["gerber_zip"]

    if file.filename == "":
        flash("No file selected", "danger")
        return redirect(url_for("project.project_detail", name=name, tab="pcb"))

    filename = secure_filename(file.filename)
    zip_data = file.read()

    # Save the ZIP
    state.project_manager.file_manager.save_project_file(
        name, "gerbers", filename, zip_data
    )
    project.pcb_gerber_zip = f"gerbers/{filename}"

    # Extract ZIP to a subfolder
    import io as io_mod
    extract_base = filename.rsplit(".", 1)[0]  # strip .zip
    extract_dir_name = f"gerbers/{extract_base}"
    project_dir = state.file_manager._project_dir(name)
    extract_path = project_dir / extract_dir_name
    extract_path.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(io_mod.BytesIO(zip_data)) as zf:
            zf.extractall(extract_path)
    except zipfile.BadZipFile:
        flash("Uploaded file is not a valid ZIP archive.", "error")
        return redirect(url_for("project.project_detail", name=name, tab="pcb"))

    # Validate: check for Gerber files
    gerber_exts = (".gbr", ".gbrjob", ".drl", ".nc")
    gerber_files = sorted(
        f.relative_to(extract_path)
        for f in extract_path.rglob("*")
        if f.suffix.lower() in gerber_exts and f.is_file()
    )

    if not gerber_files:
        flash(
            "ZIP extracted but no Gerber files (.gbr, .drl) found inside. "
            "Is this a valid manufacturing ZIP?",
            "warning",
        )
    else:
        project.pcb_gerber_folder = extract_dir_name
        flash(
            f"Gerber ZIP uploaded — {len(gerber_files)} Gerber file(s) found.",
            "success",
        )

    project.updated_at = datetime.now().isoformat()
    state.project_manager.file_manager.save_project(project)

    # Refresh PCB inventory so this board appears in Inventory → PCB tab
    projects = list(state.project_manager.projects.values())
    state.inventory_manager.update_non_elec_inventory(projects)
    if state.git_manager:
        state.git_manager.commit(f"Updated Gerber files for '{name}'")

    return redirect(url_for("project.project_detail", name=name, tab="pcb"))


# ── Download Gerber ZIP ────────────────────────────────────────────


@project_bp.route('/<name>/download_gerber')
@login_required
def download_gerber(name):
    from flask import send_from_directory

    project = state.file_manager.load_project(name)
    if not project or not project.pcb_gerber_zip:
        abort(404)

    # Use state.data_path (relative to CWD) → resolve to absolute
    data_root = Path(state.data_path).resolve()
    project_dir = data_root / "projects" / name
    gerber_path = project_dir / project.pcb_gerber_zip

    if not gerber_path.exists():
        abort(404)

    return send_from_directory(
        directory=str(gerber_path.parent),
        path=gerber_path.name,
        as_attachment=True,
        download_name=gerber_path.name,
    )


# ── Save PCB repo link ────────────────────────────────────────────


@project_bp.route(
    "/<name>/save_pcb_repo",
    methods=["POST"]
)
@login_required
def save_pcb_repo(name):

    project = state.project_manager.get_project(name)

    if not project:
        flash("Project not found", "danger")

        return redirect(url_for("main.projects"))

    repo_name = request.form.get(
        "pcb_repo_name",
        ""
    ).strip()

    repo_link = request.form.get(
        "pcb_repo_link",
        ""
    ).strip()

    # ======================================
    # APPEND NEW REPO
    # ======================================

    if repo_name and repo_link:

        project.github_links.append({

            "name": repo_name,

            "url": repo_link

        })

    # ======================================
    # SAVE PROJECT
    # ======================================

    state.project_manager.file_manager.save_project(project)

    state.project_manager.projects[name] = project

    flash(
        "PCB repository link saved",
        "success"
    )

    return redirect(
        url_for(
            "project.project_detail",
            name=name,
            tab="pcb"
        )
    )


# ── Upload PCB image ──────────────────────────────────────────────


@project_bp.route("/<name>/upload_pcb_image", methods=["POST"])
@login_required
def upload_pcb_image(name):

    project = state.project_manager.get_project(name)

    if not project:
        flash("Project not found", "danger")
        return redirect(url_for("main.dashboard"))

    if "pcb_image" not in request.files:
        flash("No file uploaded", "danger")
        return redirect(url_for("project.project_detail", name=name, tab="pcb"))

    file = request.files["pcb_image"]

    if file.filename == "":
        flash("No file selected", "danger")
        return redirect(url_for("project.project_detail", name=name, tab="pcb"))

    # Renamed to <project>_img_<n>.<ext> and kept in a LIST so the PCB tab
    # can show a slide-show when there are several images
    ext = Path(file.filename).suffix.lower()
    filename = _next_pcb_image_name(name, ext)

    # SAVE INSIDE PROJECT FOLDER
    state.project_manager.file_manager.save_project_file(
        name,
        "pcb_images",
        filename,
        file.read()
    )

    rel_path = f"pcb_images/{filename}"

    # SAVE RELATIVE PATH(S)
    if not hasattr(project, 'pcb_images') or project.pcb_images is None:
        project.pcb_images = []
    if rel_path not in project.pcb_images:
        project.pcb_images.append(rel_path)
    if not project.pcb_image:
        project.pcb_image = rel_path

    project.updated_at = datetime.now().isoformat()

    state.project_manager.file_manager.save_project(project)

    flash("PCB image uploaded successfully", "success")

    return redirect(url_for("project.project_detail", name=name, tab="pcb"))


# ── Serve PCB image ───────────────────────────────────────────────


@project_bp.route("/<name>/pcb_image/<filename>")
@login_required
def serve_pcb_image(name, filename):

    project_dir = state.project_manager.file_manager._project_dir(name)

    image_dir = os.path.join(
        project_dir,
        "pcb_images"
    )

    return send_from_directory(
        image_dir,
        filename
    )


# ── Remove PCB image ──────────────────────────────────────────────


@project_bp.route(
    '/<name>/remove_pcb_image',
    methods=['POST']
)
@login_required
def remove_pcb_image(name):

    project = state.project_manager.get_project(name)

    if not project:
        flash("Project not found", "danger")
        return redirect(url_for('main.projects'))

    project_dir = state.project_manager.file_manager._project_dir(name)

    # All images known to this project (single image + gallery list)
    all_images = list(project.pcb_images or [])
    if project.pcb_image and project.pcb_image not in all_images:
        all_images.append(project.pcb_image)

    # `image` names the exact slide to delete. Without it (old forms,
    # bookmarks) remove everything, but per-image is what the UI uses.
    target = (request.form.get('image') or '').strip()

    if target:
        if target not in all_images:
            flash("Image not found on this project", "error")
            return redirect(
                url_for('project.project_detail', name=name, tab='pcb')
            )

        image_path = os.path.join(project_dir, target)
        if os.path.exists(image_path):
            os.remove(image_path)

        project.pcb_images = [
            p for p in (project.pcb_images or []) if p != target
        ]
        if project.pcb_image == target:
            project.pcb_image = (
                project.pcb_images[0] if project.pcb_images else None
            )
        flash("PCB image removed", "success")
    else:
        for rel_path in all_images:
            image_path = os.path.join(project_dir, rel_path)
            if os.path.exists(image_path):
                os.remove(image_path)
        project.pcb_image = None
        project.pcb_images = []
        flash("All PCB images removed", "success")

    state.file_manager.save_project(project)

    return redirect(
        url_for(
            'project.project_detail',
            name=name,
            tab='pcb'
        )
    )


# ── Serve project file ────────────────────────────────────────────


@project_bp.route('/<name>/files/<path:filepath>')
@login_required
def serve_project_file(name, filepath):
    from flask import send_from_directory

    data_root = Path(state.data_path).resolve()
    project_dir = str(data_root / "projects" / name)

    return send_from_directory(project_dir, filepath)
