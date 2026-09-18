"""
su_kien.py
Tin hieu dung chung giua cac trang. Trang nao ghi config.txt thi phat
cau_hinh_doi(ten_trang); cac trang khac nap lai phan hien thi cua minh.
"""

from __future__ import annotations

import json
import os

from PySide6.QtCore import QObject, Signal

from paths import FILE_TRANG_THAI_GIAO_DIEN


class _SuKien(QObject):
    cau_hinh_doi = Signal(str)      # ten trang vua ghi (de chinh no bo qua)
    co_nhat_ky_doi = Signal(int)    # co chu moi cua khung nhat ky
    han_muc_doi = Signal()          # model bi khoa / mo khoa, so lieu su dung doi (xem han_muc.py)


su_kien = _SuKien()


def doc_trang_thai() -> dict:
    """Nhung thu nho cua giao dien (kich thuoc cua so, thu muc chon file lan cuoi), khong nam trong config.txt."""
    try:
        with open(FILE_TRANG_THAI_GIAO_DIEN, "r", encoding="utf-8") as f:
            du_lieu = json.load(f)
        return du_lieu if isinstance(du_lieu, dict) else {}
    except (OSError, ValueError):
        return {}


def ghi_trang_thai(**truong):
    du_lieu = doc_trang_thai()
    du_lieu.update(truong)
    try:
        os.makedirs(os.path.dirname(FILE_TRANG_THAI_GIAO_DIEN), exist_ok=True)
        tmp = FILE_TRANG_THAI_GIAO_DIEN + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(du_lieu, f, ensure_ascii=False, indent=1)
        os.replace(tmp, FILE_TRANG_THAI_GIAO_DIEN)
    except OSError:
        pass
