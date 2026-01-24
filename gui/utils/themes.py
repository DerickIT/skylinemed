# -*- coding: utf-8 -*-
from .paths import get_gui_asset_path


def load_stylesheet() -> str:
    path = get_gui_asset_path("style.qss")
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
