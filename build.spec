# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_all
block_cipher = None
hiddenimports = ['httpx', 'curl_cffi', 'asyncio', 'sqlite3', 'threading', 'json', 'playwright', 'PyQt6']
datas = []
binaries = []
try:
    tmp_ret = collect_all('curl_cffi')
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]
except: pass
a = Analysis(['main_gui.py'], pathex=[], binaries=binaries, datas=datas + [('notify_config.json', '.'), ('gui', 'gui'), ('core', 'core')], hiddenimports=hiddenimports)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='91160Grabber', console=False)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, name='91160Grabber')
