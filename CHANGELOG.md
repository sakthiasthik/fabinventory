# Changelog

All notable changes to FabInventory will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased]

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
* Project category tabs:

  * Electrical
  * Mechanical
  * PCB
  * 3D Print
* Print Information card for 3D projects
* 3D preview upload section
* Gerber ZIP upload success notifications
* PCB repository link persistence in metadata
* Support for:

  * `.stl`
  * `.obj`
  * `.zip`
  * `.csv`
  * `.xlsx`
  * `.xls`

### Changed

* Improved BOM table responsiveness
* Reduced horizontal scrolling in BOM table
* Improved wrapping for long component names
* Reorganized project details page into modular tabs
* Moved upload actions inside category tabs
* Improved table readability and spacing
* Improved upload form consistency across all tabs
* Standardized Mechanical and PCB upload layouts
* Updated Mechanical BOM schema:

  * Added `Mechanical Part Description`
  * Added `Value`
* Updated PCB BOM workflow to support both Gerber ZIPs and repository links
* Improved STL viewer camera positioning and scaling logic
* Improved file path handling using normalized forward slashes

### Fixed

* BOM table text overlap issues
* Header truncation issues
* Manufacturer column visibility problems
* Duplicate dependency installation logs
* Project image persistence after restart
* Table alignment inconsistencies
* Windows path separator issues in saved metadata
* STL model not rendering after reload
* Three.js viewer initialization issues
* Gerber ZIP upload persistence issues
* Metadata save issues for PCB repository links
* Upload form sizing inconsistencies
* Broken file references after restart

### Security

* Added safer dependency checking before startup
* Added secure filename handling for uploads

---

## [0.1.0] - Initial Development

### Added

* Flask-based FabInventory application
* BOM parsing from CSV and Excel
* Inventory calculation system
* Project management support
* Git integration support
* Basic Bootstrap UI
