# -*- coding: utf-8 -*-
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect


def apply_shadow(widget, blur=50, y_offset=8, opacity=15):
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(blur)
    shadow.setXOffset(0)
    shadow.setYOffset(y_offset)
    shadow.setColor(QColor(0, 0, 0, opacity))
    widget.setGraphicsEffect(shadow)


class CardFrame(QFrame):
    def __init__(self, parent=None, blur=50, y_offset=8, opacity=15):
        super().__init__(parent)
        self.setObjectName("card")
        apply_shadow(self, blur=blur, y_offset=y_offset, opacity=opacity)
