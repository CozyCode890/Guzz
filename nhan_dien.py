"""
nhan_dien.py
Goi tach_nguoi_noi_worker.py trong runtime rieng (runtime\\nguoi_noi, co torch +
pyannote) va quan ly token Hugging Face. Chi dung thu vien chuan.

Khac LecturerCleaner (subprocess.run, doc stderr sau khi xong):
  - Popen + luong doc stderr: tien do tung buoc cua pyannote hien len app ngay;
  - nut Dung terminate() duoc worker dang chay;
  - token Hugging Face nhap trong app (file rieng trong ho so nguoi dung) va
    truyen qua bien moi truong HF_TOKEN, khong can chay "hf auth login";
  - model tai ve HF_HOME cua app (runtime\\hf hoac <du lieu>\\hf), khong nam lan
    trong ~\\.cache cua may, de sau nay dong goi kem ban cai dat.
"""

from __future__ import annotations

import collections
import json
import logging
import os
import subprocess
import threading
import time

from duong_dan import WORKER_NGUOI_NOI
from google_ai import DaDung

log = logging.getLogger("Guzz")

CO_KHONG_CUA_SO = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TIEN_TO = "GUZZ|"
MA_LOI_MOI_TRUONG = 2

# Trong so thoi gian cua tung buoc pyannote, de ve mot thanh tien do lien mach.
_KHUNG_BUOC = {
    "segmentation": (0.0, 0.30),
    "speaker_counting": (0.30, 0.32),
    "embeddings": (0.32, 0.95),
    "discrete_diarization": (0.95, 1.0),
}


class LoiNhanDien(Exception):
    def __init__(self, thong_bao: str, moi_truong: bool = False):
        super().__init__(thong_bao)
        self.moi_truong = moi_truong


# --------------------------------------------------------------------------
#  TOKEN HUGGING FACE
# --------------------------------------------------------------------------

def duong_dan_file_token() -> str:
    goc = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(goc, "Guzz", "hf_token.txt")


def duong_dan_token_he_thong() -> str:
    """Noi "hf auth login" ghi token (LecturerCleaner dung cach nay)."""
    return os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "token")


def nguon_token() -> tuple[str | None, str | None]:
    """(token, noi tim thay) hoac (None, None)."""
    for p in (duong_dan_file_token(),):
        try:
            with open(p, "r", encoding="utf-8") as f:
                token = f.read().strip()
            if token:
                return token, p
        except OSError:
            pass
    token = (os.environ.get("HF_TOKEN") or "").strip()
    if token:
        return token, "HF_TOKEN"
    p = duong_dan_token_he_thong()
    try:
        with open(p, "r", encoding="utf-8") as f:
            token = f.read().strip()
        if token:
            return token, p
    except OSError:
        pass
    return None, None


def luu_token(token: str):
    p = duong_dan_file_token()
    token = (token or "").strip()
    if not token:
        try:
            os.remove(p)
        except OSError:
            pass
        return
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(token)
    os.replace(tmp, p)


# --------------------------------------------------------------------------
#  MOI TRUONG
# --------------------------------------------------------------------------

def moi_truong_worker(ch) -> dict:
    env = dict(os.environ)
    # Python embeddable bo qua PYTHONPATH, nhung Python thuong (tu chon trong app) thi khong.
    for bien in ("PYTHONHOME", "PYTHONPATH"):
        env.pop(bien, None)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["HF_HOME"] = ch.thu_muc_model_hf()
    env["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    token, _ = nguon_token()
    if token:
        env["HF_TOKEN"] = token
    if ch.nn_ngoai_tuyen:
        env["HF_HUB_OFFLINE"] = "1"
    else:
        env.pop("HF_HUB_OFFLINE", None)
    return env


def lenh_worker(ch, wav: str | None, json_ra: str | None, kiem_tra: bool = False) -> list[str]:
    lenh = [ch.duong_dan_python_nguoi_noi(), WORKER_NGUOI_NOI, "--model", ch.nn_model,
            "--thiet-bi", ch.nn_thiet_bi]
    if kiem_tra:
        return lenh + ["--kiem-tra"]
    lenh += [wav, "--ra", json_ra]
    if ch.nn_so_nguoi > 0:
        lenh += ["--so-nguoi", str(ch.nn_so_nguoi)]
    else:
        if ch.nn_it_nhat > 0:
            lenh += ["--min", str(ch.nn_it_nhat)]
        if ch.nn_nhieu_nhat > 0:
            lenh += ["--max", str(ch.nn_nhieu_nhat)]
    return lenh


def loi_thieu_python(ch) -> str | None:
    python = ch.duong_dan_python_nguoi_noi()
    if os.path.isfile(python):
        return None
    return (f"Khong thay Python cua runtime nhan dien nguoi noi: {python}. "
            "Bam \"Cai dat runtime\" o trang Nguoi noi (hoac chay cai_dat.ps1 -NguoiNoi), "
            "hoac chon duong dan python.exe khac.")


def model_da_tai(ch) -> bool:
    """Model pyannote da nam trong HF_HOME chua (khong chac day du, chi de hien trang thai)."""
    ten = "models--" + ch.nn_model.replace("/", "--")
    return os.path.isdir(os.path.join(ch.thu_muc_model_hf(), "hub", ten, "snapshots"))


# --------------------------------------------------------------------------
#  CHAY WORKER
# --------------------------------------------------------------------------

def _chay(lenh: list[str], env: dict, timeout: float, nen_dung=None, bao_dong=None,
          bao_tien_do=None) -> tuple[int, str, list[str]]:
    """
    Chay worker, doc stderr tung dong. Tra ve (ma thoat, stdout, cac dong thong bao).
    bao_dong(str): dong thong bao GUZZ|...; bao_tien_do(ty_le 0..1, buoc).
    """
    proc = subprocess.Popen(
        lenh, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
        text=True, encoding="utf-8", errors="replace", env=env, creationflags=CO_KHONG_CUA_SO,
    )
    thong_bao: list[str] = []
    duoi_stderr = collections.deque(maxlen=40)
    ket_qua_stdout = []

    def doc_stderr():
        for dong in proc.stderr:
            dong = dong.rstrip("\r\n")
            if not dong.startswith(TIEN_TO):
                if dong.strip():
                    duoi_stderr.append(dong)
                continue
            noi_dung = dong[len(TIEN_TO):]
            if noi_dung.startswith("TIEN_DO|"):
                try:
                    _, buoc, xong, tong = noi_dung.split("|")
                    dau, cuoi = _KHUNG_BUOC.get(buoc, (0.0, 1.0))
                    ty_le = dau + (cuoi - dau) * (int(xong) / max(1, int(tong)))
                except ValueError:
                    continue
                if bao_tien_do:
                    bao_tien_do(ty_le, buoc)
                continue
            thong_bao.append(noi_dung)
            if bao_dong:
                bao_dong(noi_dung)

    def doc_stdout():
        ket_qua_stdout.append(proc.stdout.read())

    luong = [threading.Thread(target=doc_stderr, daemon=True),
             threading.Thread(target=doc_stdout, daemon=True)]
    for t in luong:
        t.start()

    het_gio = time.monotonic() + timeout
    try:
        while proc.poll() is None:
            if nen_dung is not None and nen_dung():
                proc.terminate()
                try:
                    proc.wait(10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                raise DaDung()
            if time.monotonic() > het_gio:
                proc.kill()
                proc.wait(10)
                raise LoiNhanDien(f"Nhan dien nguoi noi chay qua {timeout / 60:.0f} phut ma chua xong.")
            time.sleep(0.3)
    finally:
        for t in luong:
            t.join(5)

    if proc.returncode != 0 and not thong_bao:
        thong_bao = list(duoi_stderr)
    return proc.returncode, "".join(ket_qua_stdout), thong_bao


def chay_nhan_dien(ch, wav: str, json_ra: str, nen_dung=None, bao_tien_do=None) -> None:
    """Chay pyannote tren wav, ghi json_ra. Nem LoiNhanDien / DaDung."""
    loi = loi_thieu_python(ch)
    if loi:
        raise LoiNhanDien(loi, moi_truong=True)
    if not ch.nn_ngoai_tuyen and not nguon_token()[0] and not model_da_tai(ch):
        raise LoiNhanDien("Chua co token Hugging Face de tai model pyannote. Nhap token o trang "
                          "Nguoi noi.", moi_truong=True)

    lenh = lenh_worker(ch, wav, json_ra)
    log.debug("Chay worker: %s", " ".join(f'"{x}"' if " " in x else x for x in lenh))
    luc_dau = time.monotonic()
    ma, _, thong_bao = _chay(lenh, moi_truong_worker(ch), ch.nn_timeout_giay, nen_dung,
                             bao_dong=lambda d: log.info("   %s", d), bao_tien_do=bao_tien_do)
    if ma != 0:
        chi_tiet = " | ".join(thong_bao[-4:]) or f"ma thoat {ma}"
        raise LoiNhanDien(f"Nhan dien nguoi noi that bai: {chi_tiet}", moi_truong=(ma == MA_LOI_MOI_TRUONG))
    if not os.path.isfile(json_ra):
        raise LoiNhanDien("Worker bao xong nhung khong ghi ra file ket qua.")
    log.info("Nhan dien nguoi noi xong sau %.0f giay.", time.monotonic() - luc_dau)


def kiem_tra_moi_truong(ch, timeout: float = 900, bao_dong=None) -> tuple[bool, dict, list[str]]:
    """Nap thu model (lan dau co the phai tai ve). Tra ve (san sang, thong tin, cac dong thong bao)."""
    loi = loi_thieu_python(ch)
    if loi:
        return False, {}, [loi]
    try:
        ma, stdout, thong_bao = _chay(lenh_worker(ch, None, None, kiem_tra=True),
                                      moi_truong_worker(ch), timeout, bao_dong=bao_dong)
    except (OSError, LoiNhanDien) as e:
        return False, {}, [str(e)]
    thong_tin = {}
    for dong in stdout.splitlines():
        try:
            thong_tin = json.loads(dong)
        except ValueError:
            continue
    return ma == 0 and bool(thong_tin.get("ok")), thong_tin, thong_bao
