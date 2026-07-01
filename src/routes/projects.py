"""Projects Flask Blueprint — /project/* routes."""
import os
import io
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

project_bp = Blueprint('project', __name__)


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

    return render_template(
        'project_details.html',
        project=project,
        summary=summary,
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

            # Step 3: Refresh all inventories
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

    # SAVE TO PROJECT FOLDER
    filename = secure_filename(file.filename)
    saved = state.project_manager.file_manager.save_project_file(
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

    filename = secure_filename(file.filename)

    # SAVE INSIDE PROJECT FOLDER
    state.project_manager.file_manager.save_project_file(
        name,
        "pcb_images",
        filename,
        file.read()
    )

    # SAVE RELATIVE PATH
    project.pcb_image = f"pcb_images/{filename}"

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

    if project.pcb_image:

        project_dir = state.project_manager.file_manager._project_dir(name)

        image_path = os.path.join(
            project_dir,
            project.pcb_image
        )

        if os.path.exists(image_path):
            os.remove(image_path)

    project.pcb_image = None

    state.file_manager.save_project(project)

    flash("PCB image removed", "success")

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
