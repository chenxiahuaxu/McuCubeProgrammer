"""逻辑层 — 探针管理、芯片目标管理、烧录流程控制。

子模块:
    probe_manager.py    — 探针扫描与选择逻辑，封装 ProbeInfo dataclass
    target_manager.py   — 芯片列表获取（内置 + CMSIS-Pack）、Pack 安装管理
    flash_controller.py — 烧录主流程编排：校验参数 → 调用后端 → 进度回调 → 错误处理
"""
