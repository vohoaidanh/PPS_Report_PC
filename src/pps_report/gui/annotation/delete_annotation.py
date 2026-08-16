from PySide6.QtCore import QTimer, Qt
from .annotation_base import Annotation
import vtk


class DeleteAnnotation(Annotation):

    def __init__(self, viewer):
        super().__init__(viewer)
        self._picker = vtk.vtkPropPicker()

    def on_activate(self):
        self._active = True
        self.viewer.setCursor(Qt.ForbiddenCursor)

    def on_deactivate(self):
        self._active = False
        self.viewer.unsetCursor()
        self.viewer._restore_camera()
        self.viewer._reset_toolbar_buttons()

    def on_finish(self):
        self.viewer.annotation_manager.activate(None)

    def on_cancel(self):
        self.viewer.annotation_manager.activate(None)
    # =========================
    # LEFT CLICK → DELETE
    # =========================
    def on_left_click(self, x, y):

        viewer = self.viewer

        # pick actor at screen position
        self._picker.Pick(x, y, 0, viewer._overlay_renderer)

        actor = self._picker.GetViewProp()

        if actor is None:
            return

        # =========================
        # FIND ANNOTATION
        # =========================
        target_index = None
        target_annotation = None

        for i, item in enumerate(viewer._annotations):
            ann = item["annotation"]

            # match by actor (line/text/combined)
            ann_actor = ann.get("actor")

            # case 1: single actor
            if ann_actor == actor:
                target_index = i
                target_annotation = item
                break

            # case 2: line_text (dict of actors)
            if isinstance(ann_actor, dict):
                if actor in ann_actor.values():
                    target_index = i
                    target_annotation = item
                    break

        if target_index is None:
            return

        # =========================
        # REMOVE FROM RENDERER
        # =========================
        ann = target_annotation["annotation"]
        ann_actor = ann.get("actor")

        if isinstance(ann_actor, dict):
            for a in ann_actor.values():
                if a:
                    viewer._overlay_renderer.RemoveActor(a)
        else:
            viewer._overlay_renderer.RemoveActor(ann_actor)


        # =========================
        # REMOVE FROM LIST
        # =========================
        layer_name = target_annotation["layer_name"]
        viewer._annotations.pop(target_index)

        # =========================
        # EMIT SIGNAL
        # =========================
        viewer.signals.annotation_added.emit(
            layer_name,
            {"action": "delete", "annotation": ann},
        )

        self.on_finish()

        