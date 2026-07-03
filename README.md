# MCU Cube Programmer

> 一个 `pip install`，任意 Cortex-M 芯片，三种桌面系统 — 开源跨平台 MCU 烧录 GUI

<p align="center">
  <a href="https://github.com/chenxiahuaxu/McuCubeProgrammer/stargazers"><img src="https://img.shields.io/github/stars/chenxiahuaxu/McuCubeProgrammer?style=flat-square&color=yellow" alt="Stars"></a>
  <a href="https://github.com/chenxiahuaxu/McuCubeProgrammer/network/members"><img src="https://img.shields.io/github/forks/chenxiahuaxu/McuCubeProgrammer?style=flat-square" alt="Forks"></a>
  <a href="https://github.com/chenxiahuaxu/McuCubeProgrammer/issues"><img src="https://img.shields.io/github/issues/chenxiahuaxu/McuCubeProgrammer?style=flat-square" alt="Issues"></a>
  <a href="https://github.com/chenxiahuaxu/McuCubeProgrammer/pulse"><img src="https://img.shields.io/github/last-commit/chenxiahuaxu/McuCubeProgrammer?style=flat-square" alt="Last Commit"></a>
  <br>
  <a href="https://github.com/chenxiahuaxu/McuCubeProgrammer/releases"><img src="https://img.shields.io/github/downloads/chenxiahuaxu/McuCubeProgrammer/total?style=flat-square&label=downloads" alt="Downloads"></a>
  <a href="https://github.com/chenxiahuaxu/McuCubeProgrammer/issues?q=is%3Aissue+is%3Aclosed"><img src="https://img.shields.io/github/issues-closed/chenxiahuaxu/McuCubeProgrammer?style=flat-square&label=issues%20closed" alt="Issues Closed"></a>
  <a href="https://github.com/chenxiahuaxu/McuCubeProgrammer/pulls?q=is%3Apr+is%3Aclosed"><img src="https://img.shields.io/github/issues-pr-closed/chenxiahuaxu/McuCubeProgrammer?style=flat-square&label=prs%20closed" alt="PRs Closed"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/chenxiahuaxu/McuCubeProgrammer?style=flat-square&color=blue" alt="License"></a>
  <br>
  <img src="https://img.shields.io/badge/python-3.9%2B-blue?style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/tests-77%20passed-brightgreen?style=flat-square" alt="Tests">
  <img src="https://img.shields.io/badge/platform-Win%20%7C%20Mac%20%7C%20Linux-lightgrey?style=flat-square" alt="Platform">
  <img src="https://img.shields.io/github/repo-size/chenxiahuaxu/McuCubeProgrammer?style=flat-square" alt="Repo Size">
</p>

> **当前版本：v0.1.0**

---

## 什么时候需要它？

- **固件验证** — 手上有 `.hex`/`.bin` 文件，想快速烧进去看效果，不想装 1GB 的 STM32CubeProgrammer
- **多厂商切换** — 项目同时用 STM32 和 GD32，需要一个工具同时支持两种芯片
- **创客/教育** — 不想配 PlatformIO 项目，想开了就能用，换个芯片也不用换工具

---

## 竞品对比

| | MCU Cube Programmer | STM32CubeProgrammer | OpenOCD | pyOCD CLI | Flash Magic |
|---|---|---|---|---|---|
| **GUI** | 现代 Flet/Flutter | 传统 Qt | 无 | 无 | 传统 Win32 |
| **许可证** | Apache 2.0 (开源) | Freeware | GPLv2 | Apache 2.0 | 免费/付费 |
| **平台** | Win/Mac/Linux | Win/Mac/Linux | Win/Mac/Linux | Win/Mac/Linux | Windows 独占 |
| **芯片支持** | 任意 Cortex-M | STM32 独占 | ARM/RISC-V/MIPS | 任意 Cortex-M | NXP 独占 |
| **探针** | ST-Link/J-Link/DAPLink | ST-Link/J-Link | 50+ 种 | ST-Link/J-Link/DAPLink | NXP 桥接器 |
| **安装大小** | ~300 KB | ~1 GB | ~50 MB | ~10 MB | ~30 MB |
| **调试** | SWO 输出 | 寄存器/SWV | 完整 GDB | 完整 GDB | 无 |
| **上手难度** | 低 | 中 | 高 | 中 | 低 |

> **核心差异：** MCU Cube Programmer 是唯一的同时满足「现代 GUI + 开源 + 多厂商 + 跨平台」的 MCU 烧录工具。

---

## 项目数据

| 指标 | 数值 | 说明 |
|---|---|---|
| ⭐ Stars | [![Stars](https://img.shields.io/github/stars/chenxiahuaxu/McuCubeProgrammer?style=flat-square)](https://github.com/chenxiahuaxu/McuCubeProgrammer/stargazers) | GitHub 星标数（实时） |
| 🔀 Forks | [![Forks](https://img.shields.io/github/forks/chenxiahuaxu/McuCubeProgrammer?style=flat-square)](https://github.com/chenxiahuaxu/McuCubeProgrammer/network) | 社区 fork 数 |
| 📥 Release 下载 | [![Downloads](https://img.shields.io/github/downloads/chenxiahuaxu/McuCubeProgrammer/total?style=flat-square&label=)](https://github.com/chenxiahuaxu/McuCubeProgrammer/releases) | Release 附件总下载次数 |
| ✅ Issues 关闭 | [![Issues Closed](https://img.shields.io/github/issues-closed/chenxiahuaxu/McuCubeProgrammer?style=flat-square&label=)](https://github.com/chenxiahuaxu/McuCubeProgrammer/issues?q=is%3Aissue+is%3Aclosed) | 已关闭 issue 数 |
| 🔁 PRs 关闭 | [![PRs Closed](https://img.shields.io/github/issues-pr-closed/chenxiahuaxu/McuCubeProgrammer?style=flat-square&label=)](https://github.com/chenxiahuaxu/McuCubeProgrammer/pulls?q=is%3Apr+is%3Aclosed) | 已合并/关闭 PR 数 |
| 📦 安装体积 | **~300 KB** | 源码下载（不含 pyOCD） |
| 📦 全量安装 | **~15 MB** | 含 pyOCD + pyusb 等依赖 |
| 📊 pip 安装 | `pip install mcu-cube-programmer` | PyPI 发布后生效，当前仅供源码安装 |
| 🔌 探针支持 | **3 类** | ST-Link / CMSIS-DAP(含 DAPLink) / J-Link |
| 🧠 芯片支持 | **600+ 款** | 内置目标 + CMSIS-Pack 扩展可达全部 Cortex-M |
| 📄 格式支持 | **4 种** | `.bin` / `.hex` / `.elf` / `.axf` |
| 🧪 测试覆盖 | **77 项** | pytest 全通过（backend / logic / utils） |
| 📝 源代码 | **~2,400 行** | 纯 Python，不含测试和文档 |
| 🧵 架构分层 | **4 层** | UI → Logic → Backend → Utils |
| 🪟 平台 | **3 桌面 + Web** | Windows / macOS / Linux + 浏览器 |
| 🐍 Python | **3.9+** | 无 C 扩展，纯 pip 安装 |
| 📜 许可证 | **Apache 2.0** | 完全开源，商用友好 |

<!--
  注：Stars/Forks/Issues 等 badge 由 shields.io 从 GitHub API 实时拉取，
  无需手动更新。Commit Activity 为近一个月平均。
-->

---

## 特性

- **跨平台** — Windows / macOS / Linux 桌面应用 + Web 模式（浏览器访问）
- **多探针** — ST-Link (v2/v3)、CMSIS-DAP / DAPLink、J-Link
- **多芯片** — STM32 全系列、GD32、NXP、Nordic、Raspberry Pi 等 600+ 款
- **SWO 串行调试输出** — ITM/SWO 实时日志捕获
- **CMSIS-Pack 扩展** — 安装官方 Pack 支持更多芯片（如 GD32）
- **精密仪器主题** — PCB 绿 + 铜箔走线配色，深色终端风格
- **配置持久化** — 自动记住上次的探针/芯片/固件选择

> 💡 演示截图录屏尚未收录。如需查看界面布局，见下方的 ASCII 界面示意图。

---

## 界面

```
┌───────────────────────────────────────────────────────────┐
│  [Flash]  [探针]  [SWO]  [日志]  [设置]                    │
├───────────────────────────────────────────────────────────┤
│  探针  [ST-Link/V2 ▼]  [刷新]                              │
│  厂商  [ST ▼]  芯片  [输入芯片名搜索... ▼]  [安装 Pack]      │
│  固件  [选择固件]  path/to/firmware.hex                     │
│        [全片擦除]  [开始烧录]  [取消]                        │
│        ██████████████░░░░░░░░  65%                          │
├───────────────────────────────────────────────────────────┤
│  [12:34:56] INFO  固件: 13,312 字节, 地址 0x08000000        │
│  [12:34:56] INFO  Flash: 1024 KB, 扇区 16 KB               │
│  [12:34:56] INFO  擦除扇区 0-0 (1个)                        │
│  [12:34:58] DONE  烧录完成: 扇区 0-0 (1.8s)                │
└───────────────────────────────────────────────────────────┘
```

---

## 安装

### 环境要求

- Python 3.10+

### 安装步骤

```bash
git clone <repo-url>
cd mcu-cube-programmer
pip install -r requirements.txt
```

### 硬件驱动

| 平台 | 说明 |
|---|---|
| **Windows** | 用 Zadig 给 DAPLink/ST-Link 安装 WinUSB 驱动 |
| **Linux** | 安装 udev rules：`wget https://github.com/pyocd/pyOCD/raw/main/udev/50-pyocd.rules -O /etc/udev/rules.d/50-pyocd.rules` |
| **macOS** | `brew install libusb` |
| **J-Link** | 安装 [SEGGER J-Link 驱动](https://www.segger.com/downloads/jlink/) |

---

## 使用

### 桌面模式

```bash
python src/main.py
```

### Web 模式

```bash
python src/main.py --web
# 浏览器访问 http://localhost:8550
```

### 其他参数

```bash
python src/main.py --web -p 9000   # Web 模式指定端口
```

---

## 工作流程

1. **选择探针** — 启动后自动扫描，点击刷新可重新扫描
2. **选择芯片** — 先选厂家（ST/GD/NXP…），再输入芯片名搜索
3. **选择固件** — 支持 `.bin` / `.hex` / `.elf` / `.axf`
4. **开始烧录** — 扇区擦除 + 烧录 + 验证 + 复位
5. **查看 SWO** — 在 SWO 选项卡中打开串行调试输出

### 日志示例

```
════════════════════════════════════════
 MCU Cube Programmer v0.0.1 已启动
 平台: windows | pyOCD: 可用
 检测到 1 个调试探针
 已选择探针: STM32 STLink
 内置目标: 643 个
 已选择芯片: stm32f407zgtx
 已选择固件: firmware.hex
 ════════════════════════════════════════
 固件: 13,312 字节 (13.0 KB), 地址 0x08000000-0x08003400
 Flash: 1024 KB (Internal Flash), 扇区 16 KB
 擦除扇区 0-0 (1个, 各16KB)
 烧录完成: 扇区 0-0
 验证通过，芯片已复位 (1.8s)
```

---

## 项目结构

```
src/
├── main.py                   # 应用入口
├── app.py                    # App 主类（集成+生命周期）
├── backend/
│   ├── interface.py          # BackendABC 抽象接口
│   ├── pyocd_backend.py      # pyOCD 后端实现
│   └── error_codes.py        # 统一错误码
├── logic/
│   ├── probe_manager.py      # 探针扫描/选择
│   ├── target_manager.py     # 芯片列表/Pack 管理
│   └── flash_controller.py   # 烧录流程编排
├── ui/
│   ├── theme.py              # PCB精密仪器配色
│   ├── state.py              # AppState 状态机
│   ├── components/           # 可复用 UI 组件
│   │   ├── probe_selector.py
│   │   ├── target_selector.py
│   │   ├── file_picker.py
│   │   ├── flash_panel.py
│   │   └── log_view.py
│   └── tabs/                 # 标签页
│       ├── flash_tab.py
│       ├── probe_tab.py
│       ├── swo_tab.py
│       ├── log_tab.py
│       └── settings_tab.py
└── utils/
    ├── logger.py             # 全局日志单例（线程安全）
    └── config.py             # 配置持久化

tests/
├── conftest.py               # pytest 共享 fixtures
├── test_pyocd_backend.py     # 后端测试（26 项）
├── test_flash_controller.py  # 烧录流程测试（13 项）
├── test_probe_manager.py     # 探针管理测试（8 项）
├── test_target_manager.py    # 芯片管理测试（14 项）
└── test_logger.py            # 日志单例测试（11 项）
```

---

## 技术栈

| 层级 | 技术 | 许可 |
|---|---|---|
| UI 框架 | Flet (Flutter/Material 3) | Apache 2.0 |
| 后端引擎 | pyOCD 0.44+ | Apache 2.0 |
| 语言 | Python 3.9+ | — |
| 打包 | `flet build` | BSD-3 |
| 测试 | pytest + pytest-asyncio | MIT |

---

## 开发者

### 运行测试

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

当前测试覆盖：**77 项全部通过**，覆盖：
- `PyOCDBackend` — 连接、烧录、验证、断开 (26 项)
- `FlashController` — 完整流程、进度回调、取消操作 (13 项)
- `ProbeManager` — 扫描、选择、刷新 (8 项)
- `TargetManager` — 芯片列表、Pack 安装、搜索 (14 项)
- `Logger` — 线程安全、缓冲裁剪、回调 (11 项)
- `FlashTask` + `ProbeSelector` 等辅助类 (5 项)

### 设计文档

| Phase | 内容 |
|---|---|
| 0 | 项目骨架、窗口、主题 |
| 1 | 后端封装（ErrorCode + BackendABC + PyOCDBackend） |
| 2 | 逻辑层（ProbeManager + TargetManager + FlashController） |
| 3 | UI 组件（PCB精密仪器风格） |
| 4 | 集成与最终组装 |

---

## License

Apache 2.0
