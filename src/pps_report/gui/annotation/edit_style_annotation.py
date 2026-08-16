"""
Click an existing annotation to edit its color / font / line width in place.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
import vtk

from .annotation_base import Annotation
from .style_dialog import AnnotationEditDialog


class EditStyleAnnotation(Annotation):

    def __init__(self, viewer):
        super().__init__(viewer)
        self._picker = vtk.vtkPropPicker()

    def on_activate(self):
        self._active = True
        self.viewer.setCursor(Qt.PointingHandCursor)

    def on_deactivate(self):
        self._active = False
        self.viewer.unsetCursor()
        self.viewer._restore_camera()
        self.viewer._reset_toolbar_buttons()

    def on_finish(self):
        self.viewer.annotation_manager.activate(None)

    def on_cancel(self):
        self.viewer.annotation_manager.activate(None)

    def on_left_click(self, x, y):
        viewer = self.viewer

        self._picker.Pick(x, y, 0, viewer._overlay_renderer)
        actor = self._picker.GetViewProp()
        if actor is None:
            return

        target = None
        for item in viewer._annotations:
            ann_actor = item["annotation"].get("actor")
            if ann_actor == actor or (isinstance(ann_actor, dict) and actor in ann_actor.values()):
                target = item
                break

        if target is None:
            return

        ann = target["annotation"]
        dialog = AnnotationEditDialog(
            parent=viewer,
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
            viewer.apply_annotation_edit(target, dialog.values())

        self.on_finish()
