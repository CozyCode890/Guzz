#!/usr/bin/env python3
"""
cau_hinh.py
Doc config.txt (trong DATA_DIR, xem duong_dan.py) thanh mot doi tuong CauHinh.

Chay truc tiep file nay de xem cau hinh doc duoc:
    python cau_hinh.py
"""

from __future__ import annotations

import configparser
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime

from duong_dan import APP_DIR, CONFIG_PATH, DATA_DIR, PYTHON_NGUOI_NOI, thu_muc_hf_mac_dinh, tuyet_doi
from video_io import DUOI_VIDEO_MAC_DINH

CAC_DINH_DANG_DOAN = ("flac", "wav", "mp3")
# Rung tieng se lay trong file video: "auto" = rung dau tien, hoac so thu tu rung (0, 1, ...).
RUNG_TU_DONG = "auto"
CAC_CHE_DO_GO_CHU = ("smart", "verbatim")

# Cach nhan dien nguoi noi, xem giai thich trong config.mac_dinh.txt muc [NGUOI_NOI].
NN_PYANNOTE = "pyannote"     # pyannote tren may -> gui audio + ban do nguoi noi cho model da nang
NN_GEMINI = "gemini"         # model *-transcribe tu tach nguoi noi
NN_KET_HOP = "ket_hop"       # model *-transcribe cho moc tung tu, pyannote cho luot noi, ghep tren may
CAC_CACH_NHAN_DIEN = (NN_PYANNOTE, NN_GEMINI, NN_KET_HOP)
CAC_CACH_GUI_BAN_DO = ("file", "van_ban")
CAC_THIET_BI = ("auto", "cuda", "cpu")
CAC_NGUON_NHAN_DIEN = ("da_lam_sach", "goc")

CAC_KHI_TRUNG_TEN = ("danh_so", "ghi_de", "bo_qua")
CAC_MA_HOA = ("utf-8", "utf-8-sig")
CAC_XUONG_DONG = ("crlf", "lf")
CAC_MO_KHI_XONG = ("khong", "file", "thu_muc")
CAC_KHI_FILE_LOI = ("tiep_tuc", "dung")
CAC_CHU_DE = ("auto", "light", "dark")
CAC_TY_LE = ("auto", "1.0", "1.25", "1.5", "1.75", "2.0")
CAC_MUC_NHAT_KY = ("INFO", "DEBUG")

# Model *-transcribe gioi han 30 phut audio moi yeu cau khi bat tach nguoi noi / moc tung tu.
PHUT_TOI_DA_KHI_CO_MOC_TU = 30

# Thu tu du phong uu tien model con nhieu han muc NGAY nhat: flash-lite 500 yeu cau/ngay,
# hai model flash chi 20/ngay (3.8-flash hay bao 5xx "high demand" nen de sau 3.5-flash).
MODEL_DU_PHONG_MAC_DINH = ("gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.5-transcribe")
# Han muc goi mien phi doc tu https://ai.dev/rate-limit ngay 2026-09-18: token/phut, yeu cau/phut, yeu cau/ngay.
HAN_MUC_MAC_DINH = {
    "gemini-3.5-transcribe":  (10000, 3, 25),
    "gemini-3.5-flash":      (250000, 5, 20),
    "gemini-3.8-flash":      (250000, 5, 20),
    "gemini-3.5-flash-lite": (250000, 15, 500),
}


def la_model_go_chu(model: str) -> bool:
    """Model chuyen go chu (gemini-3.5-transcribe...) chi nhan audio, khong nhan prompt hay file kem."""
    return "transcribe" in (model or "").lower()


def cac_cach_hop_le(model: str) -> tuple:
    """
    Cach nhan dien nguoi noi dung duoc voi model:
      *-transcribe : gemini (Google tu tach giong) va ket_hop (can moc tung tu cua Google).
                     pyannote + prompt bi khoa vi model nay khong nhan prompt / file kem.
      model da nang: chi pyannote + prompt. Tach giong tren Google (gemini, ket_hop) bi khoa.
    """
    return (NN_GEMINI, NN_KET_HOP) if la_model_go_chu(model) else (NN_PYANNOTE,)


def model_hop_voi_cach(model: str, cach: str | None) -> bool:
    """cach None = tat nhan dien nguoi noi: model nao cung duoc."""
    return cach is None or cach in cac_cach_hop_le(model)


def cach_thay_the(model: str, cach: str) -> str:
    """Cach gan nhat hop voi model: pyannote <-> ket_hop (deu dung pyannote tren may), gemini -> pyannote."""
    hop = cac_cach_hop_le(model)
    if cach in hop:
        return cach
    if cach == NN_PYANNOTE and NN_KET_HOP in hop:
        return NN_KET_HOP
    if cach == NN_KET_HOP and NN_PYANNOTE in hop:
        return NN_PYANNOTE
    return hop[0]


class LoiRangBuoc(ValueError):
    """Model va cach nhan dien khong di cung nhau: file nao cung se loi, nen dung ca hang doi."""
    dung_hang_doi = True

_CAC_BIEN_TEN_FILE = {"ten": "x", "ngay_ghi": "x", "ngay": "x", "gio": "x", "model": "x"}


@dataclass
class CauHinh:
    # ---- [KET_QUA] ----
    thu_muc_ra: str = ""                 # rong = cung thu muc voi file audio
    mau_ten_file: str = "{ten}"
    duoi_file_ra: str = ".txt"
    khi_trung_ten: str = "danh_so"
    ma_hoa: str = "utf-8"
    xuong_dong: str = "crlf"
    them_phan_dau: bool = False
    danh_dau_doan: bool = False
    luu_ban_do_nguoi_noi: bool = False
    luu_audio_da_lam_sach: bool = False
    mo_khi_xong: str = "khong"

    # ---- [XU_LY_AM_THANH] ----
    duoi_file_nhan: tuple = (".m4a", ".flac", ".mp3", ".wav", ".wma", ".aac", ".ogg", ".opus")
    khu_on: bool = True
    tan_so_lay_mau: int = 16000
    target_dbfs: float = -16.0
    cat_khoang_lang: bool = True
    min_silence_len: int = 700
    silence_thresh_offset: int = 16
    keep_silence: int = 300
    noise_sample_sec: float = 2.0
    bandpass_low: int = 80
    bandpass_high: int = 8000
    prop_decrease: float = 0.85
    level_window_sec: float = 0.0

    # ---- [XU_LY_VIDEO] ----
    nhan_file_video: bool = True
    duoi_file_video: tuple = DUOI_VIDEO_MAC_DINH
    video_rung_am_thanh: str = RUNG_TU_DONG
    video_tach_truoc: bool = True
    video_dinh_dang_tach: str = "flac"
    video_luu_am_thanh_tach: bool = False
    video_bo_qua_khong_tieng: bool = True

    # ---- [CAT_DOAN] ----
    phut_moi_doan: float = 10.0
    giay_tim_cho_cat: float = 20.0
    giay_doan_cuoi_toi_thieu: float = 60.0
    dinh_dang_doan: str = "flac"

    # ---- [GOOGLE_AI] ----
    model: str = "gemini-3.5-flash"
    che_do_go_chu: str = "smart"
    ngon_ngu: tuple = ()
    tu_vung: tuple = ()
    file_prompt: str = "prompt.txt"
    luu_tren_server: bool = False
    timeout_giay: int = 600
    so_lan_thu_moi_doan: int = 4
    xoa_file_tren_server: bool = True
    gioi_han_token_moi_phut: int = 10000

    # ---- [DOI_MODEL] ----
    tu_doi_model: bool = True
    model_du_phong: tuple = MODEL_DU_PHONG_MAC_DINH
    so_lan_thu_truoc_khi_doi: int = 2
    phut_khoa_khi_qua_tai: float = 10.0
    quay_lai_model_chinh: bool = True
    doi_khi_cho_qua_giay: int = 0
    cho_toi_da_khi_het_model_phut: float = 20.0
    khoa_truoc_khi_cham_han_muc: bool = True

    # ---- [HAN_MUC] ---- ten model -> (token/phut, yeu cau/phut, yeu cau/ngay)
    han_muc_model: dict = field(default_factory=lambda: dict(HAN_MUC_MAC_DINH))

    # ---- [NGUOI_NOI] ----
    nn_bat: bool = False
    nn_cach: str = NN_PYANNOTE
    nn_python: str = "auto"
    nn_model: str = "pyannote/speaker-diarization-community-1"
    nn_thu_muc_model: str = "auto"
    nn_ngoai_tuyen: bool = False
    nn_thiet_bi: str = "auto"
    nn_so_nguoi: int = 0
    nn_it_nhat: int = 1
    nn_nhieu_nhat: int = 6
    nn_chay_tren: str = "da_lam_sach"
    nn_timeout_giay: int = 3600
    nn_lam_muot: bool = True
    nn_kep_toi_da_giay: float = 3.0
    nn_kep_nghi_giay: float = 1.0
    nn_mat_do_cua_so_giay: float = 60.0
    nn_mat_do_toi_thieu_giay: float = 15.0
    nn_gop_luot_giay: float = 1.0
    nn_dat_ten_nguoi_chinh: bool = True
    nn_ten_nguoi_chinh: str = "Giảng viên"
    nn_ten_nguoi_khac: str = "Người hỏi"
    nn_ten_chung: str = "Người nói"
    nn_cach_gui: str = "file"
    nn_file_prompt: str = "prompt_nguoi_noi.txt"
    nn_moc_thoi_gian: bool = True
    nn_mau_doan: str = "[{moc}] {nguoi}: {noi_dung}"
    nn_gop_doan_toi_da_giay: float = 60.0
    nn_gop_khoang_lang_giay: float = 3.0
    nn_danh_dau_xem_lai: bool = True

    # ---- [HANG_DOI] ----
    khi_file_loi: str = "tiep_tuc"
    thong_bao_khi_xong: bool = True
    am_bao_khi_xong: bool = True
    chong_ngu: bool = True
    nho_thu_muc_chon_file: bool = True
    thu_muc_chon_file: str = ""
    them_thu_muc_con: bool = False

    # ---- [GIAO_DIEN] ----
    ngon_ngu_giao_dien: str = "vi"
    chu_de: str = "auto"
    mau_nhan: str = ""
    mica: bool = True
    ty_le: str = "auto"
    co_chu_nhat_ky: int = 12
    nho_cua_so: bool = True

    # ---- [HE_THONG] ----
    thu_muc_tam: str = "tmp"
    xoa_thu_muc_tam_khi_xong: bool = True
    duong_dan_ffmpeg: str = "auto"
    file_log: str = r"logs\guzz.log"
    muc_nhat_ky: str = "INFO"
    dung_luong_log_mb: int = 2
    so_file_log_cu: int = 5

    # ---------- Google AI ----------

    def la_model_go_chu(self, model: str | None = None) -> bool:
        return la_model_go_chu(model if model is not None else self.model)

    def cach_nhan_dien(self) -> str | None:
        """Cach nhan dien nguoi noi dang dung, None neu tat."""
        return self.nn_cach if self.nn_bat else None

    def chuoi_model(self) -> list[str]:
        """
        Thu tu model se thu: model chinh roi cac model du phong (neu bat tu doi model) hop voi
        cach nhan dien dang chon, bo trung. Moi model trong chuoi deu nhan cung mot kieu yeu cau.
        """
        cach = self.cach_nhan_dien()
        ds = [self.model]
        if self.tu_doi_model:
            for m in self.model_du_phong:
                if m and m not in ds and model_hop_voi_cach(m, cach):
                    ds.append(m)
        return ds

    def han_muc_cua(self, model: str) -> tuple[int, int, int]:
        """Han muc khai bao trong [HAN_MUC]; chua khai bao thi (gioi_han_token_moi_phut, 0, 0)."""
        return tuple(self.han_muc_model.get(model) or (self.gioi_han_token_moi_phut, 0, 0))

    def can_pyannote(self) -> bool:
        return self.nn_bat and self.nn_cach in (NN_PYANNOTE, NN_KET_HOP)

    def doc_prompt(self) -> str:
        return _doc_prompt(self.file_prompt)

    def doc_prompt_nguoi_noi(self) -> str:
        return _doc_prompt(self.nn_file_prompt)

    # ---------- video ----------

    def la_file_video(self, duong_dan: str) -> bool:
        return os.path.splitext(duong_dan)[1].lower() in self.duoi_file_video

    def cac_duoi_nhan(self) -> tuple:
        """Moi duoi file duoc nhan khi chon / keo tha: audio, va video neu dang bat."""
        if not self.nhan_file_video:
            return tuple(self.duoi_file_nhan)
        return tuple(self.duoi_file_nhan) + tuple(
            d for d in self.duoi_file_video if d not in self.duoi_file_nhan)

    def can_tach_am_thanh_video(self) -> bool:
        """Luu am thanh tach ra thi phai tach, du tat tach_am_thanh_truoc."""
        return self.video_tach_truoc or self.video_luu_am_thanh_tach

    # ---------- nguoi noi ----------

    def duong_dan_python_nguoi_noi(self) -> str:
        if not self.nn_python or self.nn_python.lower() == "auto":
            return PYTHON_NGUOI_NOI
        return tuyet_doi(self.nn_python)

    def thu_muc_model_hf(self) -> str:
        if not self.nn_thu_muc_model or self.nn_thu_muc_model.lower() == "auto":
            return thu_muc_hf_mac_dinh()
        return tuyet_doi(self.nn_thu_muc_model)

    # ---------- ket qua ----------

    def ten_file_ra(self, duong_dan_audio: str, luc_ghi: datetime | None = None,
                    bay_gio: datetime | None = None) -> str:
        """Ten ban go chu (khong kem thu muc) theo mau_ten_file."""
        bay_gio = bay_gio or datetime.now()
        if luc_ghi is None:
            try:
                luc_ghi = datetime.fromtimestamp(os.path.getctime(duong_dan_audio))
            except OSError:
                luc_ghi = bay_gio
        ten = self.mau_ten_file.format(
            ten=os.path.splitext(os.path.basename(duong_dan_audio))[0],
            ngay_ghi=luc_ghi.strftime("%Y-%m-%d_%H%M"),
            ngay=bay_gio.strftime("%Y-%m-%d"),
            gio=bay_gio.strftime("%H%M"),
            model=self.model,
        )
        return lam_sach_ten_file(ten) + self.duoi_file_ra

    def thu_muc_ket_qua(self, duong_dan_audio: str) -> str:
        if self.thu_muc_ra.strip():
            return tuyet_doi(self.thu_muc_ra, goc=os.path.dirname(os.path.abspath(duong_dan_audio)))
        return os.path.dirname(os.path.abspath(duong_dan_audio))


def duong_dan_prompt(ten: str) -> str:
    """File prompt trong thu muc du lieu; chua co (xoa nham, chua chay app lan nao) thi dung ban mau."""
    p = tuyet_doi(ten)
    mau = os.path.join(APP_DIR, ten)
    if not os.path.exists(p) and not os.path.isabs(os.path.expandvars(ten)) and os.path.exists(mau):
        return mau
    return p


def _doc_prompt(ten: str) -> str:
    with open(duong_dan_prompt(ten), "r", encoding="utf-8-sig") as f:
        return f.read().strip()


_KY_TU_CAM = r'<>:"/\|?*'


def lam_sach_ten_file(ten: str) -> str:
    """Bo cac ky tu Windows khong cho dat ten file."""
    for c in _KY_TU_CAM:
        ten = ten.replace(c, "-")
    return ten.strip().strip(".") or "transcript"


def _bool(s: str, mac_dinh=False) -> bool:
    if s is None:
        return mac_dinh
    return s.strip().lower() in ("true", "1", "yes", "co", "y", "on")


def _danh_sach(s: str) -> tuple:
    return tuple(x.strip() for x in (s or "").split(",") if x.strip())


def doc_han_muc(ten: str, s: str) -> tuple[int, int, int]:
    """'10000, 0, 25' -> (10000, 0, 25). Thieu so thi coi la 0."""
    phan = [x.strip() for x in (s or "").split(",")]
    try:
        so = [max(0, int(float(x))) if x else 0 for x in phan[:3]]
    except ValueError:
        raise ValueError(f"[HAN_MUC] {ten} = '{s}' khong hop le. Ghi <token/phut>, <yeu cau/phut>, "
                         "<yeu cau/ngay>, vi du 10000, 0, 25.") from None
    return tuple(so + [0] * (3 - len(so)))


def _chon(muc: str, key: str, gia_tri: str, cac_gia_tri: tuple, nghiem: bool = True) -> str:
    """Gia tri phai nam trong cac_gia_tri. nghiem = False (tuy chon giao dien): sai thi lay gia tri dau."""
    if gia_tri in cac_gia_tri:
        return gia_tri
    if not nghiem:
        return cac_gia_tri[0]
    raise ValueError(f"[{muc}] {key} = '{gia_tri}' khong hop le. "
                     f"Dung mot trong: {', '.join(cac_gia_tri)}.")


def doc_cau_hinh(duong_dan: str = CONFIG_PATH) -> CauHinh:
    if not os.path.exists(duong_dan):
        raise FileNotFoundError(f"Khong tim thay file cau hinh: {duong_dan}")

    # interpolation=None: neu khong configparser se coi dau % trong duong dan
    # kieu %LOCALAPPDATA% la cu phap noi suy va nem loi.
    # delimiters chi co "=": mau_doan co dau ":" ("{nguoi}: {noi_dung}").
    cp = configparser.ConfigParser(
        inline_comment_prefixes=("#", ";"), interpolation=None, delimiters=("=",)
    )
    with open(duong_dan, "r", encoding="utf-8-sig") as f:
        cp.read_file(f)

    def muc(ten):
        # Thieu ca muc thi dung section DEFAULT (rong): moi gia tri lay mac dinh.
        return cp[ten] if cp.has_section(ten) else cp[cp.default_section]

    kq = muc("KET_QUA")
    xl = muc("XU_LY_AM_THANH")
    vd = muc("XU_LY_VIDEO")
    cd = muc("CAT_DOAN")
    ga = muc("GOOGLE_AI")
    nn = muc("NGUOI_NOI")
    dm = muc("DOI_MODEL")
    hd = muc("HANG_DOI")
    gd = muc("GIAO_DIEN")
    ht = muc("HE_THONG")
    m = CauHinh()

    duoi = kq.get("duoi_file_ra", ".txt").strip().lower() or ".txt"

    ch = CauHinh(
        thu_muc_ra=kq.get("thu_muc_ra", "").strip(),
        mau_ten_file=kq.get("mau_ten_file", "{ten}").strip() or "{ten}",
        duoi_file_ra=duoi if duoi.startswith(".") else "." + duoi,
        khi_trung_ten=_chon("KET_QUA", "khi_trung_ten", kq.get("khi_trung_ten", "danh_so").strip(),
                            CAC_KHI_TRUNG_TEN),
        ma_hoa=_chon("KET_QUA", "ma_hoa", kq.get("ma_hoa", "utf-8").strip().lower(), CAC_MA_HOA),
        xuong_dong=_chon("KET_QUA", "xuong_dong", kq.get("xuong_dong", "crlf").strip().lower(),
                         CAC_XUONG_DONG),
        them_phan_dau=_bool(kq.get("them_phan_dau"), False),
        danh_dau_doan=_bool(kq.get("danh_dau_doan"), False),
        luu_ban_do_nguoi_noi=_bool(kq.get("luu_ban_do_nguoi_noi"), False),
        luu_audio_da_lam_sach=_bool(kq.get("luu_audio_da_lam_sach"), False),
        mo_khi_xong=_chon("KET_QUA", "mo_khi_xong", kq.get("mo_khi_xong", "khong").strip().lower(),
                          CAC_MO_KHI_XONG),

        duoi_file_nhan=tuple(
            e.lower() if e.startswith(".") else "." + e.lower()
            for e in _danh_sach(xl.get("duoi_file_nhan", ",".join(m.duoi_file_nhan)))
        ),
        khu_on=_bool(xl.get("khu_on"), True),
        tan_so_lay_mau=xl.getint("tan_so_lay_mau", 16000) or 16000,
        target_dbfs=xl.getfloat("target_dbfs", -16.0),
        cat_khoang_lang=_bool(xl.get("cat_khoang_lang"), True),
        min_silence_len=xl.getint("min_silence_len", 700),
        silence_thresh_offset=xl.getint("silence_thresh_offset", 16),
        keep_silence=xl.getint("keep_silence", 300),
        noise_sample_sec=xl.getfloat("noise_sample_sec", 2.0),
        bandpass_low=xl.getint("bandpass_thap", 80),
        bandpass_high=xl.getint("bandpass_cao", 8000),
        prop_decrease=xl.getfloat("ty_le_giam_on", 0.85),
        level_window_sec=xl.getfloat("can_bang_am_luong_giay", 0.0),

        nhan_file_video=_bool(vd.get("nhan_file_video"), True),
        duoi_file_video=tuple(
            e.lower() if e.startswith(".") else "." + e.lower()
            for e in _danh_sach(vd.get("duoi_file_video", ",".join(m.duoi_file_video)))
        ),
        video_rung_am_thanh=vd.get("rung_am_thanh", RUNG_TU_DONG).strip().lower() or RUNG_TU_DONG,
        video_tach_truoc=_bool(vd.get("tach_am_thanh_truoc"), True),
        video_dinh_dang_tach=vd.get("dinh_dang_tach", "flac").strip().lower().lstrip("."),
        video_luu_am_thanh_tach=_bool(vd.get("luu_am_thanh_tach"), False),
        video_bo_qua_khong_tieng=_bool(vd.get("bo_qua_video_khong_tieng"), True),

        phut_moi_doan=cd.getfloat("phut_moi_doan", 10.0),
        giay_tim_cho_cat=cd.getfloat("giay_tim_cho_cat", 20.0),
        giay_doan_cuoi_toi_thieu=cd.getfloat("giay_doan_cuoi_toi_thieu", 60.0),
        dinh_dang_doan=cd.get("dinh_dang_doan", "flac").strip().lower().lstrip("."),

        model=ga.get("model", m.model).strip(),
        che_do_go_chu=_chon("GOOGLE_AI", "che_do_go_chu", ga.get("che_do_go_chu", "smart").strip().lower(),
                            CAC_CHE_DO_GO_CHU),
        ngon_ngu=_danh_sach(ga.get("ngon_ngu", "")),
        tu_vung=_danh_sach(ga.get("tu_vung", "")),
        file_prompt=ga.get("file_prompt", "prompt.txt").strip() or "prompt.txt",
        luu_tren_server=_bool(ga.get("luu_tren_server"), False),
        timeout_giay=ga.getint("timeout_giay", 600),
        so_lan_thu_moi_doan=ga.getint("so_lan_thu_moi_doan", 4),
        xoa_file_tren_server=_bool(ga.get("xoa_file_tren_server"), True),
        gioi_han_token_moi_phut=max(0, ga.getint("gioi_han_token_moi_phut", 10000)),

        tu_doi_model=_bool(dm.get("bat"), True),
        model_du_phong=_danh_sach(dm.get("model_du_phong", ",".join(m.model_du_phong))),
        so_lan_thu_truoc_khi_doi=max(1, dm.getint("so_lan_thu_truoc_khi_doi", 2)),
        phut_khoa_khi_qua_tai=max(0.0, dm.getfloat("phut_khoa_khi_qua_tai", 10.0)),
        quay_lai_model_chinh=_bool(dm.get("quay_lai_model_chinh"), True),
        doi_khi_cho_qua_giay=max(0, dm.getint("doi_khi_cho_qua_giay", 0)),
        cho_toi_da_khi_het_model_phut=max(0.0, dm.getfloat("cho_toi_da_khi_het_model_phut", 20.0)),
        khoa_truoc_khi_cham_han_muc=_bool(dm.get("khoa_truoc_khi_cham_han_muc"), True),
        han_muc_model=({ten: doc_han_muc(ten, gia_tri) for ten, gia_tri in cp.items("HAN_MUC")
                        if gia_tri is not None} if cp.has_section("HAN_MUC") else dict(HAN_MUC_MAC_DINH)),

        nn_bat=_bool(nn.get("bat"), False),
        nn_cach=_chon("NGUOI_NOI", "cach_nhan_dien", nn.get("cach_nhan_dien", NN_PYANNOTE).strip().lower(),
                      CAC_CACH_NHAN_DIEN),
        nn_python=nn.get("duong_dan_python", "auto").strip() or "auto",
        nn_model=nn.get("model_pyannote", m.nn_model).strip() or m.nn_model,
        nn_thu_muc_model=nn.get("thu_muc_model", "auto").strip() or "auto",
        nn_ngoai_tuyen=_bool(nn.get("chi_dung_model_da_tai"), False),
        nn_thiet_bi=_chon("NGUOI_NOI", "thiet_bi", nn.get("thiet_bi", "auto").strip().lower(), CAC_THIET_BI),
        nn_so_nguoi=max(0, nn.getint("so_nguoi", 0)),
        nn_it_nhat=max(0, nn.getint("so_nguoi_it_nhat", 1)),
        nn_nhieu_nhat=max(0, nn.getint("so_nguoi_nhieu_nhat", 6)),
        nn_chay_tren=_chon("NGUOI_NOI", "chay_tren", nn.get("chay_tren", "da_lam_sach").strip().lower(),
                           CAC_NGUON_NHAN_DIEN),
        nn_timeout_giay=int(nn.getfloat("timeout_phut", 60) * 60),
        nn_lam_muot=_bool(nn.get("lam_muot"), True),
        nn_kep_toi_da_giay=nn.getfloat("kep_toi_da_giay", 3.0),
        nn_kep_nghi_giay=nn.getfloat("kep_nghi_giay", 1.0),
        nn_mat_do_cua_so_giay=nn.getfloat("mat_do_cua_so_giay", 60.0),
        nn_mat_do_toi_thieu_giay=nn.getfloat("mat_do_toi_thieu_giay", 15.0),
        nn_gop_luot_giay=max(0.0, nn.getfloat("gop_luot_cach_nhau_giay", 1.0)),
        nn_dat_ten_nguoi_chinh=_bool(nn.get("dat_ten_nguoi_chinh"), True),
        nn_ten_nguoi_chinh=nn.get("ten_nguoi_chinh", m.nn_ten_nguoi_chinh).strip() or m.nn_ten_nguoi_chinh,
        nn_ten_nguoi_khac=nn.get("ten_nguoi_khac", m.nn_ten_nguoi_khac).strip() or m.nn_ten_nguoi_khac,
        nn_ten_chung=nn.get("ten_chung", m.nn_ten_chung).strip() or m.nn_ten_chung,
        nn_cach_gui=_chon("NGUOI_NOI", "cach_gui_ban_do", nn.get("cach_gui_ban_do", "file").strip().lower(),
                          CAC_CACH_GUI_BAN_DO),
        nn_file_prompt=nn.get("file_prompt", m.nn_file_prompt).strip() or m.nn_file_prompt,
        nn_moc_thoi_gian=_bool(nn.get("moc_thoi_gian"), True),
        nn_mau_doan=nn.get("mau_doan", m.nn_mau_doan).strip() or m.nn_mau_doan,
        nn_gop_doan_toi_da_giay=max(0.0, nn.getfloat("gop_doan_toi_da_giay", 60.0)),
        nn_gop_khoang_lang_giay=max(0.0, nn.getfloat("gop_khoang_lang_giay", 3.0)),
        nn_danh_dau_xem_lai=_bool(nn.get("danh_dau_xem_lai"), True),

        khi_file_loi=_chon("HANG_DOI", "khi_file_loi", hd.get("khi_file_loi", "tiep_tuc").strip().lower(),
                           CAC_KHI_FILE_LOI),
        thong_bao_khi_xong=_bool(hd.get("thong_bao_khi_xong"), True),
        am_bao_khi_xong=_bool(hd.get("am_bao_khi_xong"), True),
        chong_ngu=_bool(hd.get("chong_ngu"), True),
        nho_thu_muc_chon_file=_bool(hd.get("nho_thu_muc_chon_file"), True),
        thu_muc_chon_file=hd.get("thu_muc_chon_file", "").strip(),
        them_thu_muc_con=_bool(hd.get("them_thu_muc_con"), False),

        # Tuy chon giao dien viet sai thi lay mac dinh, khong lam hong ca viec chuyen doi.
        ngon_ngu_giao_dien=_chon("GIAO_DIEN", "ngon_ngu", gd.get("ngon_ngu", "vi").strip().lower(),
                                 ("vi", "en"), nghiem=False),
        chu_de=_chon("GIAO_DIEN", "chu_de", gd.get("chu_de", "auto").strip().lower(), CAC_CHU_DE, nghiem=False),
        mau_nhan=gd.get("mau_nhan", "").strip(),
        mica=_bool(gd.get("hieu_ung_mica"), True),
        ty_le=_chon("GIAO_DIEN", "ty_le_hien_thi", gd.get("ty_le_hien_thi", "auto").strip().lower(),
                    CAC_TY_LE, nghiem=False),
        co_chu_nhat_ky=min(32, max(8, gd.getint("co_chu_nhat_ky", 12))),
        nho_cua_so=_bool(gd.get("nho_kich_thuoc_cua_so"), True),

        thu_muc_tam=ht.get("thu_muc_tam", "tmp").strip() or "tmp",
        xoa_thu_muc_tam_khi_xong=_bool(ht.get("xoa_thu_muc_tam_khi_xong"), True),
        duong_dan_ffmpeg=ht.get("duong_dan_ffmpeg", "auto").strip() or "auto",
        file_log=ht.get("file_log", m.file_log).strip() or m.file_log,
        muc_nhat_ky=_chon("HE_THONG", "muc_nhat_ky", ht.get("muc_nhat_ky", "INFO").strip().upper(),
                          CAC_MUC_NHAT_KY, nghiem=False),
        dung_luong_log_mb=max(1, ht.getint("dung_luong_log_mb", 2)),
        so_file_log_cu=max(0, ht.getint("so_file_log_cu", 5)),
    )
    kiem_tra(ch)
    return ch


def kiem_tra(ch: CauHinh):
    """Bao loi som nhung gia tri lam hong viec chuyen doi. GUI goi truoc khi luu."""
    if not ch.model:
        raise ValueError("[GOOGLE_AI] model dang de trong.")
    # GUI dung lai CauHinh tu cac o tren man hinh: chan gia tri la truoc khi ghi xuong config.txt.
    for muc, key, gia_tri, cac_gia_tri in (
        ("NGUOI_NOI", "cach_nhan_dien", ch.nn_cach, CAC_CACH_NHAN_DIEN),
        ("NGUOI_NOI", "cach_gui_ban_do", ch.nn_cach_gui, CAC_CACH_GUI_BAN_DO),
        ("NGUOI_NOI", "thiet_bi", ch.nn_thiet_bi, CAC_THIET_BI),
        ("NGUOI_NOI", "chay_tren", ch.nn_chay_tren, CAC_NGUON_NHAN_DIEN),
        ("KET_QUA", "khi_trung_ten", ch.khi_trung_ten, CAC_KHI_TRUNG_TEN),
        ("KET_QUA", "ma_hoa", ch.ma_hoa, CAC_MA_HOA),
        ("KET_QUA", "xuong_dong", ch.xuong_dong, CAC_XUONG_DONG),
        ("KET_QUA", "mo_khi_xong", ch.mo_khi_xong, CAC_MO_KHI_XONG),
        ("HANG_DOI", "khi_file_loi", ch.khi_file_loi, CAC_KHI_FILE_LOI),
    ):
        if not isinstance(gia_tri, str):
            gia_tri = repr(gia_tri)
        _chon(muc, key, gia_tri, cac_gia_tri)
    if ch.phut_moi_doan <= 0:
        raise ValueError("[CAT_DOAN] phut_moi_doan phai lon hon 0.")
    if ch.dinh_dang_doan not in CAC_DINH_DANG_DOAN:
        raise ValueError(f"[CAT_DOAN] dinh_dang_doan = '{ch.dinh_dang_doan}' khong hop le. "
                         f"Dung mot trong: {', '.join(CAC_DINH_DANG_DOAN)}.")
    if ch.video_dinh_dang_tach not in CAC_DINH_DANG_DOAN:
        raise ValueError(f"[XU_LY_VIDEO] dinh_dang_tach = '{ch.video_dinh_dang_tach}' khong hop le. "
                         f"Dung mot trong: {', '.join(CAC_DINH_DANG_DOAN)}.")
    rung = (ch.video_rung_am_thanh or "").strip().lower()
    if rung != RUNG_TU_DONG and not rung.isdigit():
        raise ValueError(f"[XU_LY_VIDEO] rung_am_thanh = '{ch.video_rung_am_thanh}' khong hop le. "
                         f"Dung '{RUNG_TU_DONG}' hoac so thu tu rung tieng (0, 1, 2...).")
    if ch.nn_bat and ch.nn_cach != NN_PYANNOTE and ch.phut_moi_doan > PHUT_TOI_DA_KHI_CO_MOC_TU:
        raise ValueError(f"[CAT_DOAN] phut_moi_doan toi da {PHUT_TOI_DA_KHI_CO_MOC_TU} khi nhan dien "
                         "nguoi noi bang model *-transcribe (Google gioi han 30 phut moi yeu cau).")
    if ch.nn_it_nhat and ch.nn_nhieu_nhat and ch.nn_it_nhat > ch.nn_nhieu_nhat:
        raise ValueError("[NGUOI_NOI] so_nguoi_it_nhat lon hon so_nguoi_nhieu_nhat.")
    try:
        ch.mau_ten_file.format(**_CAC_BIEN_TEN_FILE)
    except (KeyError, IndexError, ValueError) as e:
        raise ValueError(f"[KET_QUA] mau_ten_file = '{ch.mau_ten_file}' khong hop le ({e}). "
                         "Dung cac bien {ten} {ngay_ghi} {ngay} {gio} {model}.") from None
    try:
        ch.nn_mau_doan.format(moc="x", nguoi="x", noi_dung="x")
    except (KeyError, IndexError, ValueError) as e:
        raise ValueError(f"[NGUOI_NOI] mau_doan = '{ch.nn_mau_doan}' khong hop le ({e}). "
                         "Dung cac bien {moc} {nguoi} {noi_dung}.") from None


def loi_rang_buoc(ch: CauHinh) -> str | None:
    """Thong bao neu model chinh khong di duoc voi cach nhan dien nguoi noi dang bat."""
    cach = ch.cach_nhan_dien()
    if model_hop_voi_cach(ch.model, cach):
        return None
    if cach == NN_PYANNOTE:
        return (f"Cach nhan dien 'pyannote + prompt' can model da nang (nhan duoc prompt), nhung model dang chon "
                f"'{ch.model}' la *-transcribe. Doi model (vd gemini-3.5-flash) hoac chon cach Ket hop / "
                "Gemini tu tach.")
    return (f"Cach nhan dien '{cach}' tach giong tren Google nen can model *-transcribe, nhung model dang chon "
            f"'{ch.model}' khong phai. Doi model sang gemini-3.5-transcribe hoac chon cach pyannote + prompt.")


def thu_muc_tam_goc(ch: CauHinh) -> str:
    return tuyet_doi(ch.thu_muc_tam)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ch = doc_cau_hinh()
    print(f"Du lieu        : {DATA_DIR}")
    print(f"Thu muc ra     : {ch.thu_muc_ra or '(cung thu muc voi file audio)'}")
    print(f"Mau ten file   : {ch.mau_ten_file}{ch.duoi_file_ra}")
    print(f"Khu on         : {ch.khu_on}   Cat khoang lang: {ch.cat_khoang_lang}")
    print(f"Cat doan       : {ch.phut_moi_doan:g} phut/doan, dinh dang {ch.dinh_dang_doan}")
    print(f"Video          : {'nhan' if ch.nhan_file_video else 'khong nhan'}, rung tieng "
          f"{ch.video_rung_am_thanh}, tach truoc: {ch.video_tach_truoc}")
    print(f"Model          : {' -> '.join(ch.chuoi_model())}")
    print(f"Nguoi noi      : {ch.nn_cach if ch.nn_bat else 'tat'}")
    if loi_rang_buoc(ch):
        print(f"CANH BAO       : {loi_rang_buoc(ch)}")
    if ch.can_pyannote():
        print(f"Python pyannote: {ch.duong_dan_python_nguoi_noi()}")
        print(f"Model HF       : {ch.nn_model} ({ch.thu_muc_model_hf()})")
