# 🏥 91160 智慧分诊助手（PySide6 GUI）

基于 Python + PySide6 的 Windows GUI 抢号工具，支持微信扫码登录与自动抢号流程。

## ✨ 核心特性

- 微信扫码登录（curl_cffi 指纹方式）
- 城市/医院/科室/医生联动查询
- 号源查询与自动提交
- GUI 实时日志与状态提示

## 🛠️ 快速开始

### 运行环境

- Windows 10/11
- Python 3.9+

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动软件

```bash
python main.py
```

## 📦 自动构建

本项目支持 GitHub Actions 自动构建 Windows 可执行文件：

```bash
pyinstaller build.spec
```

## 📂 目录结构

```
root/
├── core/                   # 核心业务逻辑
│   ├── client.py           # 同步请求与业务接口
│   ├── qr_login.py         # 微信扫码登录
│   └── grab.py             # 抢号逻辑
├── config/                 # 配置
│   ├── cities.json         # 城市列表
│   ├── user_state.json     # UI 状态
│   └── cookies.json        # 登录 Cookie
├── gui/                    # GUI 模块
│   ├── assets/             # UI 资源
│   │   └── style.qss       # Qt 样式
│   ├── windows/            # 窗口
│   ├── components/         # 组件
│   └── utils/              # 工具
├── main.py                 # 程序入口
├── build.spec              # PyInstaller 打包配置
└── requirements.txt        # 运行依赖
```

## ⚠️ 免责声明

本软件仅供技术研究和学习使用，请勿用于非法用途或商业获利。使用本软件产生的任何后果由用户自行承担。
