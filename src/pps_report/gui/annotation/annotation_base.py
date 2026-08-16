
from PySide6.QtCore import Qt

FONT_FAMILIES = ["Arial", "Courier", "Times"]

annotation_template = {
    "type": "text",   # "text" | "line" | "line_text"
    "color": "#000000",
    "font_size": 14,
    "font_family": "Arial",
    "bold": True,
    "italic": False,
    "points": [],
    "text": "",
    "text_position": (0, 0),
    "line_width": 2,
    "actor": None
}

class Annotation:
    def __init__(self, viewer):
        self.viewer = viewer
        self.annotation = annotation_template.copy()

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    def on_cancel(self):
        pass

    def on_finish(self):
        pass

    def on_left_click(self, x, y):
        pass

    def on_mouse_move(self, x, y):
        pass

    def on_left_release(self, x, y):
        pass

    def on_right_click(self, x, y):
        pass

    def on_key_press(self, key):
        if key.lower() == "escape":
            self.on_cancel()