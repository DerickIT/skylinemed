# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None
hiddenimports = ['curl_cffi', 'PySide6', 'bs4', 'fake_useragent']
datas = [
    ('config/cities.json', 'config'),
    ('gui/assets/style.qss', 'gui/assets'),
]
binaries = []

try:
    tmp_ret = collect_all('curl_cffi')
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]
except:
    pass

a = Analysis(['main.py'], pathex=[], binaries=binaries, datas=datas, hiddenimports=hiddenimports)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='91160Grabber', console=False)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, name='91160Grabber')
