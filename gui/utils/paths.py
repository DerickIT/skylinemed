# -*- coding: utf-8 -*-
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_config_path(filename: str) -> Path:
    return get_project_root() / "config" / filename


def get_gui_asset_path(filename: str) -> Path:
    return get_project_root() / "gui" / "assets" / filename
