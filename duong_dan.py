"""
duong_dan.py
Moi duong dan cua Guzz tinh tu day, de ban chay tu thu muc code va ban cai dat
(installer) dung chung mot bo code.

    APP_DIR  : noi chua code va runtime (Program Files khi da cai dat)
    DATA_DIR : noi ghi config.txt, prompt, thu muc tam, model Hugging Face
    DIR_CHUNG: thu muc dung chung voi GoogleAITranscribe (nhat ky + su_dung.json),
               xem duong_dan_chung.py

Ban cai dat nam trong Program Files thi khong ghi duoc vao APP_DIR, nen du lieu
mac dinh nam trong %LOCALAPPDATA%\\Guzz. Co file "portable" nam canh code (thu
muc dang phat trien, hoac ban giai nen chay khong can cai) thi du lieu nam ngay
trong APP_DIR\\data. Bien moi truong GUZZ_DATA_DIR ghi de ca hai (de chay thu).

Runtime cuc bo (cai_dat.ps1 tao ra), khong dung Python / ffmpeg cua he thong:
    runtime\\python\\      Python embeddable + thu vien cua app
    runtime\\nguoi_noi\\   Python embeddable + torch + pyannote.audio
    runtime\\ffmpeg\\      ffmpeg.exe
    runtime\\hf\\          (tuy chon) model Hugging Face dong goi san
"""

from __future__ import annotations

import os
import shutil

from duong_dan_chung import (  # noqa: F401  (xuat lai cho gui/paths.py)
    DIR_CHUNG, DIR_LOG, FILE_SU_DUNG, chuyen_nhat_ky_cu, duong_dan_nhat_ky,
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
TEN_APP = "Guzz"


def _thu_muc_du_lieu() -> str:
    tu_dat = (os.environ.get("GUZZ_DATA_DIR") or "").strip()
    if tu_dat:
        return os.path.abspath(os.path.expandvars(tu_dat))
    if os.path.exists(os.path.join(APP_DIR, "portable")):
        return os.path.join(APP_DIR, "data")
    goc = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(goc, TEN_APP)


DATA_DIR = _thu_muc_du_lieu()
CONFIG_PATH = os.path.join(DATA_DIR, "config.txt")

# Ban mau di kem code; lan dau chay (hoac bam "Khoi phuc mac dinh") thi chep sang DATA_DIR.
CONFIG_MAU = os.path.join(APP_DIR, "config.mac_dinh.txt")
CAC_FILE_MAU = ("prompt.txt", "prompt_nguoi_noi.txt")

RUNTIME_DIR = os.path.join(APP_DIR, "runtime")
PYTHON_NGUOI_NOI = os.path.join(RUNTIME_DIR, "nguoi_noi", "python.exe")
FFMPEG_CUC_BO = os.path.join(RUNTIME_DIR, "ffmpeg", "ffmpeg.exe")
HF_DONG_GOI = os.path.join(RUNTIME_DIR, "hf")
WORKER_NGUOI_NOI = os.path.join(APP_DIR, "tach_nguoi_noi_worker.py")
SCRIPT_CAI_DAT = os.path.join(APP_DIR, "cai_dat.ps1")
ICON_PATH = os.path.join(APP_DIR, "gui", "assets", "icon.ico")


def tuyet_doi(duong_dan: str, goc: str = DATA_DIR) -> str:
    """Duong dan tuong doi (vd "tmp") tinh tu DATA_DIR; bien moi truong duoc mo rong.
    Rieng file_log tinh tu thu muc dung chung, xem duong_dan_nhat_ky()."""
    duong_dan = os.path.expandvars(os.path.expanduser((duong_dan or "").strip()))
    if os.path.isabs(duong_dan):
        return duong_dan
    return os.path.join(goc, duong_dan)


def thu_muc_hf_mac_dinh() -> str:
    """Model dong goi san trong runtime\\hf (ban cai dat) thi dung luon, khong thi tai ve DATA_DIR\\hf."""
    if os.path.isdir(os.path.join(HF_DONG_GOI, "hub")):
        return HF_DONG_GOI
    return os.path.join(DATA_DIR, "hf")


def dam_bao_du_lieu() -> list[str]:
    """
    Tao DATA_DIR va chep cac file mau con thieu (khong ghi de file da co).
    Tra ve danh sach file vua tao, de GUI bao cho nguoi dung.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    da_tao = []
    for nguon, dich in [(CONFIG_MAU, CONFIG_PATH)] + [
        (os.path.join(APP_DIR, ten), os.path.join(DATA_DIR, ten)) for ten in CAC_FILE_MAU
    ]:
        if not os.path.exists(dich) and os.path.exists(nguon):
            shutil.copyfile(nguon, dich)
            da_tao.append(dich)
    return da_tao
