# -*- coding: utf-8 -*-
from PySide6.QtCore import Signal, Qt, QSignalBlocker
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSizePolicy


class SegmentedToggle(QWidget):
    """
    仿 iOS 风格的分段开关 (支持多选)
    外观: [ 上午 | 下午 ]
    """
    selectionDatachanged = Signal(list)

    def __init__(self, items: list, parent=None):
        super().__init__(parent)
        self._items = items
        self._buttons = {}
        self._selected_data = set()
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setMinimumHeight(38)

        for label, data in self._items:
            btn = QPushButton(label)
            btn.setObjectName("segmentBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setFixedHeight(38)
            btn.setProperty("toggle_data", data)
            btn.clicked.connect(lambda checked, d=data: self._on_btn_clicked(d, checked))
            self._buttons[data] = btn
            layout.addWidget(btn)

        self.setStyleSheet("""
            QPushButton#segmentBtn {
                background-color: #F5F5F7;
                border: 1px solid #D2D2D7;
                color: #666666;
                border-radius: 0px;
                font-size: 13px;
                font-weight: 500;
                padding: 0;
                margin: 0;
            }
            QPushButton#segmentBtn:checked {
                background-color: #007AFF;
                color: white;
                border: 1px solid #007AFF;
                font-weight: 600;
            }
            QPushButton#segmentBtn:hover:!checked {
                background-color: #F2F2F7;
            }
            QPushButton#segmentBtn:first-child {
                border-top-left-radius: 8px;
                border-bottom-left-radius: 8px;
                border-right: none;
            }
            QPushButton#segmentBtn:last-child {
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
                border-left: none;
            }
            QPushButton#segmentBtn:!first-child:!last-child {
                border-left: none;
            }
        """)

    def _on_btn_clicked(self, data, checked):
        if checked:
            self._selected_data.add(data)
        else:
            self._selected_data.discard(data)
        self.selectionDatachanged.emit(self.get_selected_data())

    def set_selected(self, data_list):
        self._selected_data = set(data_list)
        for data, btn in self._buttons.items():
            with QSignalBlocker(btn):
                btn.setChecked(data in self._selected_data)

    def get_selected_data(self) -> list:
        return [data for label, data in self._items if data in self._selected_data]
