#!/usr/bin/env python3
"""
chuyen_doi.py
Chuyen MOT file audio (hoac video co tieng) thanh ban go chu. Luong xu ly lay tu
GoogleAITranscribe (bo phan theo doi thu muc, thoi khoa bieu va state.json: app
nay chi chuyen nhung file nguoi dung tu chon), them lop nhan dien nguoi noi.

    bai giang.m4a  (hoac bai giang.mp4)
        |-- (0) neu la video        : tmp\\bai giang_1a2b3c4d\\am_thanh_video.flac
        |-- (1) lam sach + cat doan : tmp\\bai giang_1a2b3c4d\\doan_001.flac ... (+ sach.flac)
        |-- (2) (neu can) pyannote  : nguoi_noi.<ma>.json   (luot noi ca buoi)
        |-- (3) go chu tung doan    : doan_001.<ma>.json    (chu + tu co moc)
        |-- (4) ghep, dat ten, noi  : <thu muc ra>\\bai giang.txt
        v
    xoa thu muc tam (neu bat)

Lam lai mot file vua loi giua chung: doan nao da co ket qua trong tmp thi khong
gui lai; tham so am thanh khong doi thi khong xu ly am thanh lai; ket qua
pyannote con thi khong chay lai. Ma bam trong ten file cache doi theo tham so,
nen doi cai dat roi chay lai khong bi dung nham ket qua cu.

Chay tay (PowerShell, bang Python cua runtime):
    .\\runtime\\python\\python.exe chuyen_doi.py "bai 1.m4a" "bai 2.mp4"
    .\\runtime\\python\\python.exe chuyen_doi.py bai.m4a --ra D:\\Transcripts
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import logging
import os
import shutil
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from logging.handlers import RotatingFileHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import am_thanh_io  # noqa: E402
import cau_hinh as chh  # noqa: E402
import google_ai  # noqa: E402
import han_muc  # noqa: E402
import nguoi_noi as nn  # noqa: E402
import nhan_dien  # noqa: E402
import video_io  # noqa: E402
from cau_hinh import (  # noqa: E402
    NN_GEMINI, NN_KET_HOP, NN_PYANNOTE, CauHinh, doc_cau_hinh, la_model_go_chu, thu_muc_tam_goc,
)
from duong_dan import (  # noqa: E402
    CONFIG_PATH, chuyen_nhat_ky_cu, dam_bao_du_lieu, duong_dan_nhat_ky,
)
from google_ai import DaDung, LoiGoogleAI  # noqa: E402
from xu_ly_am_thanh import BanDoThoiGian  # noqa: E402

log = logging.getLogger("Guzz")

GD_LAM_SACH = "lam_sach"
GD_NGUOI_NOI = "nguoi_noi"
GD_GO_CHU = "go_chu"
GD_NOI_LAI = "noi_lai"

FILE_DANH_SACH_DOAN = "danh_sach_doan.json"
FILE_SACH = "sach.flac"
FILE_GOC = "goc.flac"
FILE_AM_THANH_VIDEO = "am_thanh_video"   # + duoi theo [XU_LY_VIDEO] dinh_dang_tach

HUONG_DAN_MOC = ("- Begin every paragraph with its start time in square brackets, formatted mm:ss and "
                 "measured from the start of this audio clip (use the times in the speaker map), "
                 "for example \"[03:15] {ten}: ...\".")


@dataclass
class KetQuaFile:
    file_ra: str | None = None
    bo_qua: bool = False
    so_doan: int = 0
    so_ky_tu: int = 0
    thoi_luong_goc: float = 0.0
    phut_theo_nguoi: dict = field(default_factory=dict)
    canh_bao: list = field(default_factory=list)
    cac_model: dict = field(default_factory=dict)     # model -> so doan da go chu bang model do


# --------------------------------------------------------------------------
#  NHAT KY
# --------------------------------------------------------------------------

def cai_dat_log(ch: CauHinh):
    """
    Gan (hoac thay) handler ghi file theo [HE_THONG]. Chi go handler do chinh ham
    nay gan, nen handler cua GUI (QtLogHandler) van con sau khi doi cai dat.
    """
    chuyen_nhat_ky_cu()     # lan dau chay ban moi: don nhat ky cu vao thu muc chung
    duong_dan_log = duong_dan_nhat_ky(ch.file_log)
    os.makedirs(os.path.dirname(duong_dan_log), exist_ok=True)
    log.setLevel(getattr(logging, ch.muc_nhat_ky, logging.INFO))
    for h in [h for h in log.handlers if getattr(h, "_cua_guzz", False)]:
        log.removeHandler(h)
        h.close()

    dinh_dang = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    fh = RotatingFileHandler(duong_dan_log, maxBytes=ch.dung_luong_log_mb * 1024 * 1024,
                             backupCount=ch.so_file_log_cu, encoding="utf-8")
    fh.setFormatter(dinh_dang)
    fh._cua_guzz = True
    log.addHandler(fh)

    # Chay bang pythonw.exe (app GUI) thi sys.stdout la None, StreamHandler vo ich.
    if sys.stdout is not None:
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(dinh_dang)
        sh._cua_guzz = True
        log.addHandler(sh)


# --------------------------------------------------------------------------
#  TIEN ICH
# --------------------------------------------------------------------------

def van_tay(duong_dan: str) -> str:
    st = os.stat(duong_dan)
    return f"{os.path.normcase(os.path.abspath(duong_dan))}|{st.st_size}|{int(st.st_mtime)}"


def _ma(*phan) -> str:
    return hashlib.sha1(json.dumps(phan, ensure_ascii=False, sort_keys=True, default=str)
                        .encode("utf-8")).hexdigest()[:10]


def thu_muc_tam_cho(ch: CauHinh, duong_dan: str) -> str:
    """Moi file mot thu muc tam rieng; ma bam van tay de hai file trung ten khong dung nhau."""
    goc = os.path.splitext(os.path.basename(duong_dan))[0]
    return os.path.join(thu_muc_tam_goc(ch), f"{goc}_{_ma(van_tay(duong_dan))[:8]}")


def ma_am_thanh(ch: CauHinh, duong_dan: str, chu_ky_video=None) -> str:
    """chu_ky_video: cach lay tieng ra tu file video (None neu la file audio, de ma bam
    cua cac file audio cu khong doi)."""
    ma = _ma(van_tay(duong_dan), ch.khu_on, ch.tan_so_lay_mau, ch.target_dbfs, ch.cat_khoang_lang,
             ch.min_silence_len, ch.silence_thresh_offset, ch.keep_silence, ch.noise_sample_sec,
             ch.bandpass_low, ch.bandpass_high, ch.prop_decrease, ch.level_window_sec,
             ch.phut_moi_doan, ch.giay_tim_cho_cat, ch.giay_doan_cuoi_toi_thieu, ch.dinh_dang_doan)
    return ma if chu_ky_video is None else _ma(ma, chu_ky_video)


def ma_nguoi_noi(ch: CauHinh, ma_am: str) -> str:
    return _ma(ma_am, ch.nn_chay_tren, ch.nn_model, ch.nn_so_nguoi, ch.nn_it_nhat, ch.nn_nhieu_nhat)


def co_file_that(duong_dan: str) -> bool:
    return os.path.exists(duong_dan) and os.path.getsize(duong_dan) > 0


def ghi_van_ban(duong_dan: str, noi_dung: str, ma_hoa: str = "utf-8", xuong_dong: str = "lf"):
    os.makedirs(os.path.dirname(duong_dan), exist_ok=True)
    if xuong_dong == "crlf":
        noi_dung = noi_dung.replace("\r\n", "\n").replace("\n", "\r\n")
    tmp = duong_dan + ".tmp"
    with open(tmp, "w", encoding=ma_hoa, newline="") as f:
        f.write(noi_dung)
    os.replace(tmp, duong_dan)


def ten_khong_trung(duong_dan: str) -> str:
    if not os.path.exists(duong_dan):
        return duong_dan
    goc, duoi = os.path.splitext(duong_dan)
    i = 2
    while os.path.exists(f"{goc} ({i}){duoi}"):
        i += 1
    return f"{goc} ({i}){duoi}"


def hms(giay: float) -> str:
    giay = int(round(giay))
    return f"{giay // 3600}:{giay % 3600 // 60:02d}:{giay % 60:02d}"


class TienDo:
    """Doi tien do trong tung buoc (0..1) thanh tien do ca file, roi goi bao(giai_doan, ty_le, tham_so)."""

    def __init__(self, bao, co_pyannote: bool):
        self.bao = bao
        if co_pyannote:
            self.khung = {GD_LAM_SACH: (0.0, 0.15), GD_NGUOI_NOI: (0.15, 0.35),
                          GD_GO_CHU: (0.35, 0.98), GD_NOI_LAI: (0.98, 1.0)}
        else:
            self.khung = {GD_LAM_SACH: (0.0, 0.15), GD_GO_CHU: (0.15, 0.98), GD_NOI_LAI: (0.98, 1.0)}

    def __call__(self, giai_doan: str, ty_le: float = 0.0, **tham_so):
        if self.bao is None:
            return
        a, b = self.khung.get(giai_doan, (0.0, 1.0))
        self.bao(giai_doan, a + (b - a) * min(1.0, max(0.0, ty_le)), tham_so)


# --------------------------------------------------------------------------
#  (0) NGUON AM THANH (file audio, hoac tieng lay ra tu file video)
# --------------------------------------------------------------------------

class KhongCoTieng(RuntimeError):
    """File video khong co rung tieng nao de go chu."""


class NguonAudio:
    """
    Cho biet doc tieng cua mot file dau vao o dau.

      - file audio            : chinh no, khong can map rung nao.
      - video, tach truoc     : rut rung tieng da chon ra mot file trong thu muc
                                tam (chi rut mot lan; chay lai dung lai file cu).
      - video, khong tach     : doc thang tu video, ffmpeg map dung rung da chon.

    Rut tieng ra file tam la mac dinh: video bai giang thuong nang hang GB, doc
    thang thi moi buoc (lam sach, roi pyannote tren audio goc) lai giai ma lai ca
    luong hinh. Nhuoc diem la ton them cho trong thu muc tam.
    """

    def __init__(self, ch: CauHinh, duong_dan: str, thu_muc_tam: str):
        self.ch = ch
        self.duong_dan = duong_dan
        self.thu_muc_tam = thu_muc_tam
        self.la_video = ch.la_file_video(duong_dan)
        self.rung: int | None = None
        self._file_tach: str | None = None

        if not self.la_video:
            return
        cac_rung = video_io.cac_rung_am_thanh(duong_dan)
        if not cac_rung:
            raise KhongCoTieng(f"Video {os.path.basename(duong_dan)} khong co rung tieng nao.")
        self.rung = video_io.chon_rung(cac_rung, ch.video_rung_am_thanh)
        log.info("Video co %d rung tieng (%s), dung rung #%d.", len(cac_rung),
                 " | ".join(r.mo_ta() for r in cac_rung), self.rung)
        if ch.can_tach_am_thanh_video():
            self._file_tach = os.path.join(
                thu_muc_tam, f"{FILE_AM_THANH_VIDEO}.{ch.video_dinh_dang_tach}")

    def chu_ky(self):
        """Phan anh huong toi noi dung audio doc ra, de dua vao ma bam cache."""
        if not self.la_video:
            return None
        return (self.rung, self._file_tach is not None, self.ch.video_dinh_dang_tach)

    def lay(self) -> str:
        """Duong dan de doc tieng. Rut tieng khoi video o lan goi dau tien neu can."""
        if self._file_tach is None:
            return self.duong_dan
        if not co_file_that(self._file_tach):
            os.makedirs(self.thu_muc_tam, exist_ok=True)
            log.info("Dang tach rung tieng #%d khoi video ra %s...", self.rung,
                     self.ch.video_dinh_dang_tach)
            luc_dau = time.monotonic()
            video_io.tach_am_thanh(self.duong_dan, self._file_tach, self.rung)
            log.info("Tach tieng xong sau %.0f giay (%.1f MB).", time.monotonic() - luc_dau,
                     os.path.getsize(self._file_tach) / 2**20)
        # File tach ra chi con mot rung: khong map nua.
        return self._file_tach

    def rung_can_map(self) -> int | None:
        """Chi so rung phai truyen cho ffmpeg khi doc lay(); None neu file chi co mot rung."""
        return None if self._file_tach is not None else self.rung


# --------------------------------------------------------------------------
#  (1) LAM SACH + CAT DOAN
# --------------------------------------------------------------------------

def doc_danh_sach_doan(thu_muc_tam: str, ma: str) -> dict | None:
    """Danh sach doan da cat voi dung tham so, hoac None neu chua co / thieu file doan nao do."""
    try:
        with open(os.path.join(thu_muc_tam, FILE_DANH_SACH_DOAN), "r", encoding="utf-8") as f:
            du_lieu = json.load(f)
        doan = du_lieu["doan"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if du_lieu.get("ma") != ma or not doan:
        return None
    if any(not co_file_that(os.path.join(thu_muc_tam, d["file"])) for d in doan):
        return None
    return du_lieu


def chuan_bi_doan(ch: CauHinh, nguon: NguonAudio, thu_muc_tam: str, ma: str, can_sach: bool,
                  tien_do) -> tuple[list[dict], BanDoThoiGian]:
    da_co = doc_danh_sach_doan(thu_muc_tam, ma)
    if da_co and (not can_sach or co_file_that(os.path.join(thu_muc_tam, FILE_SACH))):
        log.info("Cac doan audio da co san (%d doan), bo qua buoc xu ly am thanh.", len(da_co["doan"]))
        return da_co["doan"], BanDoThoiGian(da_co["ban_do_thoi_gian"], da_co.get("thoi_luong_goc"))

    import cat_doan  # import muon cho khoi cham luc khoi dong
    import xu_ly_am_thanh

    os.makedirs(thu_muc_tam, exist_ok=True)
    try:
        os.remove(os.path.join(thu_muc_tam, FILE_DANH_SACH_DOAN))
    except OSError:
        pass

    def bao(m: str):
        log.info("   %s", m)
        if m.startswith("[") and "/6]" in m[:6]:
            tien_do(GD_LAM_SACH, (int(m[1]) - 1) / 6, buoc=int(m[1]))

    luc_dau = time.monotonic()
    y, sr, ban_do = xu_ly_am_thanh.lam_sach_theo_cau_hinh(
        ch, nguon.lay(), rung_am_thanh=nguon.rung_can_map(), progress_callback=bao)
    if len(y) == 0:
        raise RuntimeError("Sau khi lam sach khong con doan nao co tieng.")
    if can_sach:
        am_thanh_io.ghi_audio(y, sr, os.path.join(thu_muc_tam, FILE_SACH), "flac")

    diem = cat_doan.tim_diem_cat(y, sr, ch.phut_moi_doan, ch.giay_tim_cho_cat, ch.giay_doan_cuoi_toi_thieu)
    doan = cat_doan.ghi_cac_doan(y, sr, diem, thu_muc_tam, ch.dinh_dang_doan, lambda m: log.info("   %s", m))
    del y

    # Ghi danh sach SAU CUNG: co file nay nghia la moi doan da ghi xong.
    ghi_van_ban(os.path.join(thu_muc_tam, FILE_DANH_SACH_DOAN), json.dumps({
        "ma": ma,
        "nguon": nguon.duong_dan,
        "tan_so_lay_mau": sr,
        "thoi_luong_goc": round(ban_do.thoi_luong_goc, 3),
        "ban_do_thoi_gian": ban_do.sang_json(),
        "doan": doan,
    }, ensure_ascii=False, indent=1))
    tien_do(GD_LAM_SACH, 1.0)
    log.info("Xu ly am thanh va cat doan xong sau %.0f giay: %d doan.", time.monotonic() - luc_dau, len(doan))
    return doan, ban_do


# --------------------------------------------------------------------------
#  (2) NHAN DIEN NGUOI NOI (pyannote)
# --------------------------------------------------------------------------

def nhan_dien_nguoi_noi(ch: CauHinh, nguon: NguonAudio, thu_muc_tam: str, json_ra: str,
                        ban_do: BanDoThoiGian, tien_do, nen_dung) -> list[nn.LuotNoi]:
    """Luot noi ca buoi, moc tren audio DA LAM SACH."""
    if co_file_that(json_ra):
        log.info("Dung lai ket qua nhan dien nguoi noi da co.")
    else:
        if ch.nn_chay_tren == "goc":
            audio = os.path.join(thu_muc_tam, FILE_GOC)
            if not co_file_that(audio):
                log.info("Doi file goc sang 16 kHz mono cho pyannote...")
                am_thanh_io.chuyen_ma(nguon.lay(), audio, 16000, rung=nguon.rung_can_map())
        else:
            audio = os.path.join(thu_muc_tam, FILE_SACH)
        log.info("Nhan dien nguoi noi bang %s (thiet bi %s, audio %s)...", ch.nn_model, ch.nn_thiet_bi,
                 "goc" if ch.nn_chay_tren == "goc" else "da lam sach")
        tien_do(GD_NGUOI_NOI, 0.0)
        nhan_dien.chay_nhan_dien(ch, audio, json_ra, nen_dung,
                                 bao_tien_do=lambda ty_le, buoc: tien_do(GD_NGUOI_NOI, ty_le, buoc=buoc))
    tien_do(GD_NGUOI_NOI, 1.0)
    luot = nn.doc_luot_noi(json_ra)
    if ch.nn_chay_tren == "goc":
        luot = nn.doi_moc(luot, ban_do.sang_sach)
    return luot


# --------------------------------------------------------------------------
#  (3) GO CHU TUNG DOAN
# --------------------------------------------------------------------------

def so_theo_doi_cua(may_khach) -> han_muc.SoTheoDoi:
    """So theo doi cua may khach; khong co (chay tay, test) thi dung mot so tam trong bo nho."""
    so = getattr(may_khach, "so_theo_doi", None)
    if so is None:
        so = han_muc.SoTheoDoi(None)
        try:
            may_khach.so_theo_doi = so
        except AttributeError:
            pass
    return so


class BoGuiDoan:
    """
    Gui tung doan cho model dau tien con dung duoc trong ch.chuoi_model() (model chinh roi
    model du phong hop voi cach nhan dien):
      - het han muc (429): theo ngay thi khoa model toi luc Google tinh lai, theo phut thi
        khoa vai phut; roi doi model;
      - qua tai (5xx) sau ch.so_lan_thu_truoc_khi_doi lan: khoa ch.phut_khoa_khi_qua_tai phut, doi model;
      - bi bo loc cua Google chan (400 Input blocked): thu rieng doan do voi model khac, khong khoa;
      - model khong ton tai (404): khoa den khi mo tay, doi model.
    Moi model trong chuoi deu khoa thi cho model mo som nhat neu khong lau hon
    ch.cho_toi_da_khi_het_model_phut, khong thi bao loi dung hang doi.
    """

    def __init__(self, ch: CauHinh, may_khach, nen_dung=None):
        self.ch = ch
        self.kh = may_khach
        self.so = so_theo_doi_cua(may_khach)
        self.nen_dung = nen_dung
        self.chuoi = ch.chuoi_model()
        self.model_dang_dung = self.chuoi[0]

    # ---------------------------------------------------------------- chon model

    def _thu_tu(self) -> list[str]:
        if self.ch.quay_lai_model_chinh or self.model_dang_dung not in self.chuoi:
            return list(self.chuoi)
        i = self.chuoi.index(self.model_dang_dung)
        return self.chuoi[i:] + self.chuoi[:i]

    def _khoa_neu_cham_han_muc_ngay(self, model: str):
        if not self.ch.khoa_truoc_khi_cham_han_muc or self.so.bi_khoa(model):
            return
        rpd = self.so.gioi_han(self.ch, model).rpd
        da_gui = self.so.yeu_cau_hom_nay(model)
        if rpd and da_gui >= rpd:
            self.so.khoa(model, han_muc.luc_dat_lai_ngay(self.so.dong_ho()), han_muc.KHOA_CHAM_HAN_MUC,
                         f"Da gui {da_gui}/{rpd} yeu cau trong ngay.")

    def cac_model_dung_duoc(self, bo_qua=()) -> list[str]:
        kq = []
        for m in self._thu_tu():
            if m in bo_qua:
                continue
            self._khoa_neu_cham_han_muc_ngay(m)
            if not self.so.bi_khoa(m):
                kq.append(m)
        return kq

    def _chon_theo_thoi_gian_cho(self, ung_vien: list[str], so_giay: float) -> tuple[str, bool]:
        """
        Bat doi_khi_cho_qua_giay: model dau phai cho han muc phut qua lau ma model khac khong phai cho
        thi dung model khac. Tra ve (model, co phai vi cho han muc).
        """
        model = ung_vien[0]
        nguong = self.ch.doi_khi_cho_qua_giay
        ham = getattr(self.kh, "thoi_gian_cho_han_muc", None)
        if not self.ch.tu_doi_model or nguong <= 0 or len(ung_vien) < 2 or ham is None:
            return model, False
        cho = ham(self.ch, model, so_giay)
        if cho <= nguong:
            return model, False
        for m in ung_vien[1:]:
            if ham(self.ch, m, so_giay) <= 0:
                log.info("   %s phai cho %.0f giay han muc theo phut, gui doan nay cho %s.", model, cho, m)
                return m, True
        return model, False

    # ---------------------------------------------------------------- loi

    def _khoa_theo_loi(self, model: str, e: LoiGoogleAI):
        bay_gio = self.so.dong_ho()
        if e.loai == google_ai.LOI_HAN_MUC:
            if e.theo_ngay:
                self.so.khoa(model, han_muc.luc_dat_lai_ngay(bay_gio), han_muc.KHOA_HAN_MUC_NGAY, str(e))
            elif self.ch.tu_doi_model:
                if self.so.so_lan_khoa_phut_gan_day(model) >= 2:
                    log.warning("   %s bi 429 lap lai sau moi lan khoa, coi nhu da het han muc trong ngay.", model)
                    self.so.khoa(model, han_muc.luc_dat_lai_ngay(bay_gio), han_muc.KHOA_HAN_MUC_NGAY, str(e))
                else:
                    self.so.khoa(model, bay_gio + max(60.0, e.cho_giay + 2), han_muc.KHOA_HAN_MUC_PHUT, str(e))
        elif e.loai == google_ai.LOI_QUA_TAI and self.ch.tu_doi_model and self.ch.phut_khoa_khi_qua_tai > 0:
            self.so.khoa(model, bay_gio + self.ch.phut_khoa_khi_qua_tai * 60, han_muc.KHOA_QUA_TAI, str(e))
        elif e.loai == google_ai.LOI_MODEL:
            self.so.khoa(model, None, han_muc.KHOA_KHONG_TON_TAI, str(e))

    def _mo_ta_khoa(self, cac_model) -> str:
        phan = []
        for m in cac_model:
            khoa, den, ly_do, _ = self.so.trang_thai_khoa(m)
            if khoa:
                phan.append(f"{m} khoa {'toi ' + han_muc.gio_may(den) if den else 'den khi mo tay'} ({ly_do})")
        return "; ".join(phan)

    def _cho_model_mo_khoa(self, bo_qua: dict, loi_cuoi: LoiGoogleAI | None):
        con_lai = [m for m in self.chuoi if m not in bo_qua]
        if not con_lai:
            if all(e.loai == google_ai.LOI_BI_CHAN for e in bo_qua.values()):
                raise LoiGoogleAI(f"Doan nay bi bo loc cua Google chan o moi model da thu ({', '.join(bo_qua)}): "
                                  f"{loi_cuoi}", google_ai.LOI_BI_CHAN)
            raise LoiGoogleAI(f"Doan nay loi o moi model da thu ({', '.join(f'{m}: {e.loai}' for m, e in bo_qua.items())})"
                              f": {loi_cuoi}", loi_cuoi.loai if loi_cuoi else google_ai.LOI_KHAC)
        mo_ta = self._mo_ta_khoa(con_lai)
        cac_luc = [den for den in (self.so.trang_thai_khoa(m)[1] for m in con_lai) if den is not None]
        if not cac_luc:
            raise LoiGoogleAI(f"Khong con model nao dung duoc: {mo_ta}. Mo khoa o trang Han muc hoac them model "
                              "du phong.", loi_cuoi.loai if loi_cuoi else google_ai.LOI_MODEL, dung_hang_doi=True)
        den = min(cac_luc)
        cho = den - self.so.dong_ho()
        toi_da = self.ch.cho_toi_da_khi_het_model_phut * 60
        if cho > toi_da:
            raise LoiGoogleAI(
                f"Moi model dung duoc deu dang khoa: {mo_ta}. Phai cho {han_muc.dem_nguoc(cho)}, lau hon "
                f"{self.ch.cho_toi_da_khi_het_model_phut:g} phut cho phep nen dung hang doi. Them model du phong, "
                "doi cach nhan dien nguoi noi, hoac mo khoa o trang Han muc.",
                google_ai.LOI_HAN_MUC, dung_hang_doi=True)
        log.warning("Moi model dung duoc deu dang khoa (%s). Cho %s roi thu lai.", mo_ta, han_muc.dem_nguoc(cho))
        self.so.dat_dang_cho(None, "het_model", den, mo_ta)
        try:
            google_ai.ngu(max(1.0, cho + 1), self.nen_dung)
        finally:
            self.so.xoa_dang_cho()

    # ---------------------------------------------------------------- gui

    def gui(self, duong_dan: str, so_giay: float, tuy_chon_cho, bao_model=None,
            bo_qua_ban_dau: dict | None = None) -> tuple[dict, str]:
        """
        tuy_chon_cho(model) -> (prompt, tham so them cho go_chu_tho). bao_model(model) goi moi lan
        chon xong model. Tra ve (Interaction, model da go chu doan nay).
        bo_qua_ban_dau: model khong duoc dung cho doan nay (vd vua tra ve ban go chu rong).
        """
        # Model bo qua RIENG doan nay (bi bo loc chan, hoac loi ma khong khoa model): {model: loi}.
        bo_qua: dict[str, LoiGoogleAI] = dict(bo_qua_ban_dau or {})
        loi_cuoi = None
        while True:
            if self.nen_dung is not None and self.nen_dung():
                raise DaDung()
            ung_vien = self.cac_model_dung_duoc(bo_qua)
            if not ung_vien:
                self._cho_model_mo_khoa(bo_qua, loi_cuoi)
                continue
            model, vi_cho = self._chon_theo_thoi_gian_cho(ung_vien, so_giay)
            if model != self.model_dang_dung:
                # Ma ly do (trang Han muc dich ra chu): ly do khoa, bi_chan, qua_tai, cho_han_muc, uu_tien.
                if vi_cho:
                    ly_do = "cho_han_muc"
                elif self.model_dang_dung in bo_qua:
                    ly_do = {google_ai.LOI_BI_CHAN: "bi_chan", google_ai.LOI_HAN_MUC: han_muc.KHOA_HAN_MUC_PHUT,
                             google_ai.LOI_MODEL: han_muc.KHOA_KHONG_TON_TAI}.get(
                        bo_qua[self.model_dang_dung].loai, han_muc.KHOA_QUA_TAI)
                else:
                    ly_do = self.so.trang_thai_khoa(self.model_dang_dung)[2] or "uu_tien"
                log.warning("Doi model: %s -> %s (%s).", self.model_dang_dung, model, ly_do)
                self.so.ghi_doi_model(self.model_dang_dung, model, ly_do)
                self.model_dang_dung = model
            if bao_model is not None:
                bao_model(model)
            prompt, tuy_chon = tuy_chon_cho(model)
            if self.ch.tu_doi_model and len(ung_vien) > 1:
                tuy_chon = dict(tuy_chon, so_lan_thu=self.ch.so_lan_thu_truoc_khi_doi)
            try:
                tra_ve = self.kh.go_chu_tho(duong_dan, self.ch, prompt, nen_dung=self.nen_dung,
                                            so_giay_audio=so_giay, model=model, **tuy_chon)
            except LoiGoogleAI as e:
                self._khoa_theo_loi(model, e)
                loi_cuoi = e
                if e.loai not in google_ai.CAC_LOI_DOI_MODEL:
                    raise
                if self.so.bi_khoa(model):
                    continue  # da khoa: doi model, hoac cho / bao loi ro rang o vong sau
                if not self.ch.tu_doi_model:
                    raise
                # Khong khoa (bo loc chan, hoac tat khoa khi qua tai): chi bo model nay cho doan dang gui.
                bo_qua[model] = e
                if e.loai == google_ai.LOI_BI_CHAN:
                    log.warning("   Bo loc cua Google chan doan nay o %s, thu model khac.", model)
                continue
            self._khoa_neu_cham_han_muc_ngay(model)
            return tra_ve, model


def go_chu_cac_doan(ch: CauHinh, thu_muc_tam: str, doan: list[dict], may_khach, ma_am: str,
                    luot: list[nn.LuotNoi], bang: dict, tien_do, nen_dung) -> list[dict]:
    cach = ch.cach_nhan_dien()
    loi = chh.loi_rang_buoc(ch)
    if loi:
        raise chh.LoiRangBuoc(loi)
    bo_gui = BoGuiDoan(ch, may_khach, nen_dung)

    prompt_nguoi_noi = ch.doc_prompt_nguoi_noi() if cach == NN_PYANNOTE else None
    prompt_thuong = []

    def prompt_cho(model: str) -> str | None:
        """Tat nhan dien nguoi noi: model da nang (ke ca model du phong) doc prompt.txt."""
        if la_model_go_chu(model):
            return None
        if not prompt_thuong:
            prompt_thuong.append(ch.doc_prompt())
        return prompt_thuong[0]

    if cach in (NN_GEMINI, NN_KET_HOP):
        if ch.tu_vung:
            log.warning("Tu vung chuyen nganh bi bo qua: Google khong cho dung cung tach nguoi noi / "
                        "moc tung tu.")
        if ch.che_do_go_chu == "smart":
            log.info("Che do smart khong di cung tach nguoi noi / moc tung tu, dung verbatim.")

    # Khong co ten model: doan da xong bang model du phong van dung lai duoc khi chay tiep.
    ma_chung = _ma(ma_am, cach, prompt_nguoi_noi if cach == NN_PYANNOTE else prompt_cho(ch.model) if cach is None
                   else None, ch.ngon_ngu, ch.tu_vung, ch.che_do_go_chu,
                   ch.nn_cach_gui if cach == NN_PYANNOTE else None,
                   ch.nn_moc_thoi_gian if cach == NN_PYANNOTE else None)
    ket_qua = []
    tong = len(doan)
    for i, d in enumerate(doan, 1):
        goc = os.path.splitext(d["file"])[0]
        so_giay = d["ket_thuc_giay"] - d["bat_dau_giay"]
        p_nguoi_noi = None
        kem = {}
        ban_do_txt = None
        if cach == NN_PYANNOTE:
            luot_doan = nn.cat_theo_doan(luot, d["bat_dau_giay"], d["ket_thuc_giay"])
            ban_do_txt = nn.ban_do_van_ban(luot_doan, bang)
            ten = nn.ten_trong_doan(luot_doan, bang) or list(dict.fromkeys(bang.values())) or ["Speaker 1"]
            p_nguoi_noi = prompt_nguoi_noi.replace("{danh_sach_nguoi_noi}", ", ".join(ten))
            if ch.nn_moc_thoi_gian:
                p_nguoi_noi += "\n" + HUONG_DAN_MOC.replace("{ten}", ten[0])
            if ch.nn_cach_gui == "file":
                file_ban_do = os.path.join(thu_muc_tam, f"{goc}.nguoi_noi.txt")
                ghi_van_ban(file_ban_do, ban_do_txt)
                kem["file_kem"] = file_ban_do
            else:
                kem["van_ban_kem"] = ban_do_txt

        file_kq = os.path.join(thu_muc_tam, f"{goc}.{_ma(ma_chung, ban_do_txt)}.json")
        if co_file_that(file_kq):
            with open(file_kq, "r", encoding="utf-8") as f:
                ket_qua.append(json.load(f))
            tien_do(GD_GO_CHU, i / tong, doan=i, tong=tong)
            continue
        if nen_dung is not None and nen_dung():
            raise DaDung()

        def tuy_chon_cho(model: str, p_nguoi_noi=p_nguoi_noi, kem=kem):
            if cach == NN_PYANNOTE:
                return p_nguoi_noi, dict(kem)
            if cach == NN_GEMINI:
                return None, {"tach_nguoi_noi": True, "moc_tung_tu": True}
            if cach == NN_KET_HOP:
                return None, {"moc_tung_tu": True}
            return prompt_cho(model), {}

        da_bao = []

        def bao_model(model: str, i=i, d=d, da_bao=da_bao):
            if not da_bao:
                log.info("Doan %d/%d (%s - %s): gui len %s...", i, tong,
                         hms(d["bat_dau_giay"]), hms(d["ket_thuc_giay"]), model)
                da_bao.append(model)
            tien_do(GD_GO_CHU, (i - 1) / tong, doan=i, tong=tong, model=model)

        luc_dau = time.monotonic()
        file_doan = os.path.join(thu_muc_tam, d["file"])
        tra_ve, model = bo_gui.gui(file_doan, so_giay, tuy_chon_cho, bao_model)
        van_ban = google_ai.trich_van_ban(tra_ve).strip()
        # Doan im lang da bi cat tu truoc, nen ban go chu rong gan nhu chac chan la model tra ve hong
        # (Google van tinh token). Bo qua am tham = mat han may phut bai giang, nen thu lai model khac.
        if not van_ban and co_tieng_noi(ban_do_txt):
            # Con model khac thi bo qua model vua hong; chi con mot model thi thu lai chinh no
            # (bo qua het se thanh "moi model deu hong" va lam hong ca file).
            khac = [m for m in bo_gui.cac_model_dung_duoc() if m != model]
            log.warning("Doan %d/%d: %s tra ve ban go chu RONG trong khi doan nay co tieng noi. "
                        "Thu lai bang %s.", i, tong, model, khac[0] if khac else "chinh model do")
            da_bao.clear()
            try:
                tra_ve_2, model_2 = bo_gui.gui(
                    file_doan, so_giay, tuy_chon_cho, bao_model,
                    bo_qua_ban_dau=({model: LoiGoogleAI("Tra ve ban go chu rong", google_ai.LOI_BI_CHAN)}
                                    if khac else None))
            except LoiGoogleAI as e:
                # Thu lai that bai: giu ket qua rong va di tiep, dung lam hong ca file.
                log.warning("Doan %d/%d: thu lai cung khong duoc (%s). Doan nay se trong.", i, tong, e)
            else:
                van_ban_2 = google_ai.trich_van_ban(tra_ve_2).strip()
                if van_ban_2:
                    tra_ve, model, van_ban = tra_ve_2, model_2, van_ban_2
                else:
                    log.warning("Doan %d/%d: %s cung tra ve rong. Doan nay se trong.", i, tong, model_2)
        tu = google_ai.trich_tu(tra_ve) if cach in (NN_GEMINI, NN_KET_HOP) else []
        kq = {"van_ban": van_ban, "tu": tu, "model": model}
        # Khong nho ket qua rong cua doan co tieng noi: nho thi chay lai cung bo qua doan do vinh vien.
        if van_ban or not co_tieng_noi(ban_do_txt):
            ghi_van_ban(file_kq, json.dumps(kq, ensure_ascii=False))
        ket_qua.append(kq)

        so_token = getattr(may_khach, "so_token_lan_cuoi", 0)
        if van_ban:
            log.info("Doan %d/%d xong sau %.0f giay bang %s, %d ky tu%s%s.", i, tong, time.monotonic() - luc_dau,
                     model, len(van_ban), f", {len(tu)} tu co moc" if tu else "",
                     f", {so_token} token dau vao" if so_token else "")
            if cach in (NN_GEMINI, NN_KET_HOP) and not tu:
                log.warning("Doan %d/%d khong co moc thoi gian tung tu: doan nay se khong co ten "
                            "nguoi noi.", i, tong)
        else:
            log.warning("Doan %d/%d khong co chu nao (doan khong ai noi, hoac model khong nghe ra).", i, tong)
        tien_do(GD_GO_CHU, i / tong, doan=i, tong=tong, model=model)
    return ket_qua


def co_tieng_noi(ban_do_txt: str | None) -> bool:
    """
    Doan nay co ai noi khong? Cach pyannote: ban do co it nhat mot luot noi. Cach khac khong co ban do,
    nhung doan im lang da bi cat o buoc xu ly am thanh nen coi nhu co tieng noi.
    """
    if ban_do_txt is None:
        return True
    return any(" - " in dong for dong in ban_do_txt.splitlines())


def dem_model(ch: CauHinh, ket_qua: list[dict]) -> dict:
    """{model: so doan}. Ket qua cu (truoc khi co tu doi model) tinh cho model chinh."""
    dem = defaultdict(int)
    for kq in ket_qua:
        dem[kq.get("model") or ch.model] += 1
    return dict(dem)


# --------------------------------------------------------------------------
#  (4) GHEP
# --------------------------------------------------------------------------

def _doan_van_khong_ten(van_ban: str) -> list[nn.DoanVan]:
    return [nn.DoanVan(p.strip()) for p in van_ban.split("\n\n") if p.strip()]


def ghep_ban_go_chu(ch: CauHinh, doan: list[dict], ket_qua: list[dict], luot: list[nn.LuotNoi],
                    bang: dict, ban_do: BanDoThoiGian) -> tuple[str, dict]:
    """Tra ve (than ban go chu, so phut noi theo ten)."""
    cach = ch.cach_nhan_dien()
    tong = len(doan)
    phan: list[list] = [[] for _ in doan]
    phut = {}

    if cach is None:
        for i, kq in enumerate(ket_qua):
            if kq["van_ban"]:
                phan[i] = [kq["van_ban"]]

    elif cach == NN_PYANNOTE:
        cac_ten = list(dict.fromkeys(bang.values()))
        for i, (d, kq) in enumerate(zip(doan, ket_qua)):
            phan[i] = (nn.doc_doan_van_prompt(kq["van_ban"], cac_ten, d["bat_dau_giay"], ban_do.sang_goc)
                       or _doan_van_khong_ten(kq["van_ban"]))
        phut = nn.phut_theo_nguoi(luot, bang)

    elif cach == NN_GEMINI:
        # Nhan spk_1, spk_2... chi dung trong tung doan: dat ten rieng tung doan.
        thoi_gian = defaultdict(float)
        for i, (d, kq) in enumerate(zip(doan, ket_qua)):
            cau = nn.tu_sang_cau(kq["tu"], d["bat_dau_giay"])
            if not cau:
                phan[i] = _doan_van_khong_ten(kq["van_ban"])
                continue
            if any(c.nguoi_noi for c in cau):
                nn.doi_ten(cau, nn.bang_ten(cau, ch))
            for c in cau:
                thoi_gian[c.nguoi_noi] += c.ket_thuc - c.bat_dau
            gop = nn.gop_cau(cau, ch.nn_gop_doan_toi_da_giay, ch.nn_gop_khoang_lang_giay)
            phan[i] = nn.cau_sang_doan_van(gop, ban_do.sang_goc)
        phut = {k: round(v / 60, 1) for k, v in sorted(thoi_gian.items(), key=lambda kv: kv[1], reverse=True)
                if k}

    else:  # NN_KET_HOP
        cau = []
        for i, (d, kq) in enumerate(zip(doan, ket_qua)):
            cua_doan = nn.tu_sang_cau([{**t, "nguoi_noi": None} for t in kq["tu"]], d["bat_dau_giay"])
            if not cua_doan:
                phan[i] = _doan_van_khong_ten(kq["van_ban"])
            cau += cua_doan
        if cau:
            nn.gan_nguoi_noi(cau, luot)
            if ch.nn_lam_muot:
                so_doi = nn.lam_muot(cau, luot, ch.nn_kep_toi_da_giay, ch.nn_kep_nghi_giay,
                                     ch.nn_mat_do_cua_so_giay, ch.nn_mat_do_toi_thieu_giay,
                                     theo_nguoi_chinh=ch.nn_dat_ten_nguoi_chinh)
                log.info("Lam muot: doi nhan %d tu.", so_doi)
            bang = nn.bang_ten(cau, ch, chinh=nn.nguoi_noi_chinh(luot))
            phut = nn.phut_theo_nguoi(luot, bang)
            nn.doi_ten(cau, bang)
            bat_daus = [d["bat_dau_giay"] for d in doan]
            for c in nn.gop_cau(cau, ch.nn_gop_doan_toi_da_giay, ch.nn_gop_khoang_lang_giay):
                i = max(0, bisect.bisect_right(bat_daus, c.bat_dau) - 1)
                phan[i].extend(nn.cau_sang_doan_van([c], ban_do.sang_goc))

    khoi = []
    for i, ds in enumerate(phan, 1):
        if ch.danh_dau_doan:
            khoi.append(f"----- Đoạn {i}/{tong} -----")
        for x in ds:
            dong = x if isinstance(x, str) else nn.hien_thi_doan(
                x, ch.nn_mau_doan, ch.nn_moc_thoi_gian, ch.nn_danh_dau_xem_lai)
            if dong:
                khoi.append(dong)
    return "\n\n".join(khoi), phut


def phan_dau(ch: CauHinh, duong_dan: str, thoi_luong_goc: float, phut: dict,
             cac_model: dict | None = None) -> str:
    if cac_model and len(cac_model) > 1:
        ten_model = ", ".join(f"{m} ({so} đoạn)" for m, so in cac_model.items())
    else:
        ten_model = next(iter(cac_model)) if cac_model else ch.model
    dong = [f"Tệp {'video' if ch.la_file_video(duong_dan) else 'âm thanh'}: "
            f"{os.path.basename(duong_dan)}",
            f"Chuyển lúc: {datetime.now():%Y-%m-%d %H:%M} · Model: {ten_model} · "
            f"Thời lượng: {hms(thoi_luong_goc)}"]
    if phut:
        dong.append("Người nói: " + ", ".join(f"{ten} ({p:g} phút)" for ten, p in phut.items()))
    dong.append("-" * 60)
    return "\n".join(dong)


def ban_do_day_du(luot: list[nn.LuotNoi], bang: dict, ban_do: BanDoThoiGian) -> str:
    dong = [f"[{nn.hh_mm_ss(ban_do.sang_goc(l.bat_dau))} - {nn.hh_mm_ss(ban_do.sang_goc(l.ket_thuc))}] "
            f"{bang.get(l.nguoi_noi, l.nguoi_noi)}" for l in luot]
    return "\n".join(dong) + "\n"


# --------------------------------------------------------------------------
#  MOT FILE
# --------------------------------------------------------------------------

def tao_may_khach(ch: CauHinh):
    key = google_ai.lay_api_key()
    return google_ai.MayKhach(key, timeout=ch.timeout_giay, so_theo_doi=han_muc.so_theo_doi()) if key else None


def chuyen_mot_file(ch: CauHinh, duong_dan: str, may_khach, nen_dung=None, bao=None) -> KetQuaFile:
    """
    Chuyen mot file. bao(giai_doan, ty_le 0..1 ca file, tham_so dict) de GUI ve tien do.
    Nem LoiGoogleAI, nhan_dien.LoiNhanDien, DaDung, hoac loi khac.
    """
    am_thanh_io.duong_dan_ffmpeg_tu_dat = ch.duong_dan_ffmpeg
    if not os.path.isfile(duong_dan):
        raise FileNotFoundError(f"Khong thay file: {duong_dan}")

    tien_do = TienDo(bao, ch.can_pyannote())
    thu_muc_ra = ch.thu_muc_ket_qua(duong_dan)
    file_ra = os.path.join(thu_muc_ra, ch.ten_file_ra(duong_dan))
    cach = ch.cach_nhan_dien()

    log.info("-" * 70)
    log.info("File   : %s", duong_dan)
    log.info("Ket qua: %s", file_ra)
    chuoi = ch.chuoi_model()
    log.info("Model  : %s%s%s", ch.model, f" (du phong: {', '.join(chuoi[1:])})" if len(chuoi) > 1 else "",
             f" | nguoi noi: {cach}" if cach else "")

    if os.path.exists(file_ra) and ch.khi_trung_ten == "bo_qua":
        log.info("Da co ban go chu cung ten, bo qua file nay.")
        return KetQuaFile(file_ra, bo_qua=True)
    if may_khach is None:
        raise LoiGoogleAI("Chua co API key cua Google AI Studio. Nhap key o trang Google AI Studio.",
                          google_ai.LOI_CAU_HINH)
    # Bao som, truoc khi mat vai phut xu ly am thanh va chay pyannote.
    loi = chh.loi_rang_buoc(ch)
    if loi:
        raise chh.LoiRangBuoc(loi)

    thu_muc_tam = thu_muc_tam_cho(ch, duong_dan)
    try:
        nguon = NguonAudio(ch, duong_dan, thu_muc_tam)
    except KhongCoTieng as e:
        if not ch.video_bo_qua_khong_tieng:
            raise
        log.warning("%s Bo qua file nay.", e)
        return KetQuaFile(bo_qua=True)

    ma_am = ma_am_thanh(ch, duong_dan, nguon.chu_ky())
    json_nguoi_noi = os.path.join(thu_muc_tam, f"nguoi_noi.{ma_nguoi_noi(ch, ma_am)}.json")
    can_sach = ch.luu_audio_da_lam_sach or (
        ch.can_pyannote() and ch.nn_chay_tren == "da_lam_sach" and not co_file_that(json_nguoi_noi))

    # ---- (1) lam sach + cat doan ----
    tien_do(GD_LAM_SACH, 0.0)
    doan, ban_do = chuan_bi_doan(ch, nguon, thu_muc_tam, ma_am, can_sach, tien_do)
    if nen_dung is not None and nen_dung():
        raise DaDung()

    # ---- (2) pyannote ----
    luot, bang = [], {}
    if ch.can_pyannote():
        luot = nhan_dien_nguoi_noi(ch, nguon, thu_muc_tam, json_nguoi_noi, ban_do, tien_do, nen_dung)
        if not luot:
            log.warning("pyannote khong nghe thay ai noi trong file nay.")
        if cach == NN_PYANNOTE:
            luot, so_doi = nn.xu_ly_luot_noi(luot, ch)
            bang = nn.bang_ten(luot, ch, chinh=nn.nguoi_noi_chinh(luot))
            log.info("Ban do nguoi noi: %d luot%s. %s", len(luot),
                     f" (lam muot doi nhan {so_doi} luot)" if so_doi else "",
                     ", ".join(f"{t} {p:g} phut" for t, p in nn.phut_theo_nguoi(luot, bang).items()))

    # ---- (3) go chu ----
    ket_qua = go_chu_cac_doan(ch, thu_muc_tam, doan, may_khach, ma_am, luot, bang, tien_do, nen_dung)
    cac_model = dem_model(ch, ket_qua)
    if len(cac_model) > 1:
        log.info("Cac model da go chu file nay: %s", ", ".join(f"{m} {so} doan" for m, so in cac_model.items()))

    # ---- (4) ghep ----
    tien_do(GD_NOI_LAI, 0.0)
    than, phut = ghep_ban_go_chu(ch, doan, ket_qua, luot, bang, ban_do)
    noi_dung = than
    if ch.them_phan_dau:
        noi_dung = phan_dau(ch, duong_dan, ban_do.thoi_luong_goc, phut, cac_model) + ("\n\n" + than if than else "")
    if not than:
        log.warning("Ban go chu khong co chu nao.")

    if ch.khi_trung_ten == "danh_so":
        file_ra = ten_khong_trung(file_ra)
    ghi_van_ban(file_ra, noi_dung + ("\n" if noi_dung else ""), ch.ma_hoa, ch.xuong_dong)

    goc_ra = os.path.splitext(file_ra)[0]
    if ch.luu_ban_do_nguoi_noi and luot:
        ten = bang or nn.bang_ten(luot, ch, chinh=nn.nguoi_noi_chinh(luot))
        ghi_van_ban(goc_ra + ".nguoi_noi.txt", ban_do_day_du(luot, ten, ban_do), ch.ma_hoa, ch.xuong_dong)
    if ch.luu_audio_da_lam_sach and co_file_that(os.path.join(thu_muc_tam, FILE_SACH)):
        shutil.copyfile(os.path.join(thu_muc_tam, FILE_SACH), goc_ra + ".sach.flac")
    # nguon.lay() tach tieng ngay tai day neu cac doan deu lay tu cache nen chua tach lan nao.
    if ch.video_luu_am_thanh_tach and nguon.la_video:
        shutil.copyfile(nguon.lay(), f"{goc_ra}.am_thanh.{ch.video_dinh_dang_tach}")

    if phut:
        log.info("Thoi gian noi: %s", ", ".join(f"{t} {p:g} phut" for t, p in phut.items()))
    log.info("HOAN THANH: %s", file_ra)
    if ch.xoa_thu_muc_tam_khi_xong:
        shutil.rmtree(thu_muc_tam, ignore_errors=True)
    tien_do(GD_NOI_LAI, 1.0)
    return KetQuaFile(file_ra, so_doan=len(doan), so_ky_tu=len(than),
                      thoi_luong_goc=ban_do.thoi_luong_goc, phut_theo_nguoi=phut, cac_model=cac_model)


def xoa_thu_muc_tam_cu(ch: CauHinh) -> int:
    """Chi xoa thu muc con do chinh app tao (co danh_sach_doan.json, doan_* hoac am thanh
    tach tu video). Tra ve so thu muc da xoa."""
    goc = thu_muc_tam_goc(ch)
    if not os.path.isdir(goc):
        return 0
    dem = 0
    for ten in os.listdir(goc):
        p = os.path.join(goc, ten)
        if os.path.isdir(p) and any(t == FILE_DANH_SACH_DOAN or t.startswith("doan_")
                                    or t.startswith(FILE_AM_THANH_VIDEO) for t in os.listdir(p)):
            shutil.rmtree(p, ignore_errors=True)
            dem += 1
    return dem


# --------------------------------------------------------------------------
#  MAIN
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Chuyen file audio hoac video thanh ban go chu bang Google AI Studio.")
    parser.add_argument("file", nargs="+", help="Cac file audio hoac video")
    parser.add_argument("--ra", default=None, help="Thu muc luu ban go chu (mac dinh: cung thu muc audio)")
    parser.add_argument("--config", default=None, help="Duong dan config.txt")
    args = parser.parse_args()

    dam_bao_du_lieu()
    ch = doc_cau_hinh(args.config or CONFIG_PATH)
    if args.ra is not None:
        ch.thu_muc_ra = args.ra
    cai_dat_log(ch)
    may_khach = tao_may_khach(ch)
    if may_khach is None:
        log.error("Chua co API key. Nhap key trong app hoac dat bien moi truong GEMINI_API_KEY.")
        sys.exit(2)

    loi = 0
    for f in args.file:
        try:
            chuyen_mot_file(ch, os.path.abspath(f), may_khach)
        except KeyboardInterrupt:
            log.info("Da dung theo yeu cau.")
            sys.exit(130)
        except LoiGoogleAI as e:
            log.error("Google AI bao loi voi %s: %s", f, e)
            loi += 1
            if e.dung_hang_doi:
                break
        except chh.LoiRangBuoc as e:
            log.error("%s", e)
            loi += 1
            break
        except Exception as e:
            log.exception("Loi khi chuyen %s: %s", f, e)
            loi += 1
    sys.exit(1 if loi else 0)


if __name__ == "__main__":
    main()
