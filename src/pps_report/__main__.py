"""
Tunnel Concrete Thickness Analyzer
===================================

A desktop application for analyzing shotcrete (sprayed concrete) thickness
in tunnel construction using point cloud data.

Features:
- Load and visualize PLY point cloud files with custom distance fields
- Interactive 3D visualization with selection tools
- Calculate surface area and volume based on thickness data
- Generate PDF reports with statistics and histograms

Usage:
    python -m pps_report
"""

import os
import sys
import logging

# Must be set before pyvistaqt/qtpy import anything Qt-related, so qtpy
# binds to PySide6 instead of auto-detecting another binding.
os.environ.setdefault("QT_API", "pyside6")

REQUIRED = [
    "PySide6",
    "pyvista",
    "pyvistaqt",
    "numpy",
    "open3d",
    "matplotlib",
    "scipy",
    "pdfkit",
    "jinja2",
]


def check_dependencies():
    missing = []
    for lib in REQUIRED:
        try:
            __import__(lib)
        except ImportError:
            missing.append(lib)

    if missing:
        print("Missing dependencies:", missing)
        print("Please install with: pip install -e .")
        sys.exit(1)


def main():
    """Main entry point."""
    check_dependencies()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont
    from pps_report.gui.theme import apply_theme

    # Fix cho màn hình 200% vs 100%
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("Jaconequipment - Tunnel Concrete Analyzer")
    app.setOrganizationName("TunnelAnalyzer")

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    apply_theme(app)

    from pps_report.gui.main_window import MainWindow
    window = MainWindow()
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
