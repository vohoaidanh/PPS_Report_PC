from PySide6.QtCore import Qt
from .annotation_base import Annotation
import vtk


class MoveAnnotation(Annotation):

    def __init__(self, viewer):
        super().__init__(viewer)
        self._picker = vtk.vtkPropPicker()
        self._selected_item = None
        self._dragging = False
        self._last_x = 0
        self._last_y = 0

    def on_activate(self):
        self._active = True
        self.viewer.setCursor(Qt.SizeAllCursor)

    def on_deactivate(self):
        self._active = False
        self.viewer.unsetCursor()
        self.viewer._restore_camera()
        self.viewer._reset_toolbar_buttons()
        self._clear()

    def on_finish(self):
        self.viewer.annotation_manager.activate(None)

    def on_cancel(self):
        self.viewer.annotation_manager.activate(None)

    def _clear(self):
        if self._selected_item is not None:
            self.viewer._set_annotation_highlight(self._selected_item, False)
        self._selected_item = None
        self._dragging = False

    # =========================
    # PICK
    # =========================
    def on_left_click(self, x, y):
        viewer = self.viewer

        self._picker.Pick(x, y, 0, viewer._overlay_renderer)
        actor = self._picker.GetViewProp()

        if actor is None:
            return

        for item in viewer._annotations:
            ann = item["annotation"]
            ann_actor = ann.get("actor")

            if ann_actor == actor:
                self._selected_item = item
                break

            if isinstance(ann_actor, dict):
                if actor in ann_actor.values():
                    self._selected_item = item
                    break

        if self._selected_item is None:
            return

        self.viewer._set_annotation_highlight(self._selected_item, True)
        self._dragging = True
        self._last_x = x
        self._last_y = y

    # =========================
    # DRAG
    # =========================
    def on_mouse_move(self, x, y):
        if not self._dragging or not self._selected_item:
            return

        dx = x - self._last_x
        dy = y - self._last_y
        self._last_x = x
        self._last_y = y

        ann = self._selected_item["annotation"]

        if ann.get("type") == "text":
            actor = ann.get("actor")
            if actor:
                pos = actor.GetPosition()
                actor.SetPosition(pos[0] + dx, pos[1] + dy)

        elif ann.get("type") == "line_text":
            actors = ann.get("actor", {})

            line_actor = actors.get("line_actor")
            if line_actor:
                pos = line_actor.GetPosition()
                line_actor.SetPosition(pos[0] + dx, pos[1] + dy)

            text_actor = actors.get("text_actor")
            if text_actor:
                pos = text_actor.GetPosition()
                text_actor.SetPosition(pos[0] + dx, pos[1] + dy)

        self.viewer.plotter.ren_win.Render()

    # =========================
    # RELEASE
    # =========================
    def on_left_release(self, x, y):
        if not self._dragging:
            return
        self._dragging = False
        self._clear()
        self.on_finish()