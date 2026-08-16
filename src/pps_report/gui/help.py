from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget
)
from PySide6.QtCore import Qt

from pps_report.gui.theme import get_colors


class HotkeysDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.resize(500, 500)

        c = get_colors()

        main_layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)

        def section(title, text):
            box = QFrame()
            box.setStyleSheet(f"""
                QFrame {{
                    background: {c['bg_secondary']};
                    border: 1px solid {c['border']};
                    border-radius: 8px;
                    padding: 10px;
                }}
            """)
            v = QVBoxLayout(box)

            lbl_title = QLabel(title)
            lbl_title.setStyleSheet(f"""
                font-size: 15px;
                font-weight: 600;
                color: {c['accent']};
            """)

            lbl_text = QLabel(text)
            lbl_text.setTextFormat(Qt.RichText)
            lbl_text.setStyleSheet(f"""
                font-size: 13px;
                color: {c['text_main']};
            """)
            lbl_text.setWordWrap(True)

            v.addWidget(lbl_title)
            v.addWidget(lbl_text)
            return box

        layout.addWidget(section("File / Viewport", """
        <b>Key O</b> : Open file<br>
        <b>Key R</b> : Reset view<br>
        <b>Ctrl + O</b> : Open file<br>
        <b>Ctrl + S</b> : Save project<br>
        <b>Ctrl + E</b> : Export PDF report
        """))

        layout.addWidget(section("Camera Views", """
        <b>Key 1</b> : Top view<br>
        <b>Key 2</b> : Bottom view<br>
        <b>Key 3</b> : Front view<br>
        <b>Key 4</b> : Back view<br>
        <b>Key 5</b> : Right view<br>
        <b>Key 6</b> : Left view<br>
        <b>Key 7</b> : Isometric view
        """))

        layout.addWidget(section("Mouse", """
        Left drag  : Rotate<br>
        Right drag : Zoom<br>
        Middle     : Pan
        """))

        layout.addWidget(section("Selection / Annotation Tools", """
        <b>Key S</b> : Polygon selection<br>
        <b>Key T</b> : Add Text annotation<br>
        <b>Key L</b> : Add Line annotation<br>
        <b>Key M</b> : Move annotation<br>
        <b>Key D</b> : Delete annotation<br>
        Double-click an annotation : Edit its text/style
        """))

        layout.addWidget(section("Other", """
        <b>Ctrl + Z</b> : Undo<br>
        <b>Ctrl + Y</b> : Redo<br>
        <b>Esc</b> : Cancel current tool
        """))

        layout.addStretch()
        scroll.setWidget(content)

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: {c['accent']};
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {c['accent_hover']};
            }}
        """)
        btn_close.clicked.connect(self.close)

        main_layout.addWidget(scroll)
        main_layout.addWidget(btn_close, alignment=Qt.AlignRight)
