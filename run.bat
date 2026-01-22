@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo 正在检查并安装依赖...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\pip install -r requirements.txt

cls
echo 启动抢号助手...
.venv\Scripts\python.exe main.py
pause
