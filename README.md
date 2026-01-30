# 🌌 SkylineMed (天际医航)

> **Next-Gen Hospital Appointment Assistant | Powered by Rust & Tauri**

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg?style=flat-square)](https://github.com/DerickIT/skylinemed)
[![License](https://img.shields.io/badge/license-MIT-green.svg?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D7.svg?style=flat-square)](https://github.com/DerickIT/skylinemed)

**SkylineMed** (天际医航) 是一款从 QuickDoctor 全面深度进化而来的高端医院挂号助手。通过将核心引擎从 Go 迁移至 **Rust**，并结合 **Tauri 2.0** 的现代化桌面架构，我们实现了极致的运行性能与极小的系统资源占用。

![App Screenshot Placeholder](https://via.placeholder.com/800x450.png?text=SkylineMed+Apple+Style+UI+Preview)

---

## 🎨 奢华设计：Apple Style Luxury UI

SkylineMed 不仅仅是一个工具，更是一种科技美学的体现。我们摒弃了传统工具软件的粗糙感，采用 **Apple-style** 极简设计语言：

-   **Glassmorphism (毛玻璃特效)**: 全局深度拟态毛玻璃，呈现晶莹剔透的层次感。
-   **Zinc & Blue Palette**: 精心调优的金属锌色与天际蓝配色方案，沉稳而不失动感。
-   **Micro-Animations**: 丝滑的浮动与脉冲动画，让交互感如丝般顺滑。
-   **Responsive Layout**: 完美的网格布局，在不同分辨率下皆能保持优雅。

---

## ⚡ 技术核心：Engineered for Performance

### 🏗️ 架构演进 (Go ➔ Rust)
从传统的 Wails 架构全面转向 **Tauri 2.0 + Rust + Vue 3**。
-   **极致轻量**: 二进制体积大幅缩减，启动速度提升 200%。
-   **内存安全**: 彻底消除并发竞争与非法访问风险。
-   **Async Core**: 基于 `Tokio` 的异步驱动模型，毫秒级响应海量网络请求。

### 🛡️ WAF 深度规避
针对现代 Web 应用防火墙 (WAF)，SkylineMed 实现了全套浏览器指纹模拟方案：
-   **TLS 指纹模拟**: 深度模拟 Chrome/Edge 的 TLS 握手特征。
-   **Dynamic Header**: 实时构造符合浏览器逻辑的 `Sec-Fetch-*`, `Origin`, `Referer` 策略。
-   **Smart Proxy**: 支持云端高匿名代理链路，波峰时期自动加速提交。

---

## 🚀 极速起航

### 环境准备
-   **Rust**: [rustup.rs](https://rustup.rs/) (Stable 1.70+)
-   **Node.js**: 20.x + **pnpm**
-   **WebView2**: Windows 10/11 默认已搭载

### 开发模式
```powershell
# 克隆仓库
git clone git@github.com:DerickIT/skylinemed.git
cd skylinemed

# 启动开发服务器
./build.ps1 dev
```

### 生产打包
```powershell
# 构建高度集成的安装程序
./build.ps1 build
```

---

## 📂 项目结构

```text
skylinemed/
├── src-tauri/          # 💎 Rust 核心引擎
│   └── src/
│       ├── core/       # API 客户端, 抢号逻辑, WAF 策略
│       └── commands.rs # 前后端通讯网关
├── frontend/           # 🎨 Vue 3 & Glassmorphism UI
│   └── src/
│       ├── components/ # 奢华组件库
│       └── composables/# 响应式状态流
└── config/             # ⚙️ 动态配置文件
```

---

## 🤝 参与贡献

如果你对本项目感兴趣，或者有更好的 UI/技术建议，欢迎提交 PR。让我们一起打造最优雅的效率工具。

---

## ⚠️ 免责声明

本软件仅供技术研究与学习使用，所有数据与接口均来源于公开信息。开发者不承担任何由使用本软件产生的法律责任或经济损失。请在法律法规允许的范围内合理使用。

---

**SkylineMed - 由天际智联科技 (Skyline Smart Link Tech) 精研打造。**
