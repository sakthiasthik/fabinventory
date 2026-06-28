#!/usr/bin/env python3

#!/usr/bin/env python3
"""Run FabInventory web application"""

import subprocess
import sys
import os

# ====================================
# AUTO INSTALL REQUIRED PACKAGES
# ====================================

required_packages = {
    "pandas": "pandas",
    "openpyxl": "openpyxl",
    "git": "gitpython",
    "dotenv": "python-dotenv",
    "requests": "requests",
    "flask": "flask",
    "flask_wtf": "flask-wtf",
    "wtforms": "wtforms",
    "markdown": "markdown",
    "pydantic": "pydantic"
}



# Run dependency check only once
if os.environ.get("WERKZEUG_RUN_MAIN") != "true":

    print("\nChecking required dependencies...\n")

    for import_name, pip_name in required_packages.items():

        try:
            __import__(import_name)
            print(f"[OK] {pip_name}")

        except ImportError:

            print(f"[INSTALLING] {pip_name}")

            subprocess.check_call([
                sys.executable,
                "-m",
                "pip",
                "install",
                pip_name
            ])

    print("\nAll dependencies are ready.\n")
# ====================================
# ADD PROJECT ROOT TO PATH
# ====================================

sys.path.insert(0, os.path.dirname(__file__))

# ====================================
# START APPLICATION
# ====================================

from src.app import main

if __name__ == '__main__':
    main()
# """Run FabInventory web application"""

# import sys
# import os

# # Add src to path
# sys.path.insert(0, os.path.dirname(__file__))

# from src.app import main

# if __name__ == '__main__':
#     main()