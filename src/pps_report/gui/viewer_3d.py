"""
3D Point Cloud Viewer — layer-based architecture.

Polygon selection uses VTK's native 2D rendering (layer 1 overlay),
avoiding all Qt-over-OpenGL transparency issues.
All layers (original + segments) render with the same thickness colormap.
"""

import os
import time
import logging

import numpy as np
import vtk

from typing import Optional, List, Dict

import pyvista as pv
from pyvistaqt import QtInteractor

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QToolButton, QPushButton, QToolTip, QInputDialog,
)
from PySide6.QtGui import QColor, QCursor, QKeySequence, QShortcut
from PySide6.QtCore import Signal, QObject, QTimer, QSize, Qt

from pps_report.gui.vtk_polygon_picker import VTKPolygonPicker

from pps_report.gui.annotation.annotation_manager import AnnotationManager
from pps_report.gui.annotation.text_annotation import TextAnnotation
from pps_report.gui.annotation.line_annotation import LineAnnotation
from pps_report.gui.annotation.delete_annotation import DeleteAnnotation
from pps_report.gui.annotation.move_annotation import MoveAnnotation
from pps_report.gui.annotation.edit_style_annotation import EditStyleAnnotation
from pps_report.gui.annotation.style_dialog import AnnotationEditDialog
from pps_report.core.layer_manager import Layer

logger = logging.getLogger(__name__)


# ============================================================ signals
class ViewerSignals(QObject):
    selection_changed  = Signal(object, object)
    selection_cleared  = Signal()
    polygon_mode_ended = Signal()
    polygon_selection_confirmed = Signal()   # emitted after a polygon closes with a non-empty selection
    annotation_added   = Signal(str, object)
    state_changing     = Signal()   # emitted just before an in-place mutation, for undo snapshots
    delete_segment_requested = Signal()
    merge_segments_requested = Signal()
    undo_requested = Signal()
    redo_requested = Signal()



# ============================================================ viewer
class PointCloudViewer(QWidget):
    """
    Interactive 3D viewer.
    Manages multiple independent layers (original cloud + segments).
    All layers render with the same thickness colormap.
    Polygon selection via VTK-native 2D overlay.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = ViewerSignals()

        self._layers: List[Layer]       = []
        self._actors: Dict[str, object] = {}
        self._sel_actor                 = None

        self.sel_points:    Optional[np.ndarray] = None
        self.sel_distances: Optional[np.ndarray] = None

        self.point_size = 3
        self.colormap   = 'jet'
        self.min_target = 20
        self.max_target = 40

        self.annotation_manager = AnnotationManager()
        self.annotation_manager.register("text",   TextAnnotation(self))
        self.annotation_manager.register("line",   LineAnnotation(self))
        self.annotation_manager.register("delete", DeleteAnnotation(self))
        self.annotation_manager.register("move",   MoveAnnotation(self))
        self.annotation_manager.register("style",  EditStyleAnnotation(self))

        self._setup_ui()

    # ------------------------------------------------------------------ setup
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        frame = QFrame()
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(0, 0, 0, 0)

        # Annotation/segment tool buttons are constructed here (so this class
        # keeps owning the annotation_manager checkable-group logic) but are
        # NOT placed in a toolbar of their own — MainWindow embeds them into
        # its main QToolBar, keeping the 3D viewport itself full-height.
        self._build_tool_buttons()

        self.plotter = QtInteractor(frame)
        fl.addWidget(self.plotter.interactor)
        fl.addWidget(self._build_view_angle_bar())
        layout.addWidget(frame)

        self.plotter.set_background('white')
        self.plotter.add_axes()
        self.plotter.enable_rubber_band_style()

        self._overlay_renderer = vtk.vtkRenderer()
        self._overlay_renderer.SetLayer(1)
        self._overlay_renderer.InteractiveOff()
        self.plotter.ren_win.SetNumberOfLayers(2)
        self.plotter.ren_win.AddRenderer(self._overlay_renderer)

        self._iren = self.plotter.ren_win.GetInteractor()

        self._annotation_layer_name  = None
        self._annotation_preview_actor  = None
        self._annotation_preview_actors = []
        self._annotations = []

        self._edit_picker = vtk.vtkPropPicker()
        self._last_click_time = 0.0
        self._last_click_pos = None

        self._picker = VTKPolygonPicker(
            plotter          = self.plotter,
            on_closed        = self._on_polygon_closed,
            on_cancelled     = self._on_polygon_cancelled,
            overlay_renderer = self._overlay_renderer,
        )
        self._setup_interactor_events()

        self.annotation_manager.activate("text")
        self.annotation_manager.activate(None)

    def _build_tool_buttons(self):
        from pps_report.gui.lucide_icons import load_icon
        from pps_report.gui.theme import get_colors

        icon_size = QSize(20, 20)
        icon_color = get_colors()["text_main"]
        self._icon_recipes = {}

        def make_button(text, icon_name, tooltip, checkable, shortcut=None):
            btn = QToolButton()
            btn.setText(text)
            btn.setIcon(load_icon(icon_name, icon_color))
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setIconSize(icon_size)
            btn.setCheckable(checkable)
            btn.setToolTip(tooltip + (f" ({shortcut})" if shortcut else ""))
            if shortcut:
                QShortcut(QKeySequence(shortcut), self).activated.connect(btn.click)
            self._icon_recipes[btn] = icon_name
            return btn

        self.btn_add_text = make_button(
            "Text", "type", "Add a text annotation", True, "T")
        self.btn_add_text.clicked.connect(lambda: self.annotation_manager.activate("text"))

        self.btn_add_line = make_button(
            "Line", "minus", "Add a leader-line annotation", True, "L")
        self.btn_add_line.clicked.connect(lambda: self.annotation_manager.activate("line"))

        self.btn_move_annot = make_button(
            "Move", "move", "Move an existing annotation", True, "M")
        self.btn_move_annot.clicked.connect(lambda: self.annotation_manager.activate("move"))

        self.btn_delete_annot = make_button(
            "Delete", "x-circle", "Delete an existing annotation", True, "D")
        self.btn_delete_annot.clicked.connect(lambda: self.annotation_manager.activate("delete"))

        self.btn_edit_style = make_button(
            "Style", "sliders-horizontal",
            "Click an annotation to edit its text/color/font/line width", True)
        self.btn_edit_style.clicked.connect(lambda: self.annotation_manager.activate("style"))

        self.btn_delete_segment = make_button(
            "Delete Seg.", "trash-2",
            "Delete the segment selected in Layer Manager", False)
        self.btn_delete_segment.clicked.connect(self.signals.delete_segment_requested.emit)

        self.btn_merge_segments = make_button(
            "Merge", "git-merge",
            "Merge the segments selected in Layer Manager into one", False)
        self.btn_merge_segments.clicked.connect(self.signals.merge_segments_requested.emit)

        self.btn_undo = make_button("Undo", "undo-2", "Undo", False, "Ctrl+Z")
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(self.signals.undo_requested.emit)

        self.btn_redo = make_button("Redo", "redo-2", "Redo", False, "Ctrl+Y")
        self.btn_redo.setEnabled(False)
        self.btn_redo.clicked.connect(self.signals.redo_requested.emit)

        self._tool_buttons = [
            self.btn_add_text, self.btn_add_line,
            self.btn_move_annot, self.btn_delete_annot, self.btn_edit_style,
            self.btn_delete_segment, self.btn_merge_segments,
        ]
        self._set_tool_buttons_enabled(False)

        # Default annotation style (set via each annotation's own dialog now;
        # remembers the last-used values as defaults for the next annotation).
        self._annotation_color = "#000000"
        self._annotation_font_family = "Arial"
        self._annotation_font_size = 14
        self._annotation_line_width = 2
        self._annotation_bold = True
        self._annotation_italic = False

    def _build_view_angle_bar(self) -> QWidget:
        """Compact docked strip of camera-view shortcuts (Top/Front/etc)."""
        bar = QWidget()
        bar.setObjectName("view_angle_bar")
        bar.setStyleSheet("""
            QWidget#view_angle_bar { background: transparent; }
            QPushButton {
                background: #ffffff; color: #1e293b;
                border: 1px solid #cbd5e1; border-radius: 5px;
                min-width: 30px; max-width: 40px; padding: 4px 2px;
                font-size: 11px; font-weight: 600; text-align: center;
            }
            QPushButton:hover { background: #f1f5f9; border-color: #3b82f6; }
        """)
        row = QHBoxLayout(bar)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(6)
        row.addStretch()
        for label, tooltip, fn in [
            ("T",   "Top view (1)",    self.view_top),
            ("G",   "Bottom view (2)", self.view_bottom),
            ("F",   "Front view (3)",  self.view_front),
            ("B",   "Back view (4)",   self.view_back),
            ("R",   "Right view (5)",  self.view_right),
            ("L",   "Left view (6)",   self.view_left),
            ("ISO", "Isometric view (7)", self.view_iso),
        ]:
            btn = QPushButton(label)
            btn.setToolTip(tooltip)
            btn.clicked.connect(fn)
            row.addWidget(btn)
        row.addStretch()
        return bar

    def _setup_interactor_events(self):
        self._iren.AddObserver('LeftButtonPressEvent',   self._on_left_click)
        self._iren.AddObserver('MouseMoveEvent',         self._on_mouse_move)
        self._iren.AddObserver('LeftButtonReleaseEvent', self._on_left_release)
        self._iren.AddObserver('KeyPressEvent',          self._on_key_press)

    def _set_tool_buttons_enabled(self, enabled: bool):
        for btn in self._tool_buttons:
            btn.setEnabled(enabled)

    # ------------------------------------------------------------------ layer sync
    def sync_layers(self, layers: List[Layer]):
        self._layers = layers

    # ------------------------------------------------------------------ add / remove
    def assign_colors(self, layer: Layer,
                      color1=np.array([1.0, 0.0, 0.0], dtype=np.float32),
                      color2=np.array([0.0, 1.0, 0.0], dtype=np.float32),
                      color3=np.array([0.0, 0.0, 1.0], dtype=np.float32),
                      color4=np.array([0.0, 0.0, 1.0], dtype=np.float32)) -> np.ndarray:
        min_target = self.min_target
        max_target = self.max_target
        distances  = layer.distances
        colors     = np.zeros((len(distances), 3), dtype=np.float32)

        colors[distances < min_target] = color1
        colors[(distances >= min_target) & (distances <= max_target)] = color2
        colors[(distances > max_target) & (distances < 150)] = color3
        colors[distances >= 150] = color4
        return colors

    def add_layer(self, layer: Layer):
        self._drop_actor(layer.name)
        cloud = pv.PolyData(layer.points)
        cloud['thickness'] = layer.distances
        cloud['colors']    = self.assign_colors(layer)

        actor = self.plotter.add_mesh(
            cloud,
            scalars='colors',
            rgb=True,
            point_size=self.point_size,
            render_points_as_spheres=True,
            show_scalar_bar=False,
            name=f"layer_{layer.name}",
        )
        self._actors[layer.name] = actor
        if not layer.visible:
            actor.SetVisibility(False)
            self.plotter.render()

    def remove_layer(self, name: str):
        self._drop_actor(name)
        self._remove_annotation_actors_for_layer(name)

    def _drop_actor(self, name: str):
        actor = self._actors.pop(name, None)
        if actor is not None:
            try:
                self.plotter.remove_actor(actor)
            except Exception:
                pass

    def clear_all_layers(self):
        for name in list(self._actors.keys()):
            self._drop_actor(name)
        self._remove_annotation_actors_for_layer(name="all")
        self._layers = []
        self.clear_selection()
        try:
            self.plotter.clear()
            self.plotter.add_axes()
            self.plotter.enable_rubber_band_style()
            self.plotter.ren_win.SetNumberOfLayers(2)
            self.plotter.ren_win.AddRenderer(self._overlay_renderer)
        except Exception:
            pass

    # ------------------------------------------------------------------ visibility
    def set_layer_visible(self, name: str, visible: bool):
        actor = self._actors.get(name)
        if actor is not None:
            actor.SetVisibility(visible)
            self.plotter.render()

        for ann in self._annotations:
            if ann['layer_name'] != name:
                continue
            ann_actor = ann['annotation']['actor']
            if isinstance(ann_actor, dict):
                for a in ann_actor.values():
                    a.SetVisibility(visible)
            else:
                ann_actor.SetVisibility(visible)

    # ------------------------------------------------------------------ settings
    def set_thickness_targets(self, min_t: float, max_t: float):
        self.min_target = min_t
        self.max_target = max_t
        for layer in self._layers:
            self.add_layer(layer)

    def set_colormap(self, cmap: str):
        self.colormap = cmap
        for layer in self._layers:
            self.add_layer(layer)

    def set_point_size(self, size: int):
        self.point_size = size
        for layer in self._layers:
            self.add_layer(layer)

    def set_theme(self, mode: str):
        """Recolor toolbar icons for the given theme. The 3D canvas itself
        always stays white regardless of Light/Dark mode (point-cloud
        colors are calibrated against a white background)."""
        self.plotter.set_background('white')
        self.plotter.render()
        self.refresh_icons(mode)

    def refresh_icons(self, mode: str = None):
        """Recolor toolbar icons to match the given (or current) theme."""
        from pps_report.gui.lucide_icons import load_icon
        from pps_report.gui.theme import get_colors
        color = get_colors(mode)["text_main"]
        for btn, name in self._icon_recipes.items():
            btn.setIcon(load_icon(name, color))

    # ------------------------------------------------------------------ polygon mode
    def enable_polygon_mode(self):
        if not self._layers:
            return
        self._picker.start()

    def disable_polygon_mode(self):
        if self._picker.is_active:
            self._picker.stop()

    def set_annotation_layer(self, layer_name: str):
        self._annotation_layer_name = layer_name

    def enable_annotation_mode(self, action: str, text: str = None):
        if self._picker.is_active:
            return
        self.annotation_manager.activate(action)

    # ------------------------------------------------------------------ toolbar helpers
    def _reset_toolbar_buttons(self):
        for btn in self._tool_buttons:
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)

    def _current_annotation_style(self):
        """Default style for a new annotation — the last style used, or the
        built-in defaults on first use."""
        return {
            "color":       self._annotation_color,
            "line_width":  self._annotation_line_width,
            "font_size":   self._annotation_font_size,
            "font_family": self._annotation_font_family,
            "bold":        self._annotation_bold,
            "italic":      self._annotation_italic,
        }

    def _remember_annotation_style(self, values: dict):
        """Remember a just-used style as the default for the next annotation."""
        self._annotation_color = values.get("color", self._annotation_color)
        self._annotation_font_family = values.get("font_family", self._annotation_font_family)
        self._annotation_font_size = values.get("font_size", self._annotation_font_size)
        self._annotation_line_width = values.get("line_width", self._annotation_line_width)
        self._annotation_bold = values.get("bold", self._annotation_bold)
        self._annotation_italic = values.get("italic", self._annotation_italic)

    @staticmethod
    def _set_font_family(text_property, family: str):
        if family == "Courier":
            text_property.SetFontFamilyToCourier()
        elif family == "Times":
            text_property.SetFontFamilyToTimes()
        else:
            text_property.SetFontFamilyToArial()

    def apply_annotation_edit(self, item: dict, values: dict):
        """Update an existing annotation's text/color/font/line-width in place."""
        self.signals.state_changing.emit()
        self._remember_annotation_style(values)
        ann = item["annotation"]
        ann["color"] = values["color"]
        ann["font_size"] = values["font_size"]
        ann["font_family"] = values["font_family"]
        if "bold" in values:
            ann["bold"] = values["bold"]
        if "italic" in values:
            ann["italic"] = values["italic"]
        if "line_width" in values:
            ann["line_width"] = values["line_width"]
        text_changed = "text" in values and values["text"] != ann.get("text")
        if "text" in values:
            ann["text"] = values["text"]

        qcolor = QColor(values["color"])
        rgb = qcolor.getRgbF()[:3]
        actor = ann.get("actor")

        text_actor = actor.get("text_actor") if isinstance(actor, dict) else actor
        line_actor = actor.get("line_actor") if isinstance(actor, dict) else None

        if text_actor is not None:
            prop = text_actor.GetTextProperty()
            prop.SetFontSize(values["font_size"])
            prop.SetColor(*rgb)
            self._set_font_family(prop, values["font_family"])
            prop.SetBold(bool(ann.get("bold", True)))
            prop.SetItalic(bool(ann.get("italic", False)))
            if text_changed:
                text_actor.SetInput(ann["text"])

        if line_actor is not None:
            lprop = line_actor.GetProperty()
            lprop.SetColor(*rgb)
            lprop.SetLineWidth(values.get("line_width", ann.get("line_width", 2)))

        self.plotter.ren_win.Render()

        self.signals.annotation_added.emit(
            item["layer_name"],
            {"action": "move", "annotation": ann},
        )

    # ------------------------------------------------------------------ interactor callbacks
    def _on_left_click(self, obj, event):
        x, y = self._iren.GetEventPosition()

        # Double-click-to-edit: only when idle (no annotation tool active,
        # not mid-polygon-selection) so it doesn't interfere with any tool.
        if self.annotation_manager.active_annotation is None and not self._picker.is_active:
            now = time.time()
            is_dbl = (
                self._last_click_pos is not None
                and now - self._last_click_time < 0.35
                and abs(x - self._last_click_pos[0]) < 8
                and abs(y - self._last_click_pos[1]) < 8
            )
            self._last_click_time = now
            self._last_click_pos = (x, y)
            if is_dbl:
                self._try_edit_annotation_at(x, y)
                return

        tool = self.annotation_manager.active_annotation
        if not tool:
            return
        tool.on_left_click(x, y)

    def _try_edit_annotation_at(self, x, y):
        self._edit_picker.Pick(x, y, 0, self._overlay_renderer)
        actor = self._edit_picker.GetViewProp()
        if actor is None:
            return

        target = None
        for item in self._annotations:
            ann_actor = item["annotation"].get("actor")
            if ann_actor == actor or (isinstance(ann_actor, dict) and actor in ann_actor.values()):
                target = item
                break
        if target is None:
            return

        ann = target["annotation"]
        dialog = AnnotationEditDialog(
            parent=self,
            initial_text=ann.get("text") or "",
            initial_color=QColor(ann.get("color", "#000000")),
            initial_font_family=ann.get("font_family", "Arial"),
            initial_font_size=ann.get("font_size", 14),
            initial_line_width=ann.get("line_width", 2),
            initial_bold=ann.get("bold", True),
            initial_italic=ann.get("italic", False),
            show_line_width=(ann.get("type") == "line_text"),
        )
        if dialog.exec() == AnnotationEditDialog.Accepted:
            self.apply_annotation_edit(target, dialog.values())

    def _on_mouse_move(self, obj, event):
        tool = self.annotation_manager.active_annotation
        if not tool:
            return
        x, y = self._iren.GetEventPosition()
        tool.on_mouse_move(x, y)

    def _on_left_release(self, obj, event):
        tool = self.annotation_manager.active_annotation
        if not tool:
            return
        x, y = self._iren.GetEventPosition()
        tool.on_left_release(x, y)

    def _on_key_press(self, obj, event):
        tool = self.annotation_manager.active_annotation
        if not tool:
            return
        key = self._iren.GetKeySym()
        tool.on_key_press(key)

    # ------------------------------------------------------------------ annotation preview
    def _clear_annotation_preview(self):
        if self._annotation_preview_actor is not None:
            try:
                self._overlay_renderer.RemoveActor(self._annotation_preview_actor)
            except Exception:
                pass
            self._annotation_preview_actor = None

        for actor in self._annotation_preview_actors:
            try:
                self._overlay_renderer.RemoveActor(actor)
            except Exception:
                pass
        self._annotation_preview_actors = []
        self.plotter.ren_win.Render()



    def _update_text_preview(self, annotation):
        self._clear_annotation_preview()

        if annotation.get("text_position") is None or not annotation.get("text"):
            return

        actor = self._create_text_actor(annotation)
        actor.GetProperty().SetOpacity(0.85)
        self._annotation_preview_actors.append(actor)
        
    def _update_line_text_preview(self, annotation):
        self._clear_annotation_preview()
        if annotation is None:
            return

        actors = self._build_line_text_actors(annotation, preview=True)
        self._overlay_renderer.AddActor(actors["line_actor"])
        self._overlay_renderer.AddActor(actors["text_actor"])
        self._annotation_preview_actors = list(actors.values())
        self.plotter.ren_win.Render()

    # ------------------------------------------------------------------ project restore
    def restore_annotations(self, layer_name: str, annotations: list):
        """Recreate VTK actors for annotations loaded from a saved project.

        Mutates each annotation dict in place (adding its "actor") so
        identity is shared with the caller's Layer.annotations list.
        """
        for ann in annotations:
            if ann.get("type") == "line_text":
                actor = self._create_line_text_actor(ann)
            else:
                actor = self._create_text_actor(ann)
            ann["actor"] = actor
            self._annotations.append({"layer_name": layer_name, "annotation": ann})

    # ------------------------------------------------------------------ annotation builders
    def _build_line_polydata(self, points):
        if len(points) < 2:
            return None

        vtk_points = vtk.vtkPoints()
        for p in points:
            x, y = p[0], p[1]
            z    = p[2] if len(p) > 2 else 0.0
            vtk_points.InsertNextPoint(x, y, z)

        line = vtk.vtkPolyLine()
        line.GetPointIds().SetNumberOfIds(len(points))
        for i in range(len(points)):
            line.GetPointIds().SetId(i, i)

        lines = vtk.vtkCellArray()
        lines.InsertNextCell(line)

        poly = vtk.vtkPolyData()
        poly.SetPoints(vtk_points)
        poly.SetLines(lines)
        return poly

    def _build_text_actor(self, annotation, preview=False):
        text_actor = vtk.vtkTextActor()
        text_actor.SetInput(annotation.get("text", ""))

        text_pos = annotation.get("text_position", (0, 0))
        if text_pos:
            text_actor.SetDisplayPosition(*text_pos)

        prop = text_actor.GetTextProperty()
        prop.SetFontSize(annotation.get("font_size", 12))
        self._set_font_family(prop, annotation.get("font_family", "Arial"))

        color = annotation.get("color", "#000000")
        qcolor = QColor(color) if isinstance(color, str) else color
        rgb = qcolor.getRgbF()[:3]
        prop.SetColor(*rgb)
        prop.SetBold(bool(annotation.get("bold", True)))
        prop.SetItalic(bool(annotation.get("italic", False)))

        # "Callout" card look: soft, misty gray translucent background,
        # no border. VTK's 2D text rendering has no rounded-corner or
        # blur/shadow support, so this is the closest practical
        # approximation without a much larger rendering change.
        prop.SetBackgroundColor(0.5, 0.5, 0.5)
        prop.SetBackgroundOpacity(0.25 if preview else 0.55)
        prop.SetFrame(False)
        return text_actor

    def _build_line_actor(self, annotation, preview=False):
        poly = self._build_line_polydata(annotation.get("points", []))
        if poly is None:
            return None

        mapper = vtk.vtkPolyDataMapper2D()
        mapper.SetInputData(poly)

        line_actor = vtk.vtkActor2D()
        line_actor.SetMapper(mapper)

        color = annotation.get("color", "#000000")
        qcolor = QColor(color) if isinstance(color, str) else color
        line_actor.GetProperty().SetColor(*qcolor.getRgbF()[:3])
        line_actor.GetProperty().SetLineWidth(annotation.get("line_width", 2))

        if preview:
            line_actor.GetProperty().SetOpacity(0.6)
            line_actor.GetProperty().SetLineStipplePattern(0xF0F0)
        else:
            line_actor.GetProperty().SetOpacity(1.0)
            line_actor.GetProperty().SetLineStipplePattern(0xFFFF)
        return line_actor

    def _build_line_text_actors(self, annotation: dict, preview=False):
        return {
            "line_actor": self._build_line_actor(annotation, preview),
            "text_actor": self._build_text_actor(annotation, preview),
        }

    def _create_text_actor(self, annotation: dict):
        actor = self._build_text_actor(annotation)
        self._overlay_renderer.AddActor(actor)
        self.plotter.ren_win.Render()
        return actor

    def _create_line_text_actor(self, annotation: dict):
        actors = self._build_line_text_actors(annotation, preview=False)
        self._overlay_renderer.AddActor(actors["line_actor"])
        self._overlay_renderer.AddActor(actors["text_actor"])
        self.plotter.ren_win.Render()
        return actors

    # ------------------------------------------------------------------ annotation highlight
    def _set_annotation_highlight(self, item: dict, highlighted: bool):
        """Show a colored frame/thicker line on an annotation while it is selected."""
        if not item:
            return
        ann = item["annotation"]
        actor = ann.get("actor")
        highlight_color = (0.15, 0.55, 0.95)

        text_actor = actor.get("text_actor") if isinstance(actor, dict) else (
            actor if ann.get("type") == "text" else None
        )
        line_actor = actor.get("line_actor") if isinstance(actor, dict) else None

        if text_actor is not None:
            prop = text_actor.GetTextProperty()
            prop.SetFrame(highlighted)
            if highlighted:
                prop.SetFrameColor(*highlight_color)
                prop.SetFrameWidth(2)

        if line_actor is not None:
            line_prop = line_actor.GetProperty()
            base_width = ann.get("line_width", 2)
            if highlighted:
                line_prop.SetColor(*highlight_color)
                line_prop.SetLineWidth(base_width + 2)
            else:
                color = ann.get("color", "#000000")
                qcolor = QColor(color) if isinstance(color, str) else color
                line_prop.SetColor(*qcolor.getRgbF()[:3])
                line_prop.SetLineWidth(base_width)

        self.plotter.ren_win.Render()

    # ------------------------------------------------------------------ annotation removal
    def _delete_annotation_by_layer(self, layer_name: str):
        if layer_name in ("all", None, ""):
            to_remove = self._annotations[:]
        else:
            to_remove = [a for a in self._annotations if a['layer_name'] == layer_name]

        for ann in to_remove:
            actor = ann['annotation']['actor']
            if isinstance(actor, dict):
                for a in actor.values():
                    try: self._overlay_renderer.RemoveActor(a)
                    except: pass
            else:
                try: self._overlay_renderer.RemoveActor(actor)
                except: pass
            self._annotations.remove(ann)

    def _safe_remove_actor(self, annotation: dict, key: str):
        actor = annotation.get(key)
        if actor is None:
            return
        try:
            self._overlay_renderer.RemoveActor(actor)
        except Exception:
            pass
        annotation[key] = None

    def _remove_annotation(self, entry):
        annotation = entry["annotation"]
        actor = annotation.get("actor")
        if isinstance(actor, dict):
            for a in actor.values():
                try: self._overlay_renderer.RemoveActor(a)
                except: pass
        else:
            self._safe_remove_actor(annotation, "actor")
        if entry in self._annotations:
            self._annotations.remove(entry)
        self.plotter.ren_win.Render()

    def _remove_annotation_actors_for_layer(self, name: str):
        if name == "all":
            self._clear_annotation_actors()
            return
        remaining = []
        for entry in self._annotations:
            if entry["layer_name"] == name:
                actor = entry["annotation"].get("actor")
                if isinstance(actor, dict):
                    for a in actor.values():
                        try: self._overlay_renderer.RemoveActor(a)
                        except: pass
                else:
                    self._safe_remove_actor(entry["annotation"], "actor")
            else:
                remaining.append(entry)
        self._annotations = remaining
        self.plotter.ren_win.Render()

    def _clear_annotation_actors(self):
        for entry in self._annotations:
            actor = entry["annotation"].get("actor")
            if isinstance(actor, dict):
                for a in actor.values():
                    try: self._overlay_renderer.RemoveActor(a)
                    except: pass
            else:
                self._safe_remove_actor(entry["annotation"], "actor")
        self._annotations = []
        self.plotter.ren_win.Render()

    # ------------------------------------------------------------------ camera
    def _restore_camera(self):
        try:
            self.plotter.enable_rubber_band_style()
        except Exception:
            try:
                self._iren.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
            except Exception:
                pass
        try:
            self.plotter.ren_win.Render()
        except Exception:
            pass

    def reset_view(self):
        self.plotter.reset_camera()
        self.plotter.view_isometric()

    def view_top(self):    self.plotter.view_yx(-1)
    def view_bottom(self):
        self.plotter.view_yx(render=False)
        self.plotter.camera.Roll(180)
    def view_front(self):  self.plotter.view_yz(-1)
    def view_back(self):   self.plotter.view_yz()
    def view_right(self):  self.plotter.view_xz()
    def view_left(self):   self.plotter.view_xz(-1)
    def view_iso(self):
        self.plotter.view_isometric(render=False)
        self.plotter.camera.Azimuth(180)

    # ------------------------------------------------------------------ polygon callbacks
    def _on_polygon_cancelled(self):
        self.signals.polygon_mode_ended.emit()

    def _on_polygon_closed(self, screen_pts: list):
        vis = [l for l in self._layers if l.visible]
        if not vis:
            self.signals.polygon_mode_ended.emit()
            return

        all_pts   = np.concatenate([l.points    for l in vis])
        all_dists = np.concatenate([l.distances for l in vis])

        pts_2d = self._project_to_screen(all_pts)
        if pts_2d is not None:
            from matplotlib.path import Path
            inside = Path(screen_pts).contains_points(pts_2d)
            self.sel_points    = all_pts[inside]
            self.sel_distances = all_dists[inside]
            self._show_selection_highlight(self.sel_points)
            self.signals.selection_changed.emit(self.sel_points, self.sel_distances)
            if len(self.sel_points) > 0:
                self.signals.polygon_selection_confirmed.emit()

        self.signals.polygon_mode_ended.emit()

    # ------------------------------------------------------------------ distance-range selection
    def select_by_distance_range(self, min_d: float, max_d: float):
        vis = [l for l in self._layers if l.visible]
        if not vis:
            return
        all_pts   = np.concatenate([l.points    for l in vis])
        all_dists = np.concatenate([l.distances for l in vis])
        mask = (all_dists >= min_d) & (all_dists <= max_d)
        self.sel_points    = all_pts[mask]
        self.sel_distances = all_dists[mask]
        self._show_selection_highlight(self.sel_points)
        self.signals.selection_changed.emit(self.sel_points, self.sel_distances)

    def clear_selection(self):
        self.sel_points    = None
        self.sel_distances = None
        if self._sel_actor is not None:
            try:
                self.plotter.remove_actor(self._sel_actor)
            except Exception:
                pass
            self._sel_actor = None
        self.signals.selection_cleared.emit()

    def _show_selection_highlight(self, pts: np.ndarray):
        if self._sel_actor is not None:
            try:
                self.plotter.remove_actor(self._sel_actor)
            except Exception:
                pass
            self._sel_actor = None
        if pts is None or len(pts) == 0:
            return
        sel = pv.PolyData(pts)
        self._sel_actor = self.plotter.add_mesh(
            sel,
            color='yellow',
            point_size=self.point_size + 3,
            render_points_as_spheres=True,
            opacity=0.9,
        )

    # ------------------------------------------------------------------ projection
    def _project_to_screen(self, points: np.ndarray) -> Optional[np.ndarray]:
        try:
            renderer = self.plotter.renderer
            camera   = renderer.GetActiveCamera()
            aspect   = renderer.GetTiledAspectRatio()

            def to_np(m):
                return np.array([[m.GetElement(i, j) for j in range(4)]
                                 for i in range(4)], dtype=np.float64)

            V = to_np(camera.GetViewTransformMatrix())
            P = to_np(camera.GetProjectionTransformMatrix(aspect, -1, 1))

            n = len(points)
            h = np.ones((n, 4), dtype=np.float64)
            h[:, :3] = points

            clip = h @ V.T @ P.T
            w    = clip[:, 3:4]
            w    = np.where(np.abs(w) < 1e-10, 1e-10, w)
            ndc  = clip[:, :2] / w

            ww, wh = self.plotter.ren_win.GetSize()
            sx = (ndc[:, 0] + 1.0) * 0.5 * ww
            sy = (ndc[:, 1] + 1.0) * 0.5 * wh

            return np.column_stack([sx, sy])
        except Exception as e:
            logger.warning("_project_to_screen failed: %s", e)
            return None

    # ------------------------------------------------------------------ screenshot
    def get_screenshot(self, path: str = None) -> Optional[str]:
        if path is None:
            import tempfile
            path = os.path.join(tempfile.gettempdir(), 'tunnel_screenshot.png')
        self.plotter.screenshot(path)
        return path

    def close(self):
        self.plotter.close()