# -*- coding: utf-8 -*-
import os
import sys
import subprocess


def ensure_venv():
    """检测并尝试切换到虚拟环境"""
    try:
        import PySide6  # noqa: F401
        import requests  # noqa: F401
        import curl_cffi  # noqa: F401
        import bs4  # noqa: F401
        return
    except ImportError:
        pass

    print("当前Python环境缺失依赖，尝试查找 .venv 虚拟环境...")

    venv_python = os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "python.exe")

    if os.path.exists(venv_python):
        if sys.executable.lower() == venv_python.lower():
            print("错误：已经在虚拟环境中但仍无法导入依赖，请尝试重新安装: pip install -r requirements.txt")
            input("按回车键退出...")
            sys.exit(1)

        print(f"发现虚拟环境，正在切换... \nExecutable: {venv_python}")

        cmd = [venv_python, __file__] + sys.argv[1:]
        subprocess.run(cmd)
        sys.exit(0)
    else:
        print("未找到 .venv 虚拟环境目录！请先运行 pip install -r requirements.txt")
        input("按回车键退出...")
        sys.exit(1)


def main():
    ensure_venv()

    try:
        from gui import run_app
        run_app()
    except Exception:
        import traceback
        print("启动 PySide6 GUI 失败:")
        traceback.print_exc()
        input("\n程序异常退出，按回车键关闭...")


if __name__ == "__main__":
    main()
