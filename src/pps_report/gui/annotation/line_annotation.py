from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from .annotation_base import Annotation
from .style_dialog import AnnotationEditDialog


class LineAnnotation(Annotation):
    STATE_START = 0
    STATE_END = 1
    STATE_TEXT = 2

    def __init__(self, viewer):
        super().__init__(viewer)
        self.start = None
        self.end = None
        self.text_pos = None
        self.text = ""
        self.state = self.STATE_START

    def on_activate(self):
        self._active = True
        self._reset()
        self.viewer.setCursor(Qt.CrossCursor)

    def on_deactivate(self):
        self._active = False
        self.viewer.unsetCursor()
        self.viewer._update_line_text_preview(None)
        self.viewer._restore_camera()
        self.viewer._reset_toolbar_buttons()

        self._reset()

    def _reset(self):
        self.start = None
        self.end = None
        self.text_pos = None
        self.text = ""
        self.state = self.STATE_START
        self.viewer._clear_annotation_preview()

    # -------------------------
    # CLICK HANDLING
    # -------------------------
    def on_left_click(self, x, y):

        viewer = self.viewer
        # STEP 1: chọn start
        if self.state == self.STATE_START:
            self.start = (x, y)
            self.state = self.STATE_END
            style = viewer._current_annotation_style()
            self.annotation.update({
                "type": "text",
                "color": style["color"],
                "font_size": style["font_size"],
                "font_family": style["font_family"],
                "bold": style["bold"],
                "italic": style["italic"],
                "text": None,
            })
            return

        # STEP 2: chọn end + hỏi text + style
        if self.state == self.STATE_END:
            self.end = (x, y)

            default_style = viewer._current_annotation_style()
            dialog = AnnotationEditDialog(
                parent=viewer,
                initial_text="",
                initial_color=QColor(default_style["color"]),
                initial_font_family=default_style["font_family"],
                initial_font_size=default_style["font_size"],
                initial_line_width=default_style["line_width"],
                initial_bold=default_style["bold"],
                initial_italic=default_style["italic"],
                show_line_width=True,
            )
            if dialog.exec() != AnnotationEditDialog.Accepted:
                self._reset()
                self.on_cancel()
                return

            values = dialog.values()
            self.text = values["text"]
            viewer._remember_annotation_style(values)
            self.annotation.update({
                "text": self.text,
                "color": values["color"],
                "font_size": values["font_size"],
                "font_family": values["font_family"],
                "line_width": values["line_width"],
                "bold": values["bold"],
                "italic": values["italic"],
            })
            self.state = self.STATE_TEXT
            return

        # STEP 3: chọn vị trí text → finalize
        if self.state == self.STATE_TEXT:
            self.text_pos = (x, y)

            self.create_annotation()

            self.on_finish()

    # -------------------------
    # PREVIEW LINE
    # -------------------------
    def on_mouse_move(self, x, y):
        if self.end is None:
            self.annotation.update({
                'points': [self.start, (x, y), (x, y)],
            })
        else:
            self.annotation.update({
                'points': [self.start, self.end, (x, y)],
                'text_position': (x, y),
            })

        if self.start is not None:
            self.viewer._update_line_text_preview(self.annotation)

    # -------------------------
    # CREATE FINAL ANNOTATION
    # -------------------------
    def create_annotation(self):
        viewer = self.viewer

        annotation = {
            "type": "line_text",
            "text": self.text,
            "color": self.annotation["color"],
            "text_position": self.text_pos,
            "font_size": self.annotation["font_size"],
            "font_family": self.annotation["font_family"],
            "bold": self.annotation.get("bold", True),
            "italic": self.annotation.get("italic", False),
            'points': [self.start, self.end, self.text_pos],
            "line_width": self.annotation["line_width"],
        }

        actor = viewer._create_line_text_actor(annotation)
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

    def on_finish(self):
        self.viewer.annotation_manager.activate(None)

    def on_cancel(self):
        self.viewer.annotation_manager.activate(None)
