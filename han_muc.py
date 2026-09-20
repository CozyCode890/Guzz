"""
han_muc.py
So theo doi luot dung va han muc cua tung model Google AI (chi dung thu vien chuan).

    - dem yeu cau / token trong ngay cua tung model (ngay tinh theo gio My - Thai Binh
      Duong, vi Google tinh lai han muc ngay luc 0h gio do = 14h hoac 15h gio Viet Nam);
    - khoa model da cham han muc, dang qua tai, hay khong ton tai, kem thoi diem mo lai;
    - nho han muc Google bao trong loi 429 ("limit: 25") de lan sau tu khoa truoc;
    - trang thai cho hien tai (dang cho han muc token/phut, hay moi model deu khoa);
    - lich su su kien (khoa, mo khoa, doi model, loi) cho trang Han muc cua app.

Du lieu luu trong su_dung.json o thu muc dung chung (xem duong_dan_chung.py): Guzz,
GoogleAITranscribe va Header dung key khac nhau nhung chung mot tai khoan Google, ma
Google dem han muc theo tai khoan nen han muc la mot - model bi khoa o app nay thi app
kia cung phai tranh. Khoa theo ngay vi vay con nguyen khi mo lai app.

Trong mot app: luong chuyen doi ghi, giao dien doc, moi ham deu giu khoa (RLock).
Giua cac app: moi lan sua la mot giao dich - gianh khoa file (su_dung.json.khoa), doc
lai file (app kia co the vua ghi), sua, ghi, nha khoa. Luc doc thi so van tay file
(mtime + co), khac di la doc lai, nen giao dien thay ngay viec app kia vua lam.
"""

from __future__ import annotations

import contextlib
import copy
import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, time as gio_trong_ngay, timedelta, timezone

log = logging.getLogger("Guzz")

TEN_FILE = "su_dung.json"
DUOI_DA_GOP = ".da_gop"      # ten file su_dung.json cu sau khi da gop vao file chung
GIAY_CHO_KHOA = 5.0          # cho toi da bao lau de gianh khoa file, qua thi ghi luon

# File vua duoc ghi trong ngan nay giay thi khong tin van tay (mtime + co) nua ma doc
# that. Do: 300 lan ghi lien tiep cung co chu -> 15% lan co mtime trung y lan truoc, vi
# dong ho he thong khong nhuyen bang toc do ghi. Qua nguong nay thi mtime chac chan da
# on dinh, moi thay doi sau do deu lam mtime nhay.
GIAY_VAN_TAY_CHUA_CHAC = 2.0

# Ly do khoa model
KHOA_HAN_MUC_NGAY = "han_muc_ngay"          # Google bao 429 het han muc trong ngay
KHOA_HAN_MUC_PHUT = "han_muc_phut"          # 429 van con sau khi da thu lai (han muc theo phut)
KHOA_CHAM_HAN_MUC = "cham_han_muc_ngay"     # app tu dem du so yeu cau/ngay, khoa truoc khi bi 429
KHOA_QUA_TAI = "qua_tai"                    # HTTP 5xx (high demand, unavailable)
KHOA_KHONG_TON_TAI = "khong_ton_tai"        # HTTP 404: key khong dung duoc model nay

# Loai su kien trong lich su
SK_KHOA = "khoa"
SK_MO_KHOA = "mo_khoa"
SK_HET_KHOA = "het_khoa"
SK_DOI_MODEL = "doi_model"
SK_LOI = "loi"
SK_HOC_HAN_MUC = "hoc_han_muc"
SK_CHO = "cho"

CAC_TRUONG_HAN_MUC = ("tpm", "rpm", "rpd")


# --------------------------------------------------------------------------
#  KHOA FILE GIUA CAC TIEN TRINH
# --------------------------------------------------------------------------
# Ca ba app cung ghi mot su_dung.json, nen moi lan ghi deu phai:
# gianh khoa -> doc lai file -> sua -> ghi -> nha khoa. Khoa dat tren file rieng
# (su_dung.json.khoa) vi file du lieu bi thay the bang os.replace moi lan ghi.

try:
    import msvcrt

    def _gianh_khoa(fd: int) -> bool:
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    def _nha_khoa(fd: int):
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass

except ImportError:     # khong phai Windows (chay thu tren Linux / macOS)
    import fcntl

    def _gianh_khoa(fd: int) -> bool:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def _nha_khoa(fd: int):
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass


@contextlib.contextmanager
def khoa_file(duong_dan: str, giay_cho: float = GIAY_CHO_KHOA):
    """
    Gianh khoa doc quyen cho <duong_dan> (khoa nam o <duong_dan>.khoa). Cho toi da
    giay_cho giay; van khong gianh duoc thi cu chay tiep - hong mot lan ghi con hon
    treo app. Tra ve True neu dang giu khoa that.
    """
    try:
        thu_muc = os.path.dirname(duong_dan)
        if thu_muc:
            os.makedirs(thu_muc, exist_ok=True)
        fd = os.open(duong_dan + ".khoa", os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as e:
        log.debug("Khong mo duoc file khoa cua %s: %s", duong_dan, e)
        yield False
        return
    het_han = time.monotonic() + max(0.0, giay_cho)
    duoc = _gianh_khoa(fd)
    while not duoc and time.monotonic() < het_han:
        time.sleep(0.02)
        duoc = _gianh_khoa(fd)
    if not duoc:
        log.debug("Cho khoa %s qua %.0f giay ma khong duoc, ghi luon.", duong_dan, giay_cho)
    try:
        yield duoc
    finally:
        if duoc:
            _nha_khoa(fd)
        os.close(fd)


# --------------------------------------------------------------------------
#  GIO MY - THAI BINH DUONG
# --------------------------------------------------------------------------

def _chu_nhat_thu(nam: int, thang: int, thu: int) -> date:
    dau_thang = date(nam, thang, 1)
    return dau_thang + timedelta(days=(6 - dau_thang.weekday()) % 7 + 7 * (thu - 1))


def lech_pacific(utc: datetime) -> timedelta:
    """
    Do lech so voi UTC cua gio My - Thai Binh Duong tai thoi diem utc (naive, UTC).
    Gio mua he (PDT, -7) tu 2h Chu nhat thu hai thang 3 den 2h Chu nhat dau thang 11,
    con lai PST (-8). Tu tinh de khong can goi tzdata (Python embeddable tren Windows khong co).
    """
    bat_dau = datetime.combine(_chu_nhat_thu(utc.year, 3, 2), gio_trong_ngay(10))    # 2h PST
    ket_thuc = datetime.combine(_chu_nhat_thu(utc.year, 11, 1), gio_trong_ngay(9))   # 2h PDT
    return timedelta(hours=-7) if bat_dau <= utc < ket_thuc else timedelta(hours=-8)


def _utc(epoch: float) -> datetime:
    return datetime.fromtimestamp(epoch, timezone.utc).replace(tzinfo=None)


def ngay_pacific(epoch: float) -> str:
    utc = _utc(epoch)
    return (utc + lech_pacific(utc)).date().isoformat()


def luc_dat_lai_ngay(epoch: float) -> float:
    """Epoch cua 0h (gio Pacific) ngay ke tiep: luc Google tinh lai han muc theo ngay."""
    utc = _utc(epoch)
    nua_dem = datetime.combine((utc + lech_pacific(utc)).date() + timedelta(days=1), gio_trong_ngay(0))
    for gio in (7, 8):
        u = nua_dem + timedelta(hours=gio)
        if u + lech_pacific(u) == nua_dem:
            return u.replace(tzinfo=timezone.utc).timestamp()
    return (nua_dem + timedelta(hours=8)).replace(tzinfo=timezone.utc).timestamp()


def gio_may(epoch: float, bay_gio: float | None = None) -> str:
    """'14:00' neu cung ngay (gio may), khong thi '18/09 14:00'."""
    luc = datetime.fromtimestamp(epoch)
    hom_nay = datetime.fromtimestamp(bay_gio if bay_gio is not None else time.time()).date()
    return luc.strftime("%H:%M") if luc.date() == hom_nay else luc.strftime("%d/%m %H:%M")


def dem_nguoc(giay: float) -> str:
    giay = max(0, int(round(giay)))
    return f"{giay // 3600}:{giay % 3600 // 60:02d}:{giay % 60:02d}"


# --------------------------------------------------------------------------
#  HAN MUC
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class HanMuc:
    tpm: int = 0     # token dau vao moi phut
    rpm: int = 0     # yeu cau moi phut
    rpd: int = 0     # yeu cau moi ngay


def _model_moi() -> dict:
    return {
        "yeu_cau_hom_nay": 0, "token_hom_nay": 0, "yeu_cau_tong": 0, "token_tong": 0,
        "lan_dung_cuoi": None, "khoa_den": None, "khoa_vinh_vien": False, "ly_do_khoa": "",
        "chi_tiet_khoa": "", "luc_khoa": None, "loi_cuoi": "", "loai_loi_cuoi": "", "luc_loi_cuoi": None,
        "dem_loi": {}, "hoc_duoc": {}, "cac_lan_khoa_phut": [],
    }


def _chuan_hoa(du_lieu, ngay: str) -> dict:
    """Do du lieu doc tu file ve dung khuon: thieu truong nao thi them mac dinh."""
    if not isinstance(du_lieu, dict):
        du_lieu = {}
    du_lieu.setdefault("ngay", ngay)
    if not isinstance(du_lieu.get("model"), dict):
        du_lieu["model"] = {}
    if not isinstance(du_lieu.get("su_kien"), list):
        du_lieu["su_kien"] = []
    for ten, m in list(du_lieu["model"].items()):
        if not isinstance(m, dict):
            du_lieu["model"][ten] = _model_moi()
            continue
        for k, v in _model_moi().items():
            m.setdefault(k, v)
    return du_lieu


def doc_file(duong_dan: str, ngay: str) -> dict:
    """Doc su_dung.json; file khong co hay hong thi tra ve so trang."""
    try:
        with open(duong_dan, "r", encoding="utf-8") as f:
            return _chuan_hoa(json.load(f), ngay)
    except (OSError, ValueError):
        return _chuan_hoa(None, ngay)


def ghi_file(duong_dan: str, du_lieu: dict) -> bool:
    """Ghi ra file .tmp roi os.replace, de khong bao gio co su_dung.json ghi dang do."""
    try:
        thu_muc = os.path.dirname(duong_dan)
        if thu_muc:
            os.makedirs(thu_muc, exist_ok=True)
        tmp = "%s.%d.tmp" % (duong_dan, os.getpid())
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(du_lieu, f, ensure_ascii=False, indent=1)
        os.replace(tmp, duong_dan)
        return True
    except OSError as e:
        log.debug("Khong ghi duoc %s: %s", duong_dan, e)
        return False


class SoTheoDoi:
    SO_SU_KIEN_TOI_DA = 300

    def __init__(self, duong_dan: str | None = None, dong_ho=time.time):
        """duong_dan None = chi giu trong bo nho (test, hoac chay khong can luu)."""
        self.duong_dan = duong_dan
        self.dong_ho = dong_ho
        self._khoa = threading.RLock()
        self._khoa_giao_dich = threading.Lock()  # xep hang cac luong CUA APP NAY truoc khoa file
        self._chu_giao_dich: int | None = None   # luong dang o trong giao dich (de biet la long nhau)
        self.phien_ban = 0
        self._dang_cho: dict | None = None
        self._sau_giao_dich = 0                  # dang o trong may lop giao dich
        self._can_ghi = False
        self._van_tay: tuple | None = None       # (mtime, co) cua file luc doc lan cuoi
        self._du_lieu = self._nap()

    # ------------------------------------------------------------ luu tru

    def _van_tay_file(self) -> tuple:
        """(mtime, co) cua su_dung.json, (0, -1) neu chua co file. Re hon mo file ~700 lan."""
        try:
            tt = os.stat(self.duong_dan)
        except OSError:
            return (0, -1)
        return (tt.st_mtime_ns, tt.st_size)

    def _nap(self) -> dict:
        ngay = ngay_pacific(self.dong_ho())
        if not self.duong_dan:
            return _chuan_hoa(None, ngay)
        # Lay van tay TRUOC khi doc: app kia ghi xen vao giua thi van tay con la cua
        # ban cu, lan sau doc lai. Doc thua mot lan khong sao, bo sot moi sai.
        self._van_tay = self._van_tay_file()
        return doc_file(self.duong_dan, ngay)

    def _nap_lai(self, bat_buoc: bool = False) -> bool:
        """
        Doc lai file (app kia co the vua ghi), tra ve True neu noi dung khac truoc.

        Duong DOC (giao dien hoi moi giay): so van tay truoc, giong thi khong mo file.
        Mot lan mo file ton ~7ms vi Windows Defender quet, ma moi trang lai hoi vai lan
        moi giay. Van tay co the trung du noi dung da doi, nen file vua ghi xong trong
        GIAY_VAN_TAY_CHUA_CHAC giay thi van doc that -- tuc la luc app kia dang lam viec
        thi ben nay thay ngay, con luc ca hai deu ranh thi khong mo file lan nao.
        Duong GHI (_giao_dich) luon bat_buoc: doc that duoi khoa file truoc khi sua,
        nen so dem cua hai app khong bao gio de len nhau.
        """
        if not self.duong_dan:
            return False
        if not bat_buoc and self._van_tay is not None:
            van_tay = self._van_tay_file()
            if van_tay == self._van_tay and time.time() - van_tay[0] / 1e9 > GIAY_VAN_TAY_CHUA_CHAC:
                return False
        cu = self._du_lieu
        self._du_lieu = self._nap()
        if self._du_lieu == cu:
            return False
        self.phien_ban += 1
        return True

    def _luu(self):
        if self.duong_dan and ghi_file(self.duong_dan, self._du_lieu):
            self._van_tay = self._van_tay_file()   # vua ghi xong: khoi doc lai chinh minh

    @contextlib.contextmanager
    def _giao_dich(self):
        """
        Mot lan sua: gianh khoa file -> doc lai (app kia co the vua ghi) -> sua ->
        ghi -> nha khoa. Long nhau duoc: chi lop ngoai cung gianh khoa va ghi file.

        Thu tu gianh khoa LUON la _khoa_giao_dich -> khoa file -> _khoa, va luc CHO
        khoa file (toi 5 giay neu app kia dang ghi) thi KHONG giu _khoa: neu khong,
        luong giao dien goi dau_hieu() moi giay se dung hinh suot 5 giay do. Vi vay
        _dong_bo() cung phai nha _khoa truoc khi mo giao dich, khong thi khoa cheo.
        """
        if not self.duong_dan or self._chu_giao_dich == threading.get_ident():
            # Long nhau (cung mot luong) hoac chi giu trong bo nho: khong dung khoa file.
            with self._khoa:
                self._sau_giao_dich += 1
                try:
                    yield
                finally:
                    self._sau_giao_dich -= 1
            return
        with self._khoa_giao_dich:              # chan cac luong khac cua app nay
            with khoa_file(self.duong_dan):     # chan app kia; luong doc van chay binh thuong
                with self._khoa:
                    self._nap_lai(bat_buoc=True)
                    self._sau_giao_dich = 1
                    self._chu_giao_dich = threading.get_ident()
                    try:
                        yield
                    finally:
                        self._chu_giao_dich = None
                        self._sau_giao_dich = 0
                        if self._can_ghi:
                            self._can_ghi = False
                            self._luu()

    def _can_cap_nhat(self) -> bool:
        """Co viec cho _cap_nhat khong (hoi truoc de khoi mo giao dich vo ich)."""
        bay_gio = self.dong_ho()
        if self._du_lieu.get("ngay") != ngay_pacific(bay_gio):
            return True
        return any(m.get("khoa_den") and not m.get("khoa_vinh_vien") and m["khoa_den"] <= bay_gio
                   for m in self._du_lieu["model"].values())

    def _dong_bo(self):
        """
        Dau moi lan doc: app kia vua ghi thi doc lai; sang ngay moi hay het khoa thi
        cap nhat (viec cap nhat co ghi file nen phai mo mot giao dich).

        Mo giao dich SAU khi da nha _khoa: thu tu gianh khoa phai la _khoa_giao_dich
        truoc, _khoa sau (xem _giao_dich). Vi vay cac ham doc goi _dong_bo() truoc roi
        moi "with self._khoa", chu khong goi trong luc dang giu _khoa.
        """
        with self._khoa:
            self._nap_lai()
            can_cap_nhat = self._can_cap_nhat()
        if can_cap_nhat:
            with self._giao_dich():
                self._cap_nhat()

    def _da_doi(self):
        self.phien_ban += 1
        if self._sau_giao_dich:
            self._can_ghi = True     # het giao dich moi ghi, luc do van con giu khoa file
        else:
            self._luu()              # phong khi co cho sua ngoai giao dich

    def _model(self, ten: str) -> dict:
        return self._du_lieu["model"].setdefault(ten, _model_moi())

    def _them_su_kien(self, model: str | None, loai: str, noi_dung: str, **them):
        self._du_lieu["su_kien"].append({"luc": round(self.dong_ho(), 1), "model": model or "", "loai": loai,
                                         "noi_dung": noi_dung, **them})
        del self._du_lieu["su_kien"][:-self.SO_SU_KIEN_TOI_DA]

    def _cap_nhat(self) -> bool:
        """Sang ngay moi thi dat lai bo dem; khoa het han thi mo. Tra ve True neu co thay doi."""
        bay_gio = self.dong_ho()
        doi = False
        ngay = ngay_pacific(bay_gio)
        if self._du_lieu.get("ngay") != ngay:
            self._du_lieu["ngay"] = ngay
            for m in self._du_lieu["model"].values():
                m["yeu_cau_hom_nay"] = m["token_hom_nay"] = 0
            doi = True
        for ten, m in self._du_lieu["model"].items():
            if m.get("khoa_den") and not m.get("khoa_vinh_vien") and m["khoa_den"] <= bay_gio:
                self._them_su_kien(ten, SK_HET_KHOA, m.get("ly_do_khoa") or "")
                self._bo_khoa(m)
                doi = True
        if doi:
            self._da_doi()
        return doi

    @staticmethod
    def _bo_khoa(m: dict):
        m.update(khoa_den=None, khoa_vinh_vien=False, ly_do_khoa="", chi_tiet_khoa="", luc_khoa=None)

    # ------------------------------------------------------------ ghi

    def ghi_yeu_cau(self, model: str, so_token: int = 0):
        with self._giao_dich():
            self._cap_nhat()
            m = self._model(model)
            m["yeu_cau_hom_nay"] += 1
            m["yeu_cau_tong"] += 1
            m["token_hom_nay"] += max(0, int(so_token or 0))
            m["token_tong"] += max(0, int(so_token or 0))
            m["lan_dung_cuoi"] = round(self.dong_ho(), 1)
            self._da_doi()

    def ghi_loi(self, model: str, loai: str, thong_bao: str):
        with self._giao_dich():
            m = self._model(model)
            m["dem_loi"][loai] = int(m["dem_loi"].get(loai, 0)) + 1
            m.update(loi_cuoi=str(thong_bao)[:500], loai_loi_cuoi=loai, luc_loi_cuoi=round(self.dong_ho(), 1))
            self._them_su_kien(model, SK_LOI, str(thong_bao)[:300], loai_loi=loai)
            self._da_doi()

    def hoc_han_muc(self, model: str, truong: str, gia_tri: int):
        """Nho han muc Google bao trong loi 429 (vd rpd = 25)."""
        if truong not in CAC_TRUONG_HAN_MUC or not gia_tri or gia_tri <= 0:
            return
        with self._giao_dich():
            m = self._model(model)
            if m["hoc_duoc"].get(truong) == int(gia_tri):
                return
            m["hoc_duoc"][truong] = int(gia_tri)
            self._them_su_kien(model, SK_HOC_HAN_MUC, f"{truong} = {int(gia_tri)}")
            log.info("   Google bao han muc cua %s: %s = %d. Da ghi nho.", model, truong, int(gia_tri))
            self._da_doi()

    def quen_han_muc(self, model: str | None = None):
        with self._giao_dich():
            for ten, m in self._du_lieu["model"].items():
                if model is None or ten == model:
                    m["hoc_duoc"] = {}
            self._da_doi()

    def khoa(self, model: str, den: float | None, ly_do: str, chi_tiet: str = ""):
        """den None = khoa cho toi khi bam Mo khoa (vd model khong ton tai)."""
        with self._giao_dich():
            bay_gio = self.dong_ho()
            m = self._model(model)
            if den is not None and m.get("khoa_den") and not m.get("khoa_vinh_vien") and m["khoa_den"] > den \
                    and m.get("ly_do_khoa") in (KHOA_HAN_MUC_NGAY, KHOA_CHAM_HAN_MUC):
                return  # dang khoa theo ngay thi khong rut ngan
            m.update(khoa_den=round(den, 1) if den is not None else None, khoa_vinh_vien=den is None,
                     ly_do_khoa=ly_do, chi_tiet_khoa=str(chi_tiet)[:500], luc_khoa=round(bay_gio, 1))
            if ly_do == KHOA_HAN_MUC_PHUT:
                m["cac_lan_khoa_phut"] = [t for t in m["cac_lan_khoa_phut"] if bay_gio - t < 3600] + [round(bay_gio, 1)]
            den_txt = gio_may(den, bay_gio) if den is not None else "khi mo tay"
            self._them_su_kien(model, SK_KHOA, str(chi_tiet)[:300], ly_do=ly_do, den=m["khoa_den"])
            log.warning("   Khoa model %s toi %s (%s).", model, den_txt, ly_do)
            self._da_doi()

    def mo_khoa(self, model: str):
        with self._giao_dich():
            m = self._model(model)
            if not m.get("khoa_den") and not m.get("khoa_vinh_vien"):
                return
            self._bo_khoa(m)
            m["cac_lan_khoa_phut"] = []
            self._them_su_kien(model, SK_MO_KHOA, "")
            log.info("Da mo khoa model %s.", model)
            self._da_doi()

    def ghi_doi_model(self, tu_model: str, sang_model: str, ly_do: str):
        with self._giao_dich():
            self._them_su_kien(sang_model, SK_DOI_MODEL, ly_do, tu_model=tu_model)
            self._da_doi()

    def dat_dang_cho(self, model: str | None, ly_do: str, den: float, chi_tiet: str = ""):
        with self._khoa:
            self._dang_cho = {"model": model or "", "ly_do": ly_do, "den": den, "chi_tiet": chi_tiet,
                              "tu": self.dong_ho()}
            self.phien_ban += 1

    def xoa_dang_cho(self):
        with self._khoa:
            if self._dang_cho is not None:
                self._dang_cho = None
                self.phien_ban += 1

    def dat_lai_bo_dem(self, model: str | None = None):
        with self._giao_dich():
            for ten, m in self._du_lieu["model"].items():
                if model is None or ten == model:
                    m["yeu_cau_hom_nay"] = m["token_hom_nay"] = 0
            self._da_doi()

    def xoa_lich_su(self):
        with self._giao_dich():
            self._du_lieu["su_kien"] = []
            self._da_doi()

    # ------------------------------------------------------------ doc
    # Moi ham doc: _dong_bo() TRUOC, roi moi "with self._khoa" (xem _dong_bo).

    @staticmethod
    def _dang_khoa(m: dict | None) -> bool:
        return bool(m and (m.get("khoa_den") or m.get("khoa_vinh_vien")))

    def trang_thai_khoa(self, model: str) -> tuple[bool, float | None, str, str]:
        """(dang khoa, khoa den (None = den khi mo tay), ly do, chi tiet)."""
        self._dong_bo()
        with self._khoa:
            m = self._du_lieu["model"].get(model)
            if not self._dang_khoa(m):
                return False, None, "", ""
            return True, m.get("khoa_den"), m.get("ly_do_khoa") or "", m.get("chi_tiet_khoa") or ""

    def bi_khoa(self, model: str) -> bool:
        return self.trang_thai_khoa(model)[0]

    def yeu_cau_hom_nay(self, model: str) -> int:
        self._dong_bo()
        with self._khoa:
            m = self._du_lieu["model"].get(model)
            return int(m["yeu_cau_hom_nay"]) if m else 0

    def so_lan_khoa_phut_gan_day(self, model: str, trong_giay: float = 900) -> int:
        self._dong_bo()
        with self._khoa:
            m = self._du_lieu["model"].get(model)
            bay_gio = self.dong_ho()
            return sum(1 for t in (m or {}).get("cac_lan_khoa_phut", []) if bay_gio - t < trong_giay)

    def hoc_duoc(self, model: str) -> dict:
        self._dong_bo()
        with self._khoa:
            m = self._du_lieu["model"].get(model)
            return dict(m["hoc_duoc"]) if m else {}

    def gioi_han(self, ch, model: str) -> HanMuc:
        """
        Han muc dung de gian nhip / khoa truoc: so khai bao trong [HAN_MUC] (> 0), khong thi so
        Google da bao, khong nua thi model chua khai bao dung gioi_han_token_moi_phut cho token/phut.
        """
        khai_bao = ch.han_muc_model.get(model)
        hoc = self.hoc_duoc(model)
        gia_tri = []
        for i, truong in enumerate(CAC_TRUONG_HAN_MUC):
            so = int(khai_bao[i]) if khai_bao else 0
            if so <= 0:
                so = int(hoc.get(truong) or 0)
            if so <= 0 and not khai_bao and truong == "tpm":
                so = int(ch.gioi_han_token_moi_phut or 0)
            gia_tri.append(max(0, so))
        return HanMuc(*gia_tri)

    def cac_model(self) -> list[str]:
        self._dong_bo()
        with self._khoa:
            return list(self._du_lieu["model"])

    def anh_chup(self) -> dict:
        """Ban sao de giao dien ve: {'ngay', 'model': {...}, 'su_kien': [...], 'dang_cho': {...} | None}."""
        self._dong_bo()
        with self._khoa:
            kq = copy.deepcopy(self._du_lieu)
            kq["dang_cho"] = copy.deepcopy(self._dang_cho)
            return kq

    def dau_hieu(self) -> tuple:
        """Doi khi co gi can ve lai (ke ca khi khoa tu het han)."""
        self._dong_bo()
        with self._khoa:
            # Doc thang trong _du_lieu, khong goi bi_khoa() tung model: moi lan goi la
            # mot lan _dong_bo() nua, ma ham nay chay moi giay.
            return self.phien_ban, tuple(sorted(t for t, m in self._du_lieu["model"].items()
                                                if self._dang_khoa(m)))


# --------------------------------------------------------------------------
#  GOP FILE CU VAO FILE CHUNG (mot lan, luc app khoi dong)
# --------------------------------------------------------------------------

def _moi_hon(x, y):
    """Cai nao xay ra sau thi thang (None = chua tung)."""
    return max(x or 0, y or 0) or None


def gop(a: dict, b: dict) -> dict:
    """
    Gop hai so theo doi lam mot: cong don so dem, giu khoa moi nhat, tron lich su.
    Dung khi chuyen su_dung.json cu cua tung app vao file dung chung.
    """
    ngay_a, ngay_b = a.get("ngay") or "", b.get("ngay") or ""
    ngay = max(ngay_a, ngay_b)          # "YYYY-MM-DD" so sanh chuoi la dung thu tu
    kq = {"ngay": ngay, "model": {}, "su_kien": []}
    for ten in sorted(set(a["model"]) | set(b["model"])):
        ma = a["model"].get(ten) or _model_moi()
        mb = b["model"].get(ten) or _model_moi()
        m = _model_moi()
        m["yeu_cau_tong"] = int(ma["yeu_cau_tong"]) + int(mb["yeu_cau_tong"])
        m["token_tong"] = int(ma["token_tong"]) + int(mb["token_tong"])
        # So trong ngay chi cong khi ben do van con dung ngay hom nay; ben cu hon
        # coi nhu da qua luc Google dat lai han muc.
        for truong in ("yeu_cau_hom_nay", "token_hom_nay"):
            m[truong] = (int(ma[truong]) if ngay_a == ngay else 0) + \
                        (int(mb[truong]) if ngay_b == ngay else 0)
        m["lan_dung_cuoi"] = _moi_hon(ma["lan_dung_cuoi"], mb["lan_dung_cuoi"])
        # Khoa: ben nao dang khoa thi giu khoa do (ca hai cung khoa thi lay lan khoa
        # sau). Giu nham mot khoa chi mat cong bam Mo khoa, bo nham thi dot han muc.
        moi = ma if (ma["luc_khoa"] or 0) >= (mb["luc_khoa"] or 0) else mb
        for truong in ("khoa_den", "khoa_vinh_vien", "ly_do_khoa", "chi_tiet_khoa", "luc_khoa"):
            m[truong] = moi[truong]
        moi_loi = ma if (ma["luc_loi_cuoi"] or 0) >= (mb["luc_loi_cuoi"] or 0) else mb
        for truong in ("loi_cuoi", "loai_loi_cuoi", "luc_loi_cuoi"):
            m[truong] = moi_loi[truong]
        m["dem_loi"] = {k: int(ma["dem_loi"].get(k, 0)) + int(mb["dem_loi"].get(k, 0))
                        for k in sorted(set(ma["dem_loi"]) | set(mb["dem_loi"]))}
        m["hoc_duoc"] = {**ma["hoc_duoc"], **mb["hoc_duoc"]}
        m["cac_lan_khoa_phut"] = sorted(set(ma["cac_lan_khoa_phut"]) | set(mb["cac_lan_khoa_phut"]))[-50:]
        kq["model"][ten] = m
    su_kien = sorted(a["su_kien"] + b["su_kien"], key=lambda sk: sk.get("luc") or 0)
    kq["su_kien"] = su_kien[-SoTheoDoi.SO_SU_KIEN_TOI_DA:]
    return kq


def gop_file_cu(file_chung: str | None = None, dong_ho=time.time) -> list[str]:
    """
    Gop su_dung.json cu (moi app mot noi, hoi chua co thu muc dung chung) vao file
    chung, roi doi ten file cu thanh su_dung.json.da_gop de lan sau khong gop lai.
    Tra ve danh sach file cu da gop.
    """
    from duong_dan_chung import FILE_SU_DUNG, cac_file_su_dung_cu
    file_chung = file_chung or FILE_SU_DUNG
    cac_cu = [p for p in cac_file_su_dung_cu()
              if os.path.normcase(p) != os.path.normcase(file_chung)]
    if not cac_cu:
        return []
    ngay = ngay_pacific(dong_ho())
    da_gop = []
    with khoa_file(file_chung):
        chung = doc_file(file_chung, ngay)
        for p in cac_cu:
            chung = gop(chung, doc_file(p, ngay))
            da_gop.append(p)
        if not ghi_file(file_chung, chung):
            return []
        for p in da_gop:
            try:
                os.replace(p, p + DUOI_DA_GOP)
            except OSError as e:
                log.debug("Khong doi ten duoc %s: %s", p, e)
    log.info("Da gop %d file su_dung.json cu vao %s.", len(da_gop), file_chung)
    return da_gop


_SO_CHUNG: SoTheoDoi | None = None
_KHOA_TAO = threading.Lock()


def so_theo_doi() -> SoTheoDoi:
    """So dung chung cua Guzz, GoogleAITranscribe va Header, trong thu muc dung chung."""
    global _SO_CHUNG
    with _KHOA_TAO:
        if _SO_CHUNG is None:
            from duong_dan_chung import FILE_SU_DUNG
            gop_file_cu(FILE_SU_DUNG)
            _SO_CHUNG = SoTheoDoi(FILE_SU_DUNG)
        return _SO_CHUNG
