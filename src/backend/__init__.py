"""后端层 — 调试探针抽象接口与 pyOCD 实现。

子模块:
    interface.py    — BackendABC 抽象基类，定义 list_probes/connect/erase/program/reset 接口
    pyocd_backend.py — 基于 pyOCD SDK 的具体实现
    error_codes.py  — ErrorCode 枚举，统一错误码与用户可读描述
"""
