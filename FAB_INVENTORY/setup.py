"""Setup script for FabInventory"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="fabinventory",
    version="1.0.0",
    author="FabInventory Team",
    description="Git-backed inventory and BOM management for hardware engineers",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/fabinventory",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Manufacturing",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Office/Business :: Scheduling",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pandas>=2.0.0",
        "openpyxl>=3.1.0",
        "gitpython>=3.1.0",
        "python-dotenv>=1.0.0",
        "click>=8.1.0",
        "rich>=13.0.0",
        "pydantic>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "fabinventory=main:main",
        ],
    },
)