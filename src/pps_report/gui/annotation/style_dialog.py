"""
Unified dialog to create/edit an annotation: text, color, font family/size,
and line width (for leader-line annotations).
"""

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QVBoxLayout, QHBoxLayout, QComboBox, QSpinBox, QTextEdit,
    QPushButton, QDialogButtonBox, QColorDialog, QCheckBox,
)
from PySide6.QtGui import QColor

from .annotation_base import FONT_FAMILIES


class AnnotationEditDialog(QDialog):
    def __init__(self, parent=None, initial_text=None, initial_color=QColor(0, 0, 0),
                 initial_font_family="Arial", initial_font_size=14,
                 initial_line_width=2, show_line_width=True,
                 initial_bold=True, initial_italic=False):
        super().__init__(parent)
        self.setWindowTitle("Annotation")
        self.setModal(True)
        self._color = QColor(initial_color)
        self._show_text = initial_text is not None

        layout = QVBoxLayout(self)

        self.text_edit = None
        if self._show_text:
            self.text_edit = QTextEdit(self)
            self.text_edit.setPlainText(initial_text)
            self.text_edit.setFixedHeight(100)
            layout.addWidget(self.text_edit)

        form = QFormLayout()

        self.btn_color = QPushButton()
        self.btn_color.setFixedSize(32, 24)
        self._update_color_button()
        self.btn_color.clicked.connect(self._choose_color)
        form.addRow("Color:", self.btn_color)

        self.cmb_font_family = QComboBox()
        self.cmb_font_family.addItems(FONT_FAMILIES)
        idx = self.cmb_font_family.findText(initial_font_family)
        self.cmb_font_family.setCurrentIndex(idx if idx >= 0 else 0)
        form.addRow("Font:", self.cmb_font_family)

        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(8, 72)
        self.spin_font_size.setValue(initial_font_size)
        form.addRow("Font size:", self.spin_font_size)

        style_row = QHBoxLayout()
        self.chk_bold = QCheckBox("Bold")
        self.chk_bold.setChecked(initial_bold)
        self.chk_italic = QCheckBox("Italic")
        self.chk_italic.setChecked(initial_italic)
        style_row.addWidget(self.chk_bold)
        style_row.addWidget(self.chk_italic)
        style_row.addStretch()
        form.addRow("Style:", style_row)

        self.spin_line_width = QSpinBox()
        self.spin_line_width.setRange(1, 10)
        self.spin_line_width.setValue(initial_line_width)
        if show_line_width:
            form.addRow("Line width:", self.spin_line_width)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        if self._show_text and not self.text_edit.toPlainText().strip():
            # Empty text is treated as cancel — matches prior TextAnnotation behavior.
            self.reject()
            return
        self.accept()

    def _update_color_button(self):
        self.btn_color.setStyleSheet(
            f"background-color: {self._color.name()}; border: 1px solid #888; border-radius: 4px;"
        )

    def _choose_color(self):
        color = QColorDialog.getColor(self._color, self, "Select annotation color")
        if color.isValid():
            self._color = color
            self._update_color_button()

    def values(self) -> dict:
        result = {
            "color": self._color.name(),
            "font_family": self.cmb_font_family.currentText(),
            "font_size": self.spin_font_size.value(),
            "line_width": self.spin_line_width.value(),
            "bold": self.chk_bold.isChecked(),
            "italic": self.chk_italic.isChecked(),
        }
        if self._show_text:
            result["text"] = self.text_edit.toPlainText().strip()
        return result
