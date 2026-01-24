# -*- coding: utf-8 -*-
import html
from datetime import datetime

from PySide6.QtWidgets import QTextEdit


class LogViewer(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logViewer")
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.WidgetWidth)

    def append_log(self, message: str, color: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        safe_message = html.escape(message).replace("\r\n", "\n").replace("\r", "\n")
        safe_message = safe_message.replace("\n", "<br>")

        text_color = "#333333"
        bg_color = "#FFFFFF"
        indicator_color = "transparent"

        if "#00D26A" in color:
            indicator_color = "#34C759"
            bg_color = "#F2FCF5"
        elif "#FF3B30" in color:
            indicator_color = "#FF3B30"
            bg_color = "#FFF5F5"
        elif "#FF9500" in color:
            indicator_color = "#FF9500"
            bg_color = "#FFF8E1"

        html_line = (
            f'<table width="100%" cellpadding="4" cellspacing="0" '
            f'style="background-color: {bg_color}; margin-bottom: 2px;">'
            f'<tr>'
            f'<td width="4" style="background-color: {indicator_color};"></td>'
            f'<td width="60" valign="top" style="color: #8E8E93; font-size: 11px;">{timestamp}</td>'
            f'<td valign="top" style="color: {text_color}; font-size: 12px;">{safe_message}</td>'
            f'</tr>'
            f'</table>'
        )
        self.append(html_line)
        self.ensureCursorVisible()
