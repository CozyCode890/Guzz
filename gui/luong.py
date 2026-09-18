"""
luong.py
Cac QThread cua app. Viec nang (xu ly am thanh, goi Google, pyannote) chay o day
de cua so khong bi dung hinh; logic that nam trong chuyen_doi.py / nhan_dien.py.
"""

from __future__ import annotations

import ctypes
import os
import sys
import threading

from PySide6.QtCore import QThread, Signal

import am_thanh_io
import cau_hinh as chh
import chuyen_doi as cd
import google_ai as ga
import han_muc
import nhan_dien
from paths import CONFIG_PATH

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


def _chong_ngu(bat: bool):
    """Giu may thuc trong luc chuyen (chi luong goi ham nay). Man hinh van tat theo cai dat Windows."""
    if sys.platform != "win32":
        return
    try:
        co = _ES_CONTINUOUS | (_ES_SYSTEM_REQUIRED if bat else 0)
        ctypes.windll.kernel32.SetThreadExecutionState(co)
    except Exception:
        pass


class LuongChuyenDoi(QThread):
    """
    Chuyen lan luot cac file trong hang doi. Hang doi la danh sach (ma_dong, duong_dan)
    dung chung voi giao dien (co khoa): trong luc dang chay van them / bo file duoc.
    """

    bat_dau_file = Signal(int)                  # ma dong
    tien_do = Signal(int, str, float, dict)     # ma dong, giai doan, ty le ca file, tham so
    xong_file = Signal(int, object)             # ma dong, KetQuaFile
    loi_file = Signal(int, str)                 # ma dong, thong bao
    huy_file = Signal(int)
    het = Signal(int, int, bool)                # so file xong, so file loi, bi dung giua chung

    def __init__(self, parent=None):
        super().__init__(parent)
        self._khoa = threading.Lock()
        self._hang_doi: list[tuple[int, str]] = []
        self._dung = False

    def them(self, ma: int, duong_dan: str):
        with self._khoa:
            self._hang_doi.append((ma, duong_dan))

    def bo(self, ma: int):
        with self._khoa:
            self._hang_doi = [(m, p) for m, p in self._hang_doi if m != ma]

    def _lay_tiep(self):
        with self._khoa:
            return self._hang_doi.pop(0) if self._hang_doi else None

    def yeu_cau_dung(self):
        self._dung = True

    def dang_dung(self) -> bool:
        return self._dung

    def run(self):
        so_xong = so_loi = 0
        ch = None
        may_khach = None
        da_chong_ngu = False
        try:
            while not self._dung:
                muc = self._lay_tiep()
                if muc is None:
                    break
                ma, duong_dan = muc
                try:
                    ch = chh.doc_cau_hinh(CONFIG_PATH)
                except Exception as e:
                    if ch is None:
                        self.loi_file.emit(ma, f"config.txt: {e}")
                        so_loi += 1
                        break
                    cd.log.error("Khong doc duoc config.txt (%s), dung cai dat cu.", e)
                if ch.chong_ngu and not da_chong_ngu:
                    _chong_ngu(True)
                    da_chong_ngu = True
                am_thanh_io.duong_dan_ffmpeg_tu_dat = ch.duong_dan_ffmpeg
                key = ga.lay_api_key()
                if may_khach is None or may_khach.api_key != key:
                    may_khach = ga.MayKhach(key, timeout=ch.timeout_giay,
                                            so_theo_doi=han_muc.so_theo_doi()) if key else None

                self.bat_dau_file.emit(ma)
                try:
                    kq = cd.chuyen_mot_file(
                        ch, duong_dan, may_khach, nen_dung=self.dang_dung,
                        bao=lambda gd, ty_le, ts, ma=ma: self.tien_do.emit(ma, gd, ty_le, ts))
                except ga.DaDung:
                    cd.log.info("Da dung giua chung %s. Bam Bat dau de lam tiep tu doan dang do.",
                                os.path.basename(duong_dan))
                    self.huy_file.emit(ma)
                    break
                except ga.LoiGoogleAI as e:
                    so_loi += 1
                    cd.log.error("Google AI bao loi khi chuyen %s: %s", os.path.basename(duong_dan), e)
                    self.loi_file.emit(ma, str(e))
                    if e.dung_hang_doi:
                        cd.log.error("Loi nay se lap lai o moi file: dung hang doi.")
                        break
                    if ch.khi_file_loi == "dung":
                        break
                except chh.LoiRangBuoc as e:
                    so_loi += 1
                    cd.log.error("%s", e)
                    self.loi_file.emit(ma, str(e))
                    break
                except nhan_dien.LoiNhanDien as e:
                    so_loi += 1
                    cd.log.error("%s", e)
                    self.loi_file.emit(ma, str(e))
                    if e.moi_truong or ch.khi_file_loi == "dung":
                        break
                except Exception as e:
                    so_loi += 1
                    cd.log.exception("Loi khi chuyen %s: %s", os.path.basename(duong_dan), e)
                    self.loi_file.emit(ma, f"{type(e).__name__}: {e}")
                    if ch.khi_file_loi == "dung":
                        break
                else:
                    so_xong += 1
                    self.xong_file.emit(ma, kq)
        finally:
            if da_chong_ngu:
                _chong_ngu(False)
            # File con lai trong hang doi (bi dung, hoac dung vi loi) tro ve trang thai cho.
            with self._khoa:
                con_lai, self._hang_doi = self._hang_doi, []
            for ma, _ in con_lai:
                self.huy_file.emit(ma)
            self.het.emit(so_xong, so_loi, self._dung)


class LuongDoThoiLuong(QThread):
    """Doc thoi luong cac file vua them (ffmpeg -i), khong chan giao dien."""

    co_ket_qua = Signal(int, float)

    def __init__(self, cac_file: list[tuple[int, str]], ffmpeg: str, parent=None):
        super().__init__(parent)
        self.cac_file = cac_file
        self.ffmpeg = ffmpeg

    def run(self):
        am_thanh_io.duong_dan_ffmpeg_tu_dat = self.ffmpeg
        for ma, p in self.cac_file:
            giay = am_thanh_io.do_thoi_luong(p)
            if giay is not None:
                self.co_ket_qua.emit(ma, giay)


class LuongKiemTraKetNoi(QThread):
    """Liet ke model bang key dang nhap tren man hinh (chua can bam Luu)."""
    xong = Signal(bool, str, list)

    def __init__(self, api_key: str, parent=None):
        super().__init__(parent)
        self.api_key = api_key

    def run(self):
        try:
            model = ga.MayKhach(self.api_key, timeout=30).liet_ke_model()
        except ga.LoiGoogleAI as e:
            self.xong.emit(False, str(e), [])
            return
        except Exception as e:
            self.xong.emit(False, f"{type(e).__name__}: {e}", [])
            return
        self.xong.emit(True, "", model)


class LuongKiemTraNguoiNoi(QThread):
    """Nap thu model pyannote bang cai dat dang hien tren man hinh. Lan dau co the phai tai model."""
    dong = Signal(str)
    xong = Signal(bool, dict, list)

    def __init__(self, ch, parent=None):
        super().__init__(parent)
        self.ch = ch

    def run(self):
        try:
            ok, thong_tin, thong_bao = nhan_dien.kiem_tra_moi_truong(self.ch, bao_dong=self.dong.emit)
        except Exception as e:
            ok, thong_tin, thong_bao = False, {}, [f"{type(e).__name__}: {e}"]
        self.xong.emit(ok, thong_tin, thong_bao)
