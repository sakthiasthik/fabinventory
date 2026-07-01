"""Setup script for FabInventory"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="fabinventory",
    version="0.1.0",
    author="Sakthi",
    description="Git-backed inventory and BOM management for hardware engineers",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sakthiasthik/fabinventory",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    package_data={
        "": ["../templates/**/*", "../static/**/*"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Manufacturing",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "flask>=2.3.0",
        "flask-wtf>=1.1.0",
        "wtforms>=3.0.0",
        "pandas>=2.0.0",
        "openpyxl>=3.1.0",
        "gitpython>=3.1.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
        "markdown>=3.4.0",
        "requests>=2.28.0",
    ],
    entry_points={
        "console_scripts": [
            "fabinventory=src.app:main",
        ],
    },
)
