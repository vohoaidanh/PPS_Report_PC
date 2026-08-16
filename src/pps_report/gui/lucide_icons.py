"""
Loads flat Lucide (ISC-licensed) SVG icons, recolored to match the current
theme (Lucide SVGs use stroke="currentColor", substituted at load time).
"""

import os

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

from pps_report.utils.path_helper import resource_path

_ICON_DIR = os.path.join("gui", "icons", "lucide")
_cache = {}


def load_icon(name: str, color: str, size: int = 24) -> QIcon:
    key = (name, color, size)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    svg_path = resource_path(os.path.join(_ICON_DIR, f"{name}.svg"))
    with open(svg_path, "r", encoding="utf-8") as f:
        svg_data = f.read().replace("currentColor", color)

    renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    icon = QIcon(pixmap)
    _cache[key] = icon
    return icon
