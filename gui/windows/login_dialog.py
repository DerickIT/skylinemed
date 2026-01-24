# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout


class QRLoginDialog(QDialog):
    """Mac 风格二维码登录弹窗"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("扫码登录")
        self.setFixedSize(380, 460)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)

        self.stop_flag = None
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QLabel#dialogTitle {
                font-size: 20px;
                font-weight: 600;
                color: #1D1D1F;
            }
            QLabel#qrHolder {
                background-color: #F5F5F7;
                border-radius: 12px;
                border: 1px solid #E5E5E5;
            }
            QLabel#statusText {
                font-size: 14px;
                color: #86868B;
            }
            QPushButton {
                background-color: #E8E8ED;
                color: #1D1D1F;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #DCDCE0;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        title = QLabel("微信扫码登录")
        title.setObjectName("dialogTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.qr_label = QLabel()
        self.qr_label.setObjectName("qrHolder")
        self.qr_label.setFixedSize(260, 260)
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setText("加载中...")
        layout.addWidget(self.qr_label, alignment=Qt.AlignCenter)

        self.status_label = QLabel("正在获取二维码...")
        self.status_label.setObjectName("statusText")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.refresh_btn = QPushButton("刷新二维码")
        self.refresh_btn.clicked.connect(self.on_refresh)
        btn_layout.addWidget(self.refresh_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.on_cancel)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def set_qr_image(self, image_bytes: bytes):
        pixmap = QPixmap()
        pixmap.loadFromData(image_bytes)
        scaled = pixmap.scaled(240, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.qr_label.setPixmap(scaled)

    def set_status(self, text: str):
        self.status_label.setText(text)

    def on_refresh(self):
        if self.stop_flag is not None:
            self.stop_flag[0] = True
        self.status_label.setText("正在刷新...")
        self.qr_label.clear()
        self.qr_label.setText("加载中...")
        if self.parent():
            self.parent().start_qr_login()

    def on_cancel(self):
        if self.stop_flag is not None:
            self.stop_flag[0] = True
        self.reject()
