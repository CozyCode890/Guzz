"""
paths.py
Dua thu muc code (APP_DIR) va gui/ vao sys.path roi xuat lai cac duong dan cua
duong_dan.py. Python embeddable (runtime\\python) doc file ._pth nen KHONG tu them
thu muc cua script vao sys.path, vi vay main.py import file nay dau tien.
"""

import os
import sys

GUI_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.dirname(GUI_DIR), GUI_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from duong_dan import (  # noqa: E402,F401
    APP_DIR, CONFIG_MAU, CONFIG_PATH, DATA_DIR, DIR_CHUNG, ICON_PATH, SCRIPT_CAI_DAT, TEN_APP,
    dam_bao_du_lieu, duong_dan_nhat_ky, tuyet_doi,
)

PHIEN_BAN = "1.1.1"
FILE_TRANG_THAI_GIAO_DIEN = os.path.join(DATA_DIR, "giao_dien.json")
