from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from .annotation_base import Annotation
from .style_dialog import AnnotationEditDialog


class TextAnnotation(Annotation):
    name = "text"
    STATE_START = 0
    STATE_END = 1

    def __init__(self, viewer):
        super().__init__(viewer)
        self.text = None
        self.state = self.STATE_START

    def on_activate(self):
        self.viewer.setCursor(Qt.IBeamCursor)
        self._active = True

    def on_deactivate(self):
        self._active = False
        self.viewer.unsetCursor()
        self.text = None
        self.state = self.STATE_START
        self.viewer._clear_annotation_preview()
        self.viewer._restore_camera()
        self.viewer._reset_toolbar_buttons()  # 🔥 FIX button vẫn active

    def on_finish(self):
        self.viewer.annotation_manager.activate(None)

    def on_cancel(self):
        self.viewer.annotation_manager.activate(None)

    def on_mouse_move(self, x, y):
        self.annotation["text_position"] = (int(x), int(y))
        self.annotation["text"] = self.text
        if self.text is not None:
            self.viewer._update_text_preview(self.annotation)

    def create_annotation(self):
        viewer = self.viewer

        annotation = self.annotation.copy()

        actor = viewer._create_text_actor(annotation)

        annotation["actor"] = actor

        viewer._annotations.append({
            "layer_name": viewer._annotation_layer_name,
            "annotation": annotation,
        })

        viewer.signals.annotation_added.emit(
            viewer._annotation_layer_name,
            {
                "action": "add",
                "annotation": annotation,
            }
        )

    def on_left_click(self, x, y):
        if not self._active:
            return

        viewer = self.viewer
        if self.state == self.STATE_START:
            default_style = viewer._current_annotation_style()
            dialog = AnnotationEditDialog(
                parent=viewer,
                initial_text="",
                initial_color=QColor(default_style["color"]),
                initial_font_family=default_style["font_family"],
                initial_font_size=default_style["font_size"],
                initial_bold=default_style["bold"],
                initial_italic=default_style["italic"],
                show_line_width=False,
            )
            if dialog.exec() != AnnotationEditDialog.Accepted:
                self.on_cancel()
                return

            values = dialog.values()
            self.text = values["text"]
            viewer._remember_annotation_style(values)

            self.state = self.STATE_END
            self.annotation.update({
                "type": "text",
                "text": self.text,
                "color": values["color"],
                "font_size": values["font_size"],
                "font_family": values["font_family"],
                "bold": values["bold"],
                "italic": values["italic"],
                "text_position": (int(x), int(y)),
            })

            return

        self.create_annotation()

        self.on_finish()
