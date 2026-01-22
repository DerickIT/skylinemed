# 🏥 医院自动挂号助手 (Enterprise Edition)

基于 Python + Flet (Flutter) 打造的现代化 Windows 抢号软件。专为高并发、低延迟、抗风控场景设计。

![Screenshot](docs/screenshot.png)

## ✨ 核心特性

- **🚀 毫秒级并发**: 基于 asyncio + httpx 异步架构，支持单机 50+ QPS。
- **🛡️ 强力抗风控**: 集成 `curl_cffi` 模拟 TLS 指纹，绕过 WAF 检测。
- **💎 现代化 UI**: **采用 Flet (Flutter) 引擎**，极致精美，支持 MD3 风格，动态交互丝滑。
- **🤖 候补捡漏**: 30秒低频监控 + 发现退号 0.3秒 高频秒杀。
- **📱 多通道通知**: 抢到号后通过微信、钉钉强提醒，不错过支付时间。
- **🔄 企业级功能**: 支持代理 IP 池轮换、SQLite 历史记录、OTA 自动更新。

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
python main_gui.py
```

## 📦 自动构建

本项目支持 GitHub Actions 自动构建 Windows 可执行文件。

1. 提交代码并打标签 (Tag):
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
2. 等待构建完成后，在 GitHub Releases 页面下载 `91160Grabber-Win64.zip`。

## 📂 目录结构

```
root/
├── core/               # 核心业务逻辑 (GUI无关)
│   ├── tls_client.py   # TLS指纹通信
│   ├── async_grab.py   # 异步抢号引擎
│   ├── task_manager.py # 多任务管理
│   └── ...
├── gui/                # Fluent UI 界面代码
│   ├── main_window.py  # 主窗口
│   └── ...
├── legacy_cli/         # 旧版命令行工具 (已归档)
├── main_gui.py         # 程序入口
└── build.spec          # PyInstaller 打包配置
```

## ⚠️ 免责声明

本软件仅供技术研究和学习使用，请勿用于非法用途或商业获利。使用本软件产生的任何后果由用户自行承担。
