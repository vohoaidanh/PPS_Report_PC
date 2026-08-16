"""
Light/Dark theme support — color palettes + QSS generation.
"""

THEMES = {
    "light": {
        "bg_primary":   "#f8fafc",
        "bg_secondary": "#ffffff",
        "bg_tertiary":  "#f1f5f9",
        "border":       "#e2e8f0",
        "accent":       "#2563eb",
        "accent_hover": "#1d4ed8",
        "text_main":    "#0f172a",
        "text_muted":   "#64748b",
        "canvas_bg":    "#f1f5f9",
        "disabled":     "#c3cbd2",
        "success":      "#2f855a",
    },
    "dark": {
        "bg_primary":   "#121418",
        "bg_secondary": "#1a1d24",
        "bg_tertiary":  "#242832",
        "border":       "#2e3440",
        "accent":       "#3b82f6",
        "accent_hover": "#2563eb",
        "text_main":    "#e2e8f0",
        "text_muted":   "#94a3b8",
        "canvas_bg":    "#0a0c10",
        "disabled":     "#3a4150",
        "success":      "#2f855a",
    },
}

_current_theme = "light"


def get_colors(theme: str = None) -> dict:
    return THEMES[theme or _current_theme]


def current_theme() -> str:
    return _current_theme


def build_stylesheet(theme: str) -> str:
    c = THEMES[theme]
    return f"""
* {{
    font-family: "Segoe UI", Arial, sans-serif;
}}

QMainWindow, QDialog, QWidget {{
    background-color: {c['bg_primary']};
    color: {c['text_main']};
}}

QGroupBox {{
    background-color: {c['bg_secondary']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {c['text_main']};
    background-color: transparent;
}}

QPushButton {{
    background-color: {c['accent']};
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 600;
    text-align: left;
}}
QPushButton:hover {{ background-color: {c['accent_hover']}; }}
QPushButton:pressed {{ background-color: {c['accent_hover']}; }}
QPushButton:disabled {{ background-color: {c['disabled']}; color: {c['bg_tertiary']}; }}
QPushButton:checked {{ background-color: {c['success']}; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {{
    padding: 5px 7px;
    border: 1px solid {c['border']};
    border-radius: 5px;
    background-color: {c['bg_secondary']};
    color: {c['text_main']};
    selection-background-color: {c['accent']};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QTextEdit:focus {{
    border-color: {c['accent']};
}}
QLineEdit:read-only {{
    background-color: {c['bg_primary']};
    color: {c['text_muted']};
}}

QListWidget {{
    border: 1px solid {c['border']};
    border-radius: 6px;
    background-color: {c['bg_secondary']};
    outline: none;
}}
QListWidget::item {{
    padding: 4px 2px;
    border-radius: 4px;
}}
QListWidget::item:selected {{
    background-color: {c['accent']};
    color: white;
}}
QListWidget::item:hover {{
    background-color: {c['bg_tertiary']};
}}

QProgressBar {{
    border: 1px solid {c['border']};
    border-radius: 5px;
    text-align: center;
    background-color: {c['bg_secondary']};
    color: {c['text_main']};
}}
QProgressBar::chunk {{
    background-color: {c['accent']};
    border-radius: 5px;
}}

QStatusBar {{
    background-color: {c['bg_secondary']};
    color: {c['text_muted']};
    border-top: 1px solid {c['border']};
}}

QToolBar {{
    background-color: {c['bg_secondary']};
    border-bottom: 1px solid {c['border']};
    spacing: 6px;
    padding: 6px;
}}
QToolBar QToolButton {{
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px;
    background-color: {c['bg_tertiary']};
}}
QToolBar QToolButton:hover {{
    border-color: {c['accent']};
    background-color: {c['bg_secondary']};
}}
QToolBar QToolButton:checked {{
    background-color: {c['accent']};
    color: white;
}}

QMenuBar {{
    background-color: {c['bg_secondary']};
    border-bottom: 1px solid {c['border']};
}}
QMenuBar::item:selected {{ background-color: {c['bg_tertiary']}; }}

QMenu {{
    background-color: {c['bg_secondary']};
    border: 1px solid {c['border']};
}}
QMenu::item {{ padding: 6px 20px; }}
QMenu::item:selected {{ background-color: {c['accent']}; color: white; }}

QScrollBar:vertical {{
    background: {c['bg_primary']};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {c['border']};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {c['text_muted']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QToolTip {{
    background-color: {c['text_main']};
    color: {c['bg_primary']};
    border: none;
    padding: 4px 8px;
    border-radius: 4px;
}}

QSlider::groove:horizontal {{
    height: 4px;
    background: {c['border']};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {c['accent']};
    width: 14px;
    margin: -6px 0;
    border-radius: 7px;
}}
"""


def apply_theme(app, theme: str = "light"):
    global _current_theme
    _current_theme = theme
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet(theme))
