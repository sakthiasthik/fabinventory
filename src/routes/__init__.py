"""
FabInventory — Flask Blueprints
================================

Route organisation::

    main       —  /login, /setup, /dashboard, /projects  (auth + core pages)
    projects   —  /project/*  (detail, BOM uploads, images, Gerber, etc.)
    inventory  —  /inventory/*  (view, stock, import)
    orders     —  /order/*  (create, receive, summary)
    api        —  /api/*  (JSON REST endpoints)
    git_routes —  /git-settings  (commit, push, pull, remote config)

Each blueprint imports ``state``, ``login_required``, and ``api_login_required``
from ``src.app``.
"""
