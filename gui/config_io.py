"""
config_io.py
Doc/ghi config.txt theo tung dong van ban, giu nguyen moi comment va bo cuc
hien co (configparser ghi lai se lam mat het comment).

Lay tu GoogleAITranscribe (ban goc C:\\LecturerCleaner\\gui\\config_io.py, da sua hai cho):
  - ghi chu cuoi dong chi bat dau khi '#' / ';' dung SAU khoang trang, giong
    het cach configparser doc (inline_comment_prefixes). Ban goc cat o '#' dau
    tien, nen "tu_vung = C#, F#" bi doc thanh "C" va ghi lai thanh rac;
  - bo dau xuong dong truoc khi so khop: voi dong gia tri rong ("ngon_ngu ="),
    nhom "\\s*=\\s*" nuot luon dau xuong dong va ghi lai thanh hai dong vo.
"""

from __future__ import annotations

import os
import re

_SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
_KEY_RE = re.compile(r"^(\s*)([^#;=\s][^=]*?)(\s*=\s*)(.*?)\s*$")
_GHI_CHU_CUOI_DONG = re.compile(r"\s[#;]")


def doc_dong(duong_dan: str) -> list[str]:
    with open(duong_dan, "r", encoding="utf-8") as f:
        return f.readlines()


def ghi_dong(duong_dan: str, dong: list[str]):
    tmp = duong_dan + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.writelines(dong)
    os.replace(tmp, duong_dan)


def _khop_key(line: str):
    return _KEY_RE.match(line.rstrip("\r\n"))


def _tach_ghi_chu(phan_sau: str) -> tuple[str, str]:
    """'abc  # ghi chu' -> ('abc', '# ghi chu')."""
    m = _GHI_CHU_CUOI_DONG.search(phan_sau)
    if not m:
        return phan_sau, ""
    return phan_sau[:m.start()].rstrip(), phan_sau[m.start() + 1:]


def _vi_tri_section(dong: list[str], section: str) -> tuple[int, int]:
    """Tra ve (dong_bat_dau_noi_dung, dong_ket_thuc) cua mot section, khong ke dong [SECTION]."""
    bat_dau = None
    for i, line in enumerate(dong):
        m = _SECTION_RE.match(line)
        if m:
            if bat_dau is not None:
                return bat_dau, i
            if m.group(1).strip() == section:
                bat_dau = i + 1
    if bat_dau is None:
        raise KeyError(f"Khong thay section [{section}] trong config.txt")
    return bat_dau, len(dong)


def _dong_moi(m: re.Match, gia_tri) -> str:
    _, ghi_chu = _tach_ghi_chu(m.group(4))
    # "ngon_ngu =" (gia tri rong) khong co khoang trang sau dau "=".
    moi = f"{m.group(1)}{m.group(2)}{m.group(3).rstrip()} {gia_tri}".rstrip()
    if ghi_chu:
        moi += f"  {ghi_chu}"
    return moi + "\n"


def lay_gia_tri(section: str, key: str, duong_dan: str) -> str | None:
    dong = doc_dong(duong_dan)
    dau, cuoi = _vi_tri_section(dong, section)
    for line in dong[dau:cuoi]:
        m = _khop_key(line)
        if m and m.group(2).strip() == key:
            return _tach_ghi_chu(m.group(4))[0]
    return None


def dat_gia_tri(section: str, key: str, gia_tri, duong_dan: str):
    """Sua gia tri mot key trong section, giu nguyen comment cuoi dong (neu co)."""
    dat_nhieu_gia_tri({(section, key): gia_tri}, duong_dan)


def dat_nhieu_gia_tri(cap_gia_tri: dict[tuple[str, str], object], duong_dan: str):
    """
    cap_gia_tri: {(section, key): gia_tri}. Ghi mot lan cho tat ca thay doi.
    Key chua co trong section (config.txt cu) thi them vao cuoi section; section
    chua co thi them vao cuoi file.
    """
    dong = doc_dong(duong_dan)
    con_lai = dict(cap_gia_tri)

    section_hien_tai = None
    for i, line in enumerate(dong):
        m = _SECTION_RE.match(line)
        if m:
            section_hien_tai = m.group(1).strip()
            continue
        m = _khop_key(line)
        if not m:
            continue
        cap = (section_hien_tai, m.group(2).strip())
        if cap in con_lai:
            dong[i] = _dong_moi(m, con_lai.pop(cap))

    for (section, key), gia_tri in con_lai.items():
        try:
            dau, cuoi = _vi_tri_section(dong, section)
        except KeyError:
            if dong and not dong[-1].endswith("\n"):
                dong[-1] += "\n"
            dong += ["\n", f"[{section}]\n"]
            dau = cuoi = len(dong)
        # Chen truoc cac dong trong o cuoi section, giu khoang cach giua cac section.
        vi_tri = cuoi
        while vi_tri > dau and not dong[vi_tri - 1].strip():
            vi_tri -= 1
        dong.insert(vi_tri, f"{key} = {gia_tri}\n")

    ghi_dong(duong_dan, dong)


def xoa_key(section: str, cac_key, duong_dan: str):
    """Bo cac dong key trong section (vd bo khai bao han muc cua mot model). Key khong co thi bo qua."""
    cac_key = set(cac_key)
    if not cac_key:
        return
    dong = doc_dong(duong_dan)
    try:
        dau, cuoi = _vi_tri_section(dong, section)
    except KeyError:
        return
    giu = [line for line in dong[dau:cuoi] if not ((m := _khop_key(line)) and m.group(2).strip() in cac_key)]
    ghi_dong(duong_dan, dong[:dau] + giu + dong[cuoi:])
