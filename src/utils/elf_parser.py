"""ELF 符号解析 — 提取全局变量符号表。"""

from __future__ import annotations

from elftools.elf.elffile import ELFFile


def parse_elf_symbols(file_path: str) -> list[dict]:
    """解析 ELF 文件，返回全局变量符号列表。

    Args:
        file_path: .elf 或 .axf 文件路径。

    Returns:
        符号列表，每项包含 name / addr / size / type。
        只返回有地址的全局对象（非函数符号）。
    """
    symbols: list[dict] = []
    with open(file_path, "rb") as f:
        elf = ELFFile(f)
        symtab = elf.get_section_by_name(".symtab")
        if symtab is None:
            return symbols

        for sym in symtab.iter_symbols():
            st_info = sym.entry.st_info
            st_type = st_info.type
            st_bind = st_info.bind
            # 只取全局/外部链接的 OBJECT 类型（变量），NOTYPE 也可能是未初始化的全局变量
            if st_type not in ("STT_OBJECT", "STT_NOTYPE"):
                continue
            if st_bind not in ("STB_GLOBAL", "STB_WEAK"):
                continue
            addr = sym.entry.st_value
            size = sym.entry.st_size
            if addr == 0 and size == 0:
                continue
            symbols.append({
                "name": sym.name,
                "addr": addr,
                "size": size,
                "type": "object",
            })

    return sorted(symbols, key=lambda s: s["addr"])
