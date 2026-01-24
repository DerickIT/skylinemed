# -*- coding: utf-8 -*-
from PySide6.QtCore import Signal, QObject


class WorkerSignals(QObject):
    """后台线程与 UI 通信的信号"""
    log = Signal(str, str)  # message, color
    hospitals_loaded = Signal(list)
    deps_loaded = Signal(list)
    doctors_loaded = Signal(list)
    members_loaded = Signal(list)
    login_status = Signal(bool)
    qr_image = Signal(bytes)
    qr_status = Signal(str)
    qr_close = Signal()
    grab_finished = Signal(bool, str)
    update_button = Signal(str, str)  # text, object_name
