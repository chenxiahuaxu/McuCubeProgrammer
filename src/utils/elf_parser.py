"""ELF 符号解析 — 提取全局变量符号表。"""

from __future__ import annotations

from elftools.elf.elffile import ELFFile


def parse_elf_symbols(file_path: str) -> list[dict]:
    """解析 ELF 文件，返回全局变量符号列表。

    优先读取 .symtab，若不存在则回退到 .dynsym。
    只返回有地址的全局/弱链接对象符号。
    """
    symbols: list[dict] = []
    with open(file_path, "rb") as f:
        elf = ELFFile(f)

        for section_name in (".symtab", ".dynsym"):
            try:
                symtab = elf.get_section_by_name(section_name)
            except Exception:  # pylint: disable=broad-exception-caught  # OK: parse fallback
                continue
            if symtab is None:
                continue

            for sym in symtab.iter_symbols():
                st_info = sym.entry.st_info
                st_type = st_info.type
                st_bind = st_info.bind
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
                })
            break  # 只取第一个存在的符号表

    return sorted(symbols, key=lambda s: s["addr"])
