"""
duong_dan_chung.py
Thu muc dung chung cua Guzz va GoogleAITranscribe.

Hai app goi cung mot API key Google (moi app deu doc api_key.txt cua app kia khi
minh chua co), nen han muc Google tinh CHUNG: model bi 429 o app nay thi app kia
cung phai tranh. Nhat ky hai ben lai cung mot dinh dang. Vi vay ca hai dung chung:

    %LOCALAPPDATA%\\GoogleAI\\
        su_dung.json        luot dung + khoa han muc, CA HAI app doc/ghi (co khoa file)
        su_dung.json.khoa   file khoa lien tien trinh, khong co noi dung
        logs\\guzz.log       nhat ky Guzz
        logs\\google_ai_transcribe.log

Bien moi truong GOOGLEAI_DIR_CHUNG ghi de thu muc tren (de chay thu, hay ban
portable muon giu moi thu canh app).

Nhung thu rieng cua tung app (config.txt, prompt, tmp, state.json, giao_dien.json)
van o cho cu.

File nay giong het o ca hai app: sua ben nay thi chep sang ben kia.
"""

from __future__ import annotations

import os
import shutil

TEN_CHUNG = "GoogleAI"
TEN_FILE_SU_DUNG = "su_dung.json"

APP_DIR = os.path.dirname(os.path.abspath(__file__))


def _goc_chung() -> str:
    tu_dat = (os.environ.get("GOOGLEAI_DIR_CHUNG") or "").strip()
    if tu_dat:
        return os.path.abspath(os.path.expandvars(os.path.expanduser(tu_dat)))
    goc = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(goc, TEN_CHUNG)


DIR_CHUNG = _goc_chung()
DIR_LOG = os.path.join(DIR_CHUNG, "logs")
FILE_SU_DUNG = os.path.join(DIR_CHUNG, TEN_FILE_SU_DUNG)


def tuyet_doi_chung(duong_dan: str) -> str:
    """Duong dan tuong doi (vd "logs\\guzz.log") tinh tu DIR_CHUNG; bien moi truong duoc mo rong."""
    duong_dan = os.path.expandvars(os.path.expanduser((duong_dan or "").strip()))
    if os.path.isabs(duong_dan):
        return duong_dan
    return os.path.join(DIR_CHUNG, duong_dan)


def duong_dan_nhat_ky(file_log: str) -> str:
    """Noi ghi nhat ky theo [HE_THONG] file_log: duong dan tuong doi tinh tu thu muc dung chung."""
    return tuyet_doi_chung(file_log or os.path.join("logs", "app.log"))


# --------------------------------------------------------------------------
#  CHUYEN DU LIEU CU (mot lan, khong bat nguoi dung lam gi)
# --------------------------------------------------------------------------

def cac_thu_muc_cu() -> list[str]:
    """Nhung noi hai app tung ghi su_dung.json va logs\\ truoc khi gop."""
    ho_so = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    kq: list[str] = []
    for d in (APP_DIR,                                  # GoogleAITranscribe: canh ma nguon
              os.path.join(APP_DIR, "data"),            # Guzz ban portable
              os.path.join(ho_so, "Guzz"),              # Guzz ban da cai
              os.path.join(ho_so, "GoogleAITranscribe")):
        d = os.path.abspath(d)
        if os.path.isdir(d) and os.path.normcase(d) != os.path.normcase(DIR_CHUNG) and d not in kq:
            kq.append(d)
    return kq


def cac_file_su_dung_cu() -> list[str]:
    """su_dung.json con sot lai o cho cu, cho han_muc.gop_file_cu() gop vao file chung."""
    return [p for p in (os.path.join(d, TEN_FILE_SU_DUNG) for d in cac_thu_muc_cu()) if os.path.isfile(p)]


def chuyen_nhat_ky_cu() -> list[str]:
    """
    Chuyen file nhat ky cu (<noi cu>\\logs\\*.log*) sang <chung>\\logs, mot lan.
    File dang bi mo (app kia dang chay) hay trung ten thi bo qua, khong lam hong gi.
    """
    da_chuyen = []
    for thu_muc in cac_thu_muc_cu():
        cu = os.path.join(thu_muc, "logs")
        if not os.path.isdir(cu):
            continue
        for ten in sorted(os.listdir(cu)):
            nguon = os.path.join(cu, ten)
            dich = os.path.join(DIR_LOG, ten)
            if ".log" not in ten or not os.path.isfile(nguon) or os.path.exists(dich):
                continue
            try:
                os.makedirs(DIR_LOG, exist_ok=True)
                shutil.move(nguon, dich)
                da_chuyen.append(dich)
            except OSError:
                pass        # file dang mo, hay khong co quyen: cu de nguyen cho cu
        try:
            os.rmdir(cu)    # don thu muc rong
        except OSError:
            pass
    return da_chuyen
