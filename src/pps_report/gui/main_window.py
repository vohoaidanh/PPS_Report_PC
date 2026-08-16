"""
Main application window — Tunnel Concrete Thickness Analyzer.
Layer-based architecture: original cloud + independent segments.
Report always uses only the visible layers.
"""

import os
import copy
import logging
import numpy as np
from typing import Optional

from PySide6.QtWidgets import (
    QFrame, QLineEdit, QMainWindow, QSizePolicy, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QToolBar, QToolButton, QFileDialog, QMessageBox, QGroupBox, QApplication,
    QLabel, QPushButton, QSpinBox, QDoubleSpinBox, QComboBox,
    QListWidget, QListWidgetItem, QProgressBar, QStatusBar,
    QFormLayout, QScrollArea, QCheckBox, QMenu, QInputDialog,
    QAbstractItemView, QDialog, QDialogButtonBox, QSlider,
)
from PySide6.QtCore import Qt, QSize, QPoint, QSettings
from PySide6.QtGui import QFont, QColor, QPixmap, QIcon, QPixmapCache, QAction, QKeySequence, QShortcut

from pps_report.gui.help import HotkeysDialog
from pps_report.gui.viewer_3d import PointCloudViewer
from pps_report.gui.workers import CalculationWorker
from pps_report.gui import theme as theme_module
from pps_report.core.ply_loader import load_ply, get_ply_fields
from pps_report.core.filename_parser import parse_filename, ProjectInfo
from pps_report.core.layer_manager import Layer, LayerManager
from pps_report.core.calculator import CalculationResult, ThicknessDistribution
from pps_report.core.job_info import load_thickness_targets
from pps_report.core.project_io import save_project, load_project

logger = logging.getLogger(__name__)


# ============================================================ main window
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tunnel Concrete Thickness Analyzer")
        self.setGeometry(100, 100, 1440, 900)

        # Data
        self.layer_manager   = LayerManager()
        self.project_info: Optional[ProjectInfo] = None
        self.calc_result:   Optional[CalculationResult]     = None
        self.thickness_dist: Optional[ThicknessDistribution] = None
        self._current_filepath: Optional[str] = None

        # Cache of the last calculation result each layer contributed to,
        # keyed by layer name, so re-selecting a segment shows its numbers
        # again without recalculating.
        self._layer_calc_cache: dict = {}
        self._last_calc_layer_names: list = []

        # Snapshot-based undo/redo over segment (layer) state: create/delete/
        # merge/rename, and annotation add/move/delete/edit.
        self._undo_stack: list = []
        self._redo_stack: list = []
        self._MAX_UNDO_HISTORY = 20

        # Pending selection (from polygon / distance range)
        self._sel_pts:   Optional[np.ndarray] = None
        self._sel_dists: Optional[np.ndarray] = None

        # Settings
        self.target_min = 50.0
        self.target_max = 150.0
        self._setup_ui()
        self._setup_menubar()
        self._setup_toolbar()
        self._setup_statusbar()

        self.settings = QSettings('TunnelAnalyzer', 'TunnelConcreteThicknessAnalyzer')
        self._load_settings()


    # ================================================================== UI
    def _setup_ui(self):
        c = QWidget()
        self.setCentralWidget(c)
        lay = QHBoxLayout(c)
        lay.setContentsMargins(1, 1, 1, 1)

        sp = QSplitter(Qt.Horizontal)
        sp.addWidget(self._create_side_panel())

        self.viewer = PointCloudViewer()
        self.viewer.signals.selection_changed.connect(self._on_selection_changed)
        self.viewer.signals.selection_cleared.connect(self._on_selection_cleared)
        self.viewer.signals.polygon_mode_ended.connect(self._on_polygon_mode_ended)
        self.viewer.signals.polygon_selection_confirmed.connect(self._prompt_create_segment_dialog)
        self.viewer.signals.annotation_added.connect(self._on_annotation_added)
        self.viewer.signals.state_changing.connect(self._push_undo_snapshot)
        self.viewer.signals.delete_segment_requested.connect(self._on_toolbar_delete_segment)
        self.viewer.signals.merge_segments_requested.connect(self._on_merge_segments)
        self.viewer.signals.undo_requested.connect(self._on_undo)
        self.viewer.signals.redo_requested.connect(self._on_redo)
        # Connect visualization controls that need viewer (created after left panel)
        self.spin_point_size.valueChanged.connect(self.viewer.set_point_size)
        self.cmb_colormap.currentTextChanged.connect(self.viewer.set_colormap)
        sp.addWidget(self.viewer)

        sp.addWidget(self._create_right_panel())
        sp.setSizes([300, 700, 280])


        lay.addWidget(sp)



    # ------------------------------------------------------------------ side panel
    def _create_side_panel(self) -> QWidget:
        """Single consolidated side panel: File Information, Analysis
        Settings, Visualization, Layer Manager. (Selection/segment-creation
        controls and Calculate/Export live in the main toolbar — no
        duplicated Actions section here.)"""
        panel = QWidget()
        panel.setObjectName("side_panel")
        panel.setStyleSheet("""
            QWidget#side_panel {
                border: 1px solid #d0d7de;
                border-radius: 0px;
            }
        """)
        panel.setMinimumWidth(280)
        panel.setMaximumWidth(380)
        lay = QVBoxLayout(panel)
        lay.setSpacing(8)

        # ---- File info ----
        fg = QGroupBox("File Information")
        fl = QFormLayout(fg)

        self.lbl_filename = QLineEdit("File is not loaded yet")
        self.lbl_filename.setReadOnly(True)
        self.lbl_filename.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                padding: 0px;
            }
        """)
        self.lbl_project  = QLabel("-")
        self.lbl_job      = QLabel("-")
        self.lbl_time     = QLabel("-")
        fl.addRow("File:",      self.lbl_filename)
        fl.addRow("Project:",   self.lbl_project)
        fl.addRow("Job:",       self.lbl_job)
        fl.addRow("Time:",      self.lbl_time)
        lay.addWidget(fg)

        # ---- Settings ----
        sg = QGroupBox("Target Settings")
        sl = QFormLayout(sg)

        self.spin_target_min = QDoubleSpinBox()
        self.spin_target_min.setRange(0, 9999); self.spin_target_min.setValue(self.target_min)
        self.spin_target_min.setSuffix(" mm")
        sl.addRow("Min target thickness:", self.spin_target_min)

        self.spin_target_max = QDoubleSpinBox()
        self.spin_target_max.setRange(0, 9999); self.spin_target_max.setValue(self.target_max)
        self.spin_target_max.setSuffix(" mm")
        sl.addRow("Max target thickness:", self.spin_target_max)

        # Connect target changes
        self.spin_target_min.valueChanged.connect(self._on_target_changed)
        self.spin_target_max.valueChanged.connect(self._on_target_changed)

        lay.addWidget(sg)

        # ---- Layer Manager ----
        self.lbl_sel_count = QLabel("No selection")
        self.lbl_sel_count.setStyleSheet("color:#2c5282; font-weight:bold; font-size:10px;")
        lay.addWidget(self.lbl_sel_count)

        layer_box = QGroupBox("Layer Manager")
        layer_layout = QVBoxLayout(layer_box)

        hint = QLabel("☑ Hide/Show  |  Right-click → Options  |  Ctrl/Shift-click to multi-select for Merge")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#718096; font-size:9px;")
        layer_layout.addWidget(hint)

        self.list_layers = QListWidget()
        self.list_layers.setMinimumHeight(18)
        self.list_layers.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_layers.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_layers.customContextMenuRequested.connect(self._on_layer_context_menu)
        self.list_layers.itemChanged.connect(self._on_layer_item_changed)
        self.list_layers.currentItemChanged.connect(self._on_layer_selected)
        layer_layout.addWidget(self.list_layers)
        self.lbl_current_layer = QLabel("")
        self.lbl_current_layer.setStyleSheet("color:#2c5282; font-weight:bold; font-size:14px;")
        layer_layout.addWidget(self.lbl_current_layer)
        lay.addWidget(layer_box, stretch=1)

        # ---- Visualization (moved to the bottom) ----
        vg = QGroupBox("Visualization")
        vl = QFormLayout(vg)

        self.spin_point_size = QSpinBox()
        self.spin_point_size.setRange(1, 10); self.spin_point_size.setValue(1)
        vl.addRow("Point Size:", self.spin_point_size)

        self.cmb_colormap = QComboBox()
        self.cmb_colormap.addItems(['jet', 'viridis', 'plasma', 'coolwarm', 'rainbow'])
        self.cmb_colormap.hide()
        lay.addWidget(vg)

        return panel

    # ------------------------------------------------------------------ right panel
    def _create_right_panel(self) -> QWidget:
        panel = QWidget()

        panel.setMinimumWidth(10)
        panel.setMaximumWidth(360)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setSpacing(10)
       

        # Results
        rg = QGroupBox("Analysis Results")
        rl = QFormLayout(rg)
        bold = QFont("Arial", 12, QFont.Bold)

        self.lbl_area           = QLabel("-"); self.lbl_area.setFont(bold)
        self.lbl_target_coverage  = QLabel("-"); self.lbl_target_coverage.setFont(bold)
        self.lbl_volume         = QLabel("-"); self.lbl_volume.setFont(bold)
        self.lbl_mean_thickness = QLabel("-"); self.lbl_mean_thickness.setFont(bold)
        self.lbl_min_thickness  = QLabel("-")
        self.lbl_max_thickness  = QLabel("-")
        self.lbl_std_thickness  = QLabel("-")
        self.lbl_num_points     = QLabel("-")
        rl.addRow("Surface Area (m²):",   self.lbl_area)
        rl.addRow("Target Coverage (m²):", self.lbl_target_coverage)
        rl.addRow("Volume (m³):",    self.lbl_volume)
        rl.addRow("Mean Thickness (mm):",   self.lbl_mean_thickness)
        rl.addRow("Min Thickness (mm):",  self.lbl_min_thickness)
        rl.addRow("Max Thickness (mm):",  self.lbl_max_thickness)
        rl.addRow("Standard Deviation:",    self.lbl_std_thickness)
        rl.addRow("Number of Points:",          self.lbl_num_points)
        lay.addWidget(rg)

        # Distribution
        dg = QGroupBox("Thickness Distribution")
        dl = QVBoxLayout(dg)
        dl.setSpacing(10)

        def dist_row(title, color):
            row = QVBoxLayout()
            row.setSpacing(3)
            head = QHBoxLayout()
            lbl_title = QLabel(title)
            lbl_title.setStyleSheet("font-weight:600;")
            lbl_pct = QLabel("-")
            lbl_pct.setStyleSheet(f"color:{color}; font-weight:bold;")
            head.addWidget(lbl_title)
            head.addStretch()
            head.addWidget(lbl_pct)
            row.addLayout(head)

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            bar.setStyleSheet(f"""
                QProgressBar {{ border: none; border-radius: 3px; background: #e2e8f0; }}
                QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}
            """)
            row.addWidget(bar)
            dl.addLayout(row)
            return lbl_pct, bar

        self.lbl_below, self.bar_below   = dist_row("Below Target", "#ef4444")
        self.lbl_within, self.bar_within = dist_row("Within Target", "#10b981")
        self.lbl_above, self.bar_above   = dist_row("Above Target", "#2563eb")

        lay.addWidget(dg)

        lay.addStretch()
        scroll.setWidget(content)
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.addWidget(scroll)
        return panel

    # ------------------------------------------------------------------ menu / toolbar
    def _setup_menubar(self):
        mb = self.menuBar()
        fm = mb.addMenu("File")
        for label, shortcut, fn in [
            ("Open PLY File…",       "Ctrl+O", self._on_open_file),
            ("Save Project",        "Ctrl+S", self._on_save_project),
            ("Export PDF Report…",  "Ctrl+E", self._on_export_pdf),
            ("Exit",              "Ctrl+Q", self.close),
        ]:
            a = QAction(label, self); a.setShortcut(shortcut); a.triggered.connect(fn)
            if label == "Exit":
                fm.addSeparator()
            fm.addAction(a)

        hm = mb.addMenu("Help")
        ab = QAction("About", self); ab.triggered.connect(self._show_about)
        hm.addAction(ab)

        hotkeys = hm.addAction("Keyboard Shortcuts")
        hotkeys.triggered.connect(self._show_hotkeys)

        # Light/Dark toggle, top-right corner of the menu bar.
        self.btn_theme_toggle = QToolButton()
        self.btn_theme_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_theme_toggle.setAutoRaise(True)
        self.btn_theme_toggle.clicked.connect(self._on_toggle_theme)
        mb.setCornerWidget(self.btn_theme_toggle, Qt.TopRightCorner)
        self._update_theme_button()

    def _on_toggle_theme(self):
        new_mode = "dark" if theme_module.current_theme() == "light" else "light"
        theme_module.apply_theme(QApplication.instance(), new_mode)
        self.viewer.set_theme(new_mode)
        self._refresh_toolbar_icons()
        self._update_theme_button()

    def _update_theme_button(self):
        if theme_module.current_theme() == "dark":
            self.btn_theme_toggle.setText("☀ Light Mode")
        else:
            self.btn_theme_toggle.setText("🌙 Dark Mode")

    def _make_ribbon_button(self, text, icon_name, tooltip, checkable=False):
        """QToolButton (icon-over-text) matching the style of the viewer's
        annotation/segment toolbar buttons."""
        from pps_report.gui.lucide_icons import load_icon
        from pps_report.gui.theme import get_colors

        btn = QToolButton()
        btn.setText(text)
        btn.setIcon(load_icon(icon_name, get_colors()["text_main"]))
        btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        btn.setIconSize(QSize(20, 20))
        btn.setCheckable(checkable)
        btn.setToolTip(tooltip)
        self._icon_recipes[btn] = icon_name
        return btn

    def _make_ribbon_action(self, text, icon_name, tooltip=""):
        from pps_report.gui.lucide_icons import load_icon
        from pps_report.gui.theme import get_colors

        act = QAction(load_icon(icon_name, get_colors()["text_main"]), text, self)
        if tooltip:
            act.setToolTip(tooltip)
        self._icon_recipes[act] = icon_name
        return act

    def _refresh_toolbar_icons(self):
        from pps_report.gui.lucide_icons import load_icon
        from pps_report.gui.theme import get_colors
        color = get_colors()["text_main"]
        for widget, name in self._icon_recipes.items():
            widget.setIcon(load_icon(name, color))

    def _build_selection_toolbar_widgets(self, tb: QToolBar):
        """Selection controls, moved from the left panel onto the main
        toolbar. Both Polygon and By-Thickness selection end in a confirm
        dialog that asks for a segment name — no separate Create-Segment
        button is needed."""
        self.btn_polygon = self._make_ribbon_button(
            "Polygon", "pentagon", "Draw an area to select points", checkable=True)
        self.btn_polygon.toggled.connect(self._on_polygon_toggled)
        QShortcut(QKeySequence("S"), self).activated.connect(self.btn_polygon.click)
        tb.addWidget(self.btn_polygon)

        btn_range = self._make_ribbon_button(
            "By Thickness", "layers", "Select points within a thickness range")
        btn_range.clicked.connect(self._on_select_by_range_dialog)
        tb.addWidget(btn_range)

    def _setup_toolbar(self):
        self._icon_recipes = {}

        tb = QToolBar("Main")
        tb.setIconSize(QSize(22, 22))
        tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.addToolBar(tb)

        # ---- File / view ----
        self.act_open_file = self._make_ribbon_action("Open File", "folder-open")
        self.act_open_file.triggered.connect(self._on_open_file)
        tb.addAction(self.act_open_file)
        QShortcut(QKeySequence("O"), self).activated.connect(self.act_open_file.trigger)

        self.act_reset_view = self._make_ribbon_action("Reset View", "rotate-ccw")
        self.act_reset_view.triggered.connect(self.viewer.reset_view)
        tb.addAction(self.act_reset_view)
        QShortcut(QKeySequence("R"), self).activated.connect(self.act_reset_view.trigger)
        tb.addSeparator()

        # ---- Selection / segment creation ----
        self._build_selection_toolbar_widgets(tb)
        tb.addSeparator()

        # ---- Annotation tools ----
        # (owned/constructed by the viewer for its annotation-manager
        # checkable-group logic, displayed here in the main toolbar)
        for btn in (self.viewer.btn_add_text, self.viewer.btn_add_line,
                    self.viewer.btn_move_annot, self.viewer.btn_delete_annot,
                    self.viewer.btn_edit_style):
            tb.addWidget(btn)
        tb.addSeparator()

        # ---- Segment management ----
        for btn in (self.viewer.btn_delete_segment, self.viewer.btn_merge_segments):
            tb.addWidget(btn)
        tb.addSeparator()

        # ---- History ----
        for btn in (self.viewer.btn_undo, self.viewer.btn_redo):
            tb.addWidget(btn)
        tb.addSeparator()

        # ---- Analysis / export ----
        self.btn_calculate = self._make_ribbon_action("Calculate", "calculator")
        self.btn_calculate.triggered.connect(self._on_calculate)
        tb.addAction(self.btn_calculate)

        self.act_export_pdf = self._make_ribbon_action("Export PDF", "file-text")
        self.act_export_pdf.triggered.connect(self._on_export_pdf)
        tb.addAction(self.act_export_pdf)

    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.statusbar.addPermanentWidget(self.progress_bar)

        self.statusbar.showMessage("Ready — Please open a PLY file")


    def _show_hotkeys(self):
        dlg = HotkeysDialog(self)
        dlg.exec()
    # ================================================================== file
    def _on_open_file(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "Open Point Cloud File", "",
            "Compare Files (*compare*.ply);;"
            "PLY Files (*.ply);;"
            "All Files (*)"
        )
        if fp:
            self._load_file(fp)

    def _load_file(self, filepath: str):
        try:
            self.statusbar.showMessage(f"Loading: {filepath}…")

            fields = get_ply_fields(filepath)
            dist_field = "distances" if "distances" in fields else "x"

            cloud_data = load_ply(filepath, dist_field)
            # dists = cloud_data.distances
            # dists = np.where(dists <= -20, np.abs(dists), dists)
            # dists = np.where((dists > -20) & (dists < 20), 0, dists)
            # cloud_data.distances = dists
            self.project_info = parse_filename(filepath)

            min_target, max_target = load_thickness_targets(filepath)

            # Set thickness targets in viewer
            self.viewer.set_thickness_targets(min_target, max_target)
            self.spin_target_min.setValue(min_target)
            self.spin_target_max.setValue(max_target)

            # Reset everything
            self.layer_manager.clear()
            self._layer_calc_cache.clear()
            self._last_calc_layer_names = []
            self.viewer.clear_all_layers()
            self.list_layers.blockSignals(True)
            self.list_layers.clear()
            self.list_layers.blockSignals(False)
            self._clear_results()
            self._reset_selection()

            # Add original layer
            layer = self.layer_manager.set_original(
                name=os.path.basename(filepath),
                points=cloud_data.points,
                distances=cloud_data.distances,
            )
            self.viewer.sync_layers(self.layer_manager.layers)
            self.viewer.add_layer(layer)
            self.viewer.reset_view()
            self._add_layer_item(layer)

            # Update file info labels
            self.lbl_filename.setText(self.project_info.original_filename)
            self.lbl_project.setText(self.project_info.project_name)
            self.lbl_job.setText(self.project_info.job_number)
            self.lbl_time.setText(self.project_info.formatted_time)

            self._current_filepath = filepath

            restored_count = self._restore_project_if_present(filepath)
            if restored_count:
                self.statusbar.showMessage(
                    f"Loaded: {os.path.basename(filepath)}  ({cloud_data.num_points:,} point) "
                    f"— restored {restored_count} saved segment(s)"
                )
            else:
                self.statusbar.showMessage(
                    f"Loaded: {os.path.basename(filepath)}  ({cloud_data.num_points:,} point)"
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Cannot load file:\n{e}")
            self.statusbar.showMessage("Error loading file")

    def _restore_project_if_present(self, filepath: str) -> int:
        """Restore previously-saved segments for this PLY, if a project sidecar exists."""
        project = load_project(filepath)
        if project is None:
            return 0

        for seg in project["segments"]:
            layer = self.layer_manager.add_segment(
                points=seg["points"],
                distances=seg["distances"],
                name=seg["name"],
                color=seg["color"],
                visible=seg["visible"],
                annotations=seg["annotations"],
            )
            self.viewer.sync_layers(self.layer_manager.layers)
            self.viewer.add_layer(layer)
            self.viewer.restore_annotations(layer.name, layer.annotations)
            self.viewer.set_layer_visible(layer.name, layer.visible)
            item = self._add_layer_item(layer)
            item.setCheckState(Qt.Checked if layer.visible else Qt.Unchecked)

        if project.get("target_min") is not None:
            self.spin_target_min.setValue(project["target_min"])
        if project.get("target_max") is not None:
            self.spin_target_max.setValue(project["target_max"])

        return len(project["segments"])

    def _on_save_project(self):
        if self._current_filepath is None:
            QMessageBox.warning(self, "Warning", "Please load a PLY file first!")
            return
        try:
            path = save_project(
                self._current_filepath, self.layer_manager,
                self.spin_target_min.value(), self.spin_target_max.value(),
            )
            self.statusbar.showMessage(f"Project saved: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project:\n{e}")

    # ================================================================== layer list helpers
    def _layer_icon(self, layer: Layer) -> QIcon:
        pix = QPixmap(14, 14)
        if layer.color is None:
            pix.fill(QColor(50, 130, 255))   # blue = original
        else:
            r, g, b = (int(c * 255) for c in layer.color)
            pix.fill(QColor(r, g, b))
        return QIcon(pix)

    def _layer_display_text(self, layer: Layer) -> str:
        count = len(getattr(layer, "annotations", []))
        note_flag = f" 📝({count})" if count else ""
        return f"{layer.name}{note_flag}  ({layer.num_points:,} points)"

    def _layer_tooltip(self, layer: Layer) -> str:
        annotations = getattr(layer, "annotations", [])
        if not annotations:
            return ""
        return "\n".join(f"- {ann['text']}" for ann in annotations)

    def _uncheck_all_layers(self):
        for i in range(self.list_layers.count()):
            item = self.list_layers.item(i)
            item.setCheckState(Qt.Unchecked)

    def _add_layer_item(self, layer: Layer):
        item = QListWidgetItem(self._layer_display_text(layer))
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if layer.visible else Qt.Unchecked)
        item.setData(Qt.UserRole, layer.name)
        item.setIcon(self._layer_icon(layer))
        if getattr(layer, "annotations", []):
            item.setToolTip(self._layer_tooltip(layer))
        if layer.is_original:
            f = item.font(); f.setBold(True); item.setFont(f)
        self.list_layers.blockSignals(True)
        self.list_layers.addItem(item)
        self.list_layers.blockSignals(False)
        return item

    def _item_for(self, name: str) -> Optional[QListWidgetItem]:
        for i in range(self.list_layers.count()):
            it = self.list_layers.item(i)
            if it.data(Qt.UserRole) == name:
                return it
        return None

    def _on_layer_item_changed(self, item: QListWidgetItem):
        name    = item.data(Qt.UserRole)
        visible = item.checkState() == Qt.Checked
        layer   = self.layer_manager.get(name)
        if layer:
            layer.visible = visible
        self.viewer.set_layer_visible(name, visible)




    def _on_layer_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        if current is None:
            return

        self.viewer._set_tool_buttons_enabled(True)
        name = current.data(Qt.UserRole)
        self.viewer.set_annotation_layer(name)

        cached = self._layer_calc_cache.get(name)
        if cached is not None:
            self._display_calc_result(*cached)
            self.statusbar.showMessage(f"Showing cached calculation for {name}")
        else:
            self._clear_results()




    # ------------------------------------------------------------------ layer context menu
    def _on_layer_context_menu(self, pos: QPoint):
        item = self.list_layers.itemAt(pos)
        if item is None:
            return
        name  = item.data(Qt.UserRole)
        layer = self.layer_manager.get(name)
        if layer is None:
            return

        menu = QMenu(self)
        act_show     = menu.addAction("👁  Show")
        act_hide     = menu.addAction("🙈  Hide")
        menu.addSeparator()
        act_calc     = menu.addAction("📊  Calculate for this layer")
        act_export   = menu.addAction("📄  Export PDF for this layer")
        menu.addSeparator()
        act_note     = menu.addAction("�  Annotate this layer")
        act_rename   = menu.addAction("✏  Rename")
        if not layer.is_original:
            menu.addSeparator()
            act_delete = menu.addAction("🗑  Delete layer")
        else:
            act_delete = None

        chosen = menu.exec(self.list_layers.mapToGlobal(pos))

        if chosen == act_show:
            item.setCheckState(Qt.Checked)
        elif chosen == act_hide:
            item.setCheckState(Qt.Unchecked)
        elif chosen == act_calc:
            self.list_layers.setCurrentItem(item)
            self._on_calculate()
        elif chosen == act_export:
            self._calc_and_export_layer(layer)
        elif chosen == act_rename:
            self._rename_layer(name, item)
        elif chosen == act_note:
            self._annotate_layer(layer, item)
        elif act_delete and chosen == act_delete:
            self._push_undo_snapshot()
            self._delete_layer(name)

    def _rename_layer(self, old_name: str, item: QListWidgetItem):
        new_name, ok = QInputDialog.getText(
            self, "Rename Layer", "New name:", text=old_name)
        if not ok or not new_name.strip() or new_name == old_name:
            return
        new_name = new_name.strip()
        layer = self.layer_manager.get(old_name)
        if layer is None:
            return
        self._push_undo_snapshot()
        self.layer_manager.rename(old_name, new_name)
        # update actor key in viewer
        actor = self.viewer._actors.pop(old_name, None)
        if actor:
            self.viewer._actors[new_name] = actor
        cached = self._layer_calc_cache.pop(old_name, None)
        if cached is not None:
            self._layer_calc_cache[new_name] = cached
        item.setText(self._layer_display_text(layer))
        item.setData(Qt.UserRole, new_name)

    def _delete_layer(self, name: str):
        self.viewer._delete_annotation_by_layer(name)
        self._layer_calc_cache.pop(name, None)
        self.layer_manager.remove(name)
        self.viewer.remove_layer(name)
        self.viewer.sync_layers(self.layer_manager.layers)
        item = self._item_for(name)
        if item:
            self.list_layers.takeItem(self.list_layers.row(item))

        

    # ================================================================== selection
    def _on_polygon_toggled(self, checked: bool):
        if checked:
            if not self.layer_manager.layers:
                self.btn_polygon.setChecked(False)
                QMessageBox.warning(self, "Warning", "Please load a PLY file first!")
                return
            self.statusbar.showMessage(
                "Drawing polygon: Left-click to add points  |  Double-click/Enter: complete  |  ESC: cancel"
            )
            self.viewer.enable_polygon_mode()
        else:
            self.viewer.disable_polygon_mode()
            self.statusbar.showMessage("Ready")

    def _on_polygon_mode_ended(self):
        self.btn_polygon.blockSignals(True)
        self.btn_polygon.setChecked(False)
        self.btn_polygon.blockSignals(False)

    def _on_select_by_range_dialog(self):
        if not self.layer_manager.layers:
            QMessageBox.warning(self, "Warning", "Please load a PLY file first!")
            return

        original = self.layer_manager.original
        if original is not None:
            stats = original.get_stats()
            lo, hi = int(stats['min']) - 1, int(stats['max']) + 1
        else:
            lo, hi = -50, 500
        lo = min(lo, 0)
        if hi <= lo:
            hi = lo + 1

        dlg = QDialog(self)
        dlg.setWindowTitle("Select by Thickness")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(f"Thickness range ({lo} to {hi} mm):"))

        form = QFormLayout()

        sld_min = QSlider(Qt.Horizontal)
        sld_min.setRange(lo, hi)
        sld_min.setValue(min(max(int(self.spin_target_min.value()), lo), hi))
        lbl_min_val = QLabel(f"{sld_min.value()} mm")
        sld_min.valueChanged.connect(lambda v: lbl_min_val.setText(f"{v} mm"))
        min_row = QHBoxLayout(); min_row.addWidget(sld_min); min_row.addWidget(lbl_min_val)
        form.addRow("Min:", min_row)

        sld_max = QSlider(Qt.Horizontal)
        sld_max.setRange(lo, hi)
        sld_max.setValue(min(max(int(self.spin_target_max.value()), lo), hi))
        lbl_max_val = QLabel(f"{sld_max.value()} mm")
        sld_max.valueChanged.connect(lambda v: lbl_max_val.setText(f"{v} mm"))
        max_row = QHBoxLayout(); max_row.addWidget(sld_max); max_row.addWidget(lbl_max_val)
        form.addRow("Max:", max_row)

        lay.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dlg)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)

        if dlg.exec() != QDialog.Accepted:
            return

        min_v, max_v = sld_min.value(), sld_max.value()
        if min_v > max_v:
            min_v, max_v = max_v, min_v

        self.viewer.select_by_distance_range(min_v, max_v)

        if self._sel_pts is None or len(self._sel_pts) == 0:
            QMessageBox.information(self, "No Points", "No points found in that thickness range.")
            return

        self._prompt_create_segment_dialog()

    def _on_target_changed(self):
        min_t = self.spin_target_min.value()
        max_t = self.spin_target_max.value()
        self.viewer.set_thickness_targets(min_t, max_t)

    def _on_selection_changed(self, pts: np.ndarray, dists: np.ndarray):
        self._sel_pts   = pts
        self._sel_dists = dists
        n = len(pts) if pts is not None else 0
        logger.debug("selection changed -> %d points", n)
        self.lbl_sel_count.setText(f"Selected area: {n:,} points")
        self.statusbar.showMessage(f"Selected {n:,} points")

    def _on_selection_cleared(self):
        self._reset_selection()

    def _reset_selection(self):
        self._sel_pts   = None
        self._sel_dists = None
        self.lbl_sel_count.setText("No selection")

    def _prompt_create_segment_dialog(self):
        """Confirm + name dialog used after both Polygon and By-Thickness selection."""
        if self._sel_pts is None or len(self._sel_pts) == 0:
            return

        n = len(self._sel_pts)
        default_name = self.layer_manager.next_segment_name()

        dlg = QDialog(self)
        dlg.setWindowTitle("Create Segment")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(f"{n:,} points selected. Create a segment from this selection?"))

        name_edit = QLineEdit(default_name)
        name_edit.selectAll()
        lay.addWidget(name_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dlg)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)

        if dlg.exec() == QDialog.Accepted:
            name = name_edit.text().strip()
            self._create_segment_from_selection(name if name else None)
        else:
            self.viewer.clear_selection()
            self._reset_selection()

    def _create_segment_from_selection(self, name: Optional[str] = None):
        if self._sel_pts is None or len(self._sel_pts) == 0:
            return

        self._push_undo_snapshot()
        layer = self.layer_manager.add_segment(
            points=self._sel_pts.copy(),
            distances=self._sel_dists.copy(),
            name=name,
        )
        self.viewer.sync_layers(self.layer_manager.layers)
        self._uncheck_all_layers()
        self.viewer.add_layer(layer)
        item = self._add_layer_item(layer)
        self.list_layers.setCurrentItem(item)
        self.viewer.clear_selection()
        self._reset_selection()
        self.statusbar.showMessage(f"Created {layer.name} ({layer.num_points:,} points)")

    def _on_toolbar_delete_segment(self):
        item = self.list_layers.currentItem()
        if item is None:
            QMessageBox.warning(self, "Warning", "Please select a segment in Layer Manager first!")
            return
        name = item.data(Qt.UserRole)
        layer = self.layer_manager.get(name)
        if layer is None or layer.is_original:
            QMessageBox.warning(self, "Warning", "Select a segment (not the original layer) to delete.")
            return
        self._push_undo_snapshot()
        self._delete_layer(name)
        self.statusbar.showMessage(f"Deleted {name}")

    def _on_merge_segments(self):
        items = self.list_layers.selectedItems()
        names = [it.data(Qt.UserRole) for it in items]
        layers = [self.layer_manager.get(n) for n in names]
        layers = [l for l in layers if l is not None and not l.is_original]
        if len(layers) < 2:
            QMessageBox.warning(
                self, "Warning",
                "Select 2 or more segments in Layer Manager (Ctrl/Shift-click) to merge!"
            )
            return

        self._push_undo_snapshot()

        merged_points = np.vstack([l.points for l in layers])
        merged_distances = np.concatenate([l.distances for l in layers])
        merged_annotations = []
        for l in layers:
            merged_annotations.extend(l.annotations)
        old_names = [l.name for l in layers]

        for name in old_names:
            self._delete_layer(name)

        new_layer = self.layer_manager.add_segment(
            points=merged_points,
            distances=merged_distances,
            annotations=merged_annotations,
        )
        self.viewer.sync_layers(self.layer_manager.layers)
        self.viewer.add_layer(new_layer)
        self.viewer.restore_annotations(new_layer.name, new_layer.annotations)
        item = self._add_layer_item(new_layer)
        self.list_layers.setCurrentItem(item)
        self.statusbar.showMessage(
            f"Merged {len(old_names)} segments into {new_layer.name} ({new_layer.num_points:,} points)"
        )

    # ================================================================== undo/redo
    def _snapshot_state(self) -> dict:
        segments = []
        for layer in self.layer_manager.layers:
            if layer.is_original:
                continue
            segments.append({
                "name": layer.name,
                "points": layer.points.copy(),
                "distances": layer.distances.copy(),
                "color": layer.color,
                "visible": layer.visible,
                "annotations": copy.deepcopy(
                    [{k: v for k, v in ann.items() if k != "actor"} for ann in layer.annotations]
                ),
            })
        return {"segments": segments}

    def _restore_state(self, state: dict):
        for layer in [l for l in self.layer_manager.layers if not l.is_original]:
            self.viewer._delete_annotation_by_layer(layer.name)
            self.viewer.remove_layer(layer.name)
        self.layer_manager.clear_segments()
        self._layer_calc_cache.clear()

        self.list_layers.blockSignals(True)
        for i in reversed(range(self.list_layers.count())):
            item = self.list_layers.item(i)
            name = item.data(Qt.UserRole)
            if self.layer_manager.get(name) is None:
                self.list_layers.takeItem(i)
        self.list_layers.blockSignals(False)

        last_item = None
        for seg in state["segments"]:
            layer = self.layer_manager.add_segment(
                points=seg["points"], distances=seg["distances"], name=seg["name"],
                color=seg["color"], visible=seg["visible"], annotations=seg["annotations"],
            )
            self.viewer.sync_layers(self.layer_manager.layers)
            self.viewer.add_layer(layer)
            self.viewer.restore_annotations(layer.name, layer.annotations)
            self.viewer.set_layer_visible(layer.name, layer.visible)
            last_item = self._add_layer_item(layer)
            last_item.setCheckState(Qt.Checked if layer.visible else Qt.Unchecked)

        if last_item is not None:
            self.list_layers.setCurrentItem(last_item)

    def _push_undo_snapshot(self):
        self._undo_stack.append(self._snapshot_state())
        if len(self._undo_stack) > self._MAX_UNDO_HISTORY:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._update_undo_redo_buttons()

    def _on_undo(self):
        if not self._undo_stack:
            return
        current = self._snapshot_state()
        state = self._undo_stack.pop()
        self._redo_stack.append(current)
        self._restore_state(state)
        self._update_undo_redo_buttons()
        self.statusbar.showMessage("Undo")

    def _on_redo(self):
        if not self._redo_stack:
            return
        current = self._snapshot_state()
        state = self._redo_stack.pop()
        self._undo_stack.append(current)
        self._restore_state(state)
        self._update_undo_redo_buttons()
        self.statusbar.showMessage("Redo")

    def _update_undo_redo_buttons(self):
        self.viewer.btn_undo.setEnabled(bool(self._undo_stack))
        self.viewer.btn_redo.setEnabled(bool(self._redo_stack))

    # ================================================================== calculation
    def _on_calculate(self):
        # selected_items = self.list_layers.selectedItems()
        selected_items = [
            self.list_layers.item(i)
            for i in range(self.list_layers.count())
            if self.list_layers.item(i).checkState() == Qt.Checked
        ]
        if not selected_items or len(selected_items) == 0:
            QMessageBox.warning(self, "Warning",
                                "Please check one or more layers!")
            return
        
        # Collect points and distances from all selected layers
        all_points = []
        all_distances = []
        layer_names = []

        for item in selected_items:
            layer_name = item.data(Qt.UserRole)
            layer = self.layer_manager.get(layer_name)
            # only include visible layers with points to caculate
            if layer is None or layer.visible == False:
                continue
            if len(layer.points) > 0:
                all_points.append(layer.points)
                all_distances.append(layer.distances)
                layer_names.append(layer_name)

        if not all_points:
            QMessageBox.warning(self, "Warning",
                                "Selected layers have no points!")
            return

        # Combine points and distances from all selected layers
        pts = np.vstack(all_points)
        dists = np.concatenate(all_distances)

        self._last_calc_layer_names = layer_names
        self._run_calculation(pts, dists)

    def _run_calculation(self, pts: np.ndarray, dists: np.ndarray):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.btn_calculate.setEnabled(False)

        self.worker = CalculationWorker(
            pts, dists,
            self.spin_target_min.value(),
            self.spin_target_max.value(),
        )
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self._on_calc_done)
        self.worker.error.connect(self._on_calc_error)
        self.worker.start()

    def _display_calc_result(self, calc: CalculationResult, dist: ThicknessDistribution):
        self.calc_result    = calc
        self.thickness_dist = dist

        self.lbl_area.setText(f"{calc.surface_area_m2:.1f}")
        self.lbl_target_coverage.setText(f"{calc.area_reached_target_m2:.1f}")
        self.lbl_volume.setText(f"{calc.volume_m3:.1f}")
        self.lbl_mean_thickness.setText(f"{calc.mean_thickness_mm:.0f}")
        self.lbl_min_thickness.setText(f"{calc.min_thickness_mm:.0f}")
        self.lbl_max_thickness.setText(f"{calc.max_thickness_mm:.0f}")
        self.lbl_std_thickness.setText(f"{calc.std_thickness_mm:.0f}")
        self.lbl_num_points.setText(f"{calc.num_points:,}")

        self.lbl_below.setText(f"{dist.below_target_percent:.1f}%")
        self.lbl_below.setToolTip(f"{dist.below_target:,} points")
        self.bar_below.setValue(int(round(dist.below_target_percent)))

        self.lbl_within.setText(f"{dist.within_target_percent:.1f}%")
        self.lbl_within.setToolTip(f"{dist.within_target:,} points")
        self.bar_within.setValue(int(round(dist.within_target_percent)))

        self.lbl_above.setText(f"{dist.above_target_percent:.1f}%")
        self.lbl_above.setToolTip(f"{dist.above_target:,} points")
        self.bar_above.setValue(int(round(dist.above_target_percent)))

    def _on_calc_done(self, calc: CalculationResult, dist: ThicknessDistribution):
        self._display_calc_result(calc, dist)

        for name in self._last_calc_layer_names:
            self._layer_calc_cache[name] = (calc, dist)

        self.progress_bar.setVisible(False)
        self.btn_calculate.setEnabled(True)
        self.statusbar.showMessage("Completed calculation")

    def _on_calc_error(self, msg: str):
        self.progress_bar.setVisible(False)
        self.btn_calculate.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Error occurred while calculating:\n{msg}")

    def _annotate_layer(self, layer: Layer, item: QListWidgetItem = None):
        if not layer.visible:
            QMessageBox.warning(self, "Warning", "Layer must be visible to place an annotation on the view.")
            return
        text, ok = QInputDialog.getMultiLineText(
            self,
            "Add Annotation",
            f"Enter annotation text for {layer.name}:"
        )
        if not ok or not text.strip():
            return
        self.statusbar.showMessage(
            f"Click on the view to place the annotation for {layer.name}."
        )
        self.viewer.enable_annotation_mode(layer.name, text.strip())

    def _on_annotate_layer(self):
        item = self.list_layers.currentItem()
        if item is None:
            QMessageBox.warning(self, "Warning", "Please select a layer first!")
            return
        layer = self.layer_manager.get(item.data(Qt.UserRole))
        if layer is None:
            QMessageBox.warning(self, "Warning", "Selected layer not found.")
            return
        self._annotate_layer(layer, item)

    def _on_annotation_added(self, layer_name: str, event: object):
        layer = self.layer_manager.get(layer_name)
        item = self._item_for(layer_name)
        if layer is None or item is None:
            return

        action = event.get("action") if isinstance(event, dict) else None
        annotation = event.get("annotation") if isinstance(event, dict) else event

        # "move" (style/text edits) already pushes its own pre-mutation
        # snapshot via viewer.signals.state_changing, since the annotation
        # dict is mutated in place before this handler runs.
        if action in ("add", "delete"):
            self._push_undo_snapshot()

        if action == "add":
            layer.annotations.append(annotation)
        elif action == "move":
            found = None
            for existing in layer.annotations:
                if existing is annotation or existing.get("type") == annotation.get("type") and existing.get("position") == annotation.get("position"):
                    found = existing
                    break
            if found:
                found.update(annotation)
        elif action == "delete":
            layer.annotations = [ann for ann in layer.annotations if ann is not annotation and not (
                ann.get("type") == annotation.get("type")
                and ann.get("position") == annotation.get("position")
                and ann.get("end_position") == annotation.get("end_position")
            )]

        item.setText(self._layer_display_text(layer))
        item.setToolTip(self._layer_tooltip(layer))
        self.statusbar.showMessage(
            f"Annotation updated for {layer_name}."
        )

    def _clear_results(self):
        for w in (self.lbl_area, self.lbl_volume, self.lbl_target_coverage,
                  self.lbl_mean_thickness, self.lbl_min_thickness,
                  self.lbl_max_thickness, self.lbl_std_thickness,
                  self.lbl_num_points, self.lbl_below, self.lbl_within,
                  self.lbl_above):
            w.setText("-")
        for bar in (self.bar_below, self.bar_within, self.bar_above):
            bar.setValue(0)
        self.calc_result    = None
        self.thickness_dist = None

    # ================================================================== export
    def _on_export_pdf(self):
        if self.calc_result is None:
            QMessageBox.warning(self, "Warning", "Please run calculation first!")
            return
        visible_layers = self.layer_manager.visible_layers()
        self._do_export(self.calc_result, self.thickness_dist,
                        visible_layers=visible_layers)

    def _calc_and_export_layer(self, layer: Layer):
        """Calculate for a single layer synchronously, then export."""
        try:
            calc = self.calc_result
            dist = self.thickness_dist
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Calculation failed:\n{e}")
            return
        self._do_export(calc, dist,
                        visible_layers=[layer],
                        suffix=f"_{layer.name}")


    def _do_export(self, calc: CalculationResult, dist: ThicknessDistribution,
                visible_layers, suffix: str = ""):

        import subprocess
        import platform
        import tempfile
        import shutil
        from pps_report.gui.pdf_preview_dialog import PdfPreviewDialog

        if self.project_info is None:
            QMessageBox.warning(self, "Warning", "Please load a PLY file first!")
            return

        # =========================
        # 1. Default filename
        # =========================
        _segment_str = ""
        for _layer in visible_layers:
            _segment_str += f"_{_layer.name}" if _layer.name and (self.project_info.job_number not in _layer.name) else ""

        default = (
            f"{self.project_info.project_name}_"
            f"{self.project_info.job_number}_{self.project_info.scan_time}_{self.project_info.segment_name}{_segment_str}{suffix}.pdf"
        )

        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(tmp_fd)

        try:
            self.statusbar.showMessage("Generating PDF report…")

            # =========================
            # 2. Capture data (UI layer only)
            # =========================
            screenshot = self.viewer.get_screenshot()
            original_area_m2 = None

            ctx = {
                "project_info": self.project_info,
                "calculation_result": calc,
                "thickness_distribution": dist,
                "target_min": self.spin_target_min.value(),
                "target_max": self.spin_target_max.value(),
                "original_area_m2": original_area_m2,
                "screenshot_path": screenshot,
                "visible_layers": visible_layers,
            }

            # =========================
            # 3. Generate report to a temp file for preview
            # =========================
            from pps_report.report import PDFGenerator

            generator = PDFGenerator(tmp_path)
            generator.generate(ctx)

            # =========================
            # 4. Preview — user confirms before choosing where to save
            # =========================
            preview = PdfPreviewDialog(tmp_path, parent=self)
            if preview.exec() != PdfPreviewDialog.Accepted:
                self.statusbar.showMessage("Export cancelled")
                return

            fp, _ = QFileDialog.getSaveFileName(
                self, "Save PDF Report", default, "PDF Files (*.pdf)"
            )
            if not fp:
                self.statusbar.showMessage("Export cancelled")
                return

            shutil.move(tmp_path, fp)
            tmp_path = None
            out = fp

            # =========================
            # 5. UI feedback
            # =========================
            self.statusbar.showMessage(f"Completed: {out}")

            QMessageBox.information(
                self,
                "Success",
                f"Report exported:\n{out}"
            )

            # =========================
            # 6. Auto-open file
            # =========================
            if platform.system() == 'Windows':
                os.startfile(out)
            elif platform.system() == 'Darwin':
                subprocess.call(['open', out])
            else:
                subprocess.call(['xdg-open', out])

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to generate report:\n{str(e)}"
            )
        finally:
            if tmp_path is not None and os.path.exists(tmp_path):
                os.remove(tmp_path)
    # ================================================================== misc
    def _show_about(self):
        
        QMessageBox.about(
            self, "About Tunnel Analyzer",
            "Tunnel Concrete Thickness Analyzer\n\n"
            "Analysis of sprayed concrete thickness in tunnel engineering from Point Cloud (.ply)\n\n"
            "Version 2.0 — Layer-based architecture")

    def closeEvent(self, event):
        self._save_settings()
        self.viewer.close()
        event.accept()

    # ------------------------------------------------------------------ persistence
    def _load_settings(self):
        self.settings.beginGroup('Visualization')
        self.spin_point_size.setValue(self.settings.value('point_size', 1, type=int))
        colormap = self.settings.value('colormap', 'jet')
        idx = self.cmb_colormap.findText(colormap)
        if idx >= 0:
            self.cmb_colormap.setCurrentIndex(idx)
        self.spin_target_min.setValue(self.settings.value('target_min', self.target_min, type=float))
        self.spin_target_max.setValue(self.settings.value('target_max', self.target_max, type=float))
        self.settings.endGroup()

        self.settings.beginGroup('Annotation')
        self.viewer._annotation_color = self.settings.value('annotation_color', '#000000')
        self.viewer._annotation_line_width = self.settings.value('line_width', 2, type=int)
        self.viewer._annotation_font_size = self.settings.value('font_size', 14, type=int)
        self.viewer._annotation_font_family = self.settings.value('font_family', 'Arial')
        self.settings.endGroup()

        self.settings.beginGroup('Appearance')
        saved_theme = self.settings.value('theme', 'light')
        self.settings.endGroup()
        if saved_theme != theme_module.current_theme():
            theme_module.apply_theme(QApplication.instance(), saved_theme)
        self.viewer.set_theme(saved_theme)
        self._refresh_toolbar_icons()
        self._update_theme_button()

    def _save_settings(self):
        self.settings.beginGroup('Visualization')
        self.settings.setValue('point_size', self.spin_point_size.value())
        self.settings.setValue('colormap', self.cmb_colormap.currentText())
        self.settings.setValue('target_min', self.spin_target_min.value())
        self.settings.setValue('target_max', self.spin_target_max.value())
        self.settings.endGroup()

        self.settings.beginGroup('Annotation')
        self.settings.setValue('annotation_color', self.viewer._annotation_color)
        self.settings.setValue('line_width', self.viewer._annotation_line_width)
        self.settings.setValue('font_size', self.viewer._annotation_font_size)
        self.settings.setValue('font_family', self.viewer._annotation_font_family)
        self.settings.endGroup()

        self.settings.beginGroup('Appearance')
        self.settings.setValue('theme', theme_module.current_theme())
        self.settings.endGroup()
