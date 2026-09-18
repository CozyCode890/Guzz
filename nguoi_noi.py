"""
nguoi_noi.py
Moi thu lien quan toi "ai noi doan nao", chi dung thu vien chuan (chay bang Python
cua app, khong can torch).

Ba cach nhan dien (CauHinh.nn_cach), dung chung cac khoi o day:

    pyannote : luot noi cua pyannote (ca buoi) -> lam muot, gop, dat ten
               -> cat theo tung doan audio -> ban do van ban gui kem cho Google
               -> ban go chu co ten nguoi noi -> doc_doan_van_prompt()
    gemini   : tu (word_info) co nhan spk_1, spk_2... cua model *-transcribe
               -> dat ten TRONG TUNG DOAN -> gop thanh doan van
    ket_hop  : tu co moc thoi gian cua model *-transcribe + luot noi pyannote
               -> gan_nguoi_noi -> lam_muot -> dat ten -> gop thanh doan van

Thuat toan gan / lam muot / gop lay tu C:\\LecturerCleaner\\ghep_nguoi_noi.py
(do tren buoi Data Mining 84 phut: 68 luot nham -> 0), doi ten tham so thanh
tuy chon trong config. Rieng cach pyannote lam muot ngay tren cac luot noi truoc
khi gui, vi luc do chua co tu nao de gan.

Moi moc thoi gian o day tinh tren audio DA LAM SACH (da cat khoang lang); chi
luc in ra moi doi ve moc file goc qua BanDoThoiGian (xu_ly_am_thanh.py).
"""

from __future__ import annotations

import bisect
import json
import re
from collections import defaultdict
from dataclasses import dataclass

KHONG_RO = "?"


@dataclass
class LuotNoi:
    bat_dau: float
    ket_thuc: float
    nguoi_noi: str


@dataclass
class Cau:
    """Mot tu (hoac mot nhom tu da gop) co moc thoi gian."""
    bat_dau: float
    ket_thuc: float
    noi_dung: str
    nguoi_noi: str | None = None
    xem_lai: bool = False


@dataclass
class DoanVan:
    """Mot doan van trong ban go chu cuoi cung. moc: giay tren file GOC, hoac None."""
    noi_dung: str
    nguoi_noi: str | None = None
    moc: float | None = None
    xem_lai: bool = False


# --------------------------------------------------------------------------
#  LUOT NOI (ket qua pyannote)
# --------------------------------------------------------------------------

def doc_luot_noi(duong_dan_json: str) -> list[LuotNoi]:
    with open(duong_dan_json, "r", encoding="utf-8") as f:
        du_lieu = json.load(f)
    ds = [LuotNoi(float(d["bat_dau"]), float(d["ket_thuc"]), str(d["nguoi_noi"]))
          for d in du_lieu.get("doan") or []]
    ds.sort(key=lambda l: l.bat_dau)
    return ds


def doi_moc(ds: list[LuotNoi], ham) -> list[LuotNoi]:
    """Doi moc moi luot qua ham (vd BanDoThoiGian.sang_sach). Luot bi cat mat het thi bo."""
    kq = []
    for l in ds:
        a, b = ham(l.bat_dau), ham(l.ket_thuc)
        if b - a > 1e-3:
            kq.append(LuotNoi(a, b, l.nguoi_noi))
    return kq


def nguoi_noi_chinh(ds: list) -> str | None:
    """Nguoi noi lau nhat. `ds` la list[LuotNoi] (nen dung) hoac list[Cau]."""
    thoi_gian = defaultdict(float)
    for x in ds:
        if x.nguoi_noi is not None:
            thoi_gian[x.nguoi_noi] += x.ket_thuc - x.bat_dau
    return max(thoi_gian, key=thoi_gian.get) if thoi_gian else None


def _cac_khoi(ds: list) -> list[tuple[int, int]]:
    """Chia ds thanh cac khoang [dau, cuoi] lien tiep cung nguoi noi."""
    ket_qua = []
    i = 0
    while i < len(ds):
        j = i
        while j + 1 < len(ds) and ds[j + 1].nguoi_noi == ds[i].nguoi_noi:
            j += 1
        ket_qua.append((i, j))
        i = j + 1
    return ket_qua


def _quy_tac_kep(ds: list, kep_toi_da: float, kep_nghi: float) -> int:
    """
    Quy tac 1: khoi ngan (< kep_toi_da) kep giua CUNG mot nguoi, hai ben nghi
    khong qua kep_nghi -> tra ve nguoi do. Lap den khi khong con khoi kep nao.
    """
    so_doi = 0
    co_doi = True
    while co_doi:
        co_doi = False
        khoi = _cac_khoi(ds)
        k = 1
        while k < len(khoi) - 1:
            (a, b), (_, pb), (na, _) = khoi[k], khoi[k - 1], khoi[k + 1]
            truoc, sau = ds[pb], ds[na]
            if (truoc.nguoi_noi == sau.nguoi_noi
                    and ds[b].ket_thuc - ds[a].bat_dau < kep_toi_da
                    and ds[a].bat_dau - truoc.ket_thuc <= kep_nghi
                    and sau.bat_dau - ds[b].ket_thuc <= kep_nghi):
                for x in range(a, b + 1):
                    ds[x].nguoi_noi = truoc.nguoi_noi
                so_doi += b - a + 1
                co_doi = True
                k += 2  # khoi ke tiep da nhap vao khoi truoc, tinh lai o vong sau
            else:
                k += 1
    return so_doi


def _quy_tac_mat_do(ds: list, ds_luot: list[LuotNoi], cua_so: float, toi_thieu: float) -> int:
    """
    Quy tac 2: phan tu cua nguoi phu ma trong +-cua_so, pyannote nghe nhung nguoi
    phu noi tong cong < toi_thieu -> tra ve nguoi noi chinh. Do bang thoi gian
    noi cua pyannote (ds_luot goc), KHONG bang thoi luong cac tu da go.
    """
    chinh = nguoi_noi_chinh(ds_luot)
    if chinh is None:
        return 0
    luot_phu = [l for l in ds_luot if l.nguoi_noi != chinh]  # da sap theo bat_dau
    bat_daus = [l.bat_dau for l in luot_phu]
    cong_don = [0.0]
    for l in luot_phu:
        cong_don.append(cong_don[-1] + l.ket_thuc - l.bat_dau)
    can_doi = []
    for c in ds:
        if c.nguoi_noi is None or c.nguoi_noi == chinh:
            continue
        lo = bisect.bisect_left(bat_daus, c.bat_dau - cua_so)
        hi = bisect.bisect_right(bat_daus, c.ket_thuc + cua_so)
        if cong_don[hi] - cong_don[lo] < toi_thieu:
            can_doi.append(c)
    for c in can_doi:
        c.nguoi_noi = chinh
        if hasattr(c, "xem_lai"):
            c.xem_lai = False
    return len(can_doi)


def lam_muot(ds: list, ds_luot: list[LuotNoi], kep_toi_da: float = 3.0, kep_nghi: float = 1.0,
             cua_so: float = 60.0, toi_thieu: float = 15.0, theo_nguoi_chinh: bool = True) -> int:
    """
    Sua nhan nguoi noi goc (truoc khi dat ten) theo hai quy tac. `ds` la list[Cau]
    (cach ket_hop) hoac chinh list[LuotNoi] (cach pyannote, luc do ds_luot la ban
    sao cua luot goc). Quy tac 2 chi chay khi theo_nguoi_chinh. Tra ve so phan tu da doi.
    """
    so_doi = _quy_tac_kep(ds, kep_toi_da, kep_nghi)
    if theo_nguoi_chinh and toi_thieu > 0:
        so_doi += _quy_tac_mat_do(ds, ds_luot, cua_so, toi_thieu)
    return so_doi


def gop_luot(ds: list[LuotNoi], khoang_nghi: float) -> list[LuotNoi]:
    """Gop hai luot lien nhau cua cung mot nguoi cach nhau khong qua khoang_nghi giay."""
    kq: list[LuotNoi] = []
    for l in ds:
        if kq and kq[-1].nguoi_noi == l.nguoi_noi and l.bat_dau - kq[-1].ket_thuc <= khoang_nghi:
            kq[-1].ket_thuc = max(kq[-1].ket_thuc, l.ket_thuc)
        else:
            kq.append(LuotNoi(l.bat_dau, l.ket_thuc, l.nguoi_noi))
    return kq


def xu_ly_luot_noi(ds_goc: list[LuotNoi], ch) -> tuple[list[LuotNoi], int]:
    """Cach pyannote: lam muot (neu bat) roi gop luot. Tra ve (luot moi, so luot da doi nhan)."""
    ds = [LuotNoi(l.bat_dau, l.ket_thuc, l.nguoi_noi) for l in ds_goc]
    so_doi = 0
    if ch.nn_lam_muot:
        so_doi = lam_muot(ds, ds_goc, ch.nn_kep_toi_da_giay, ch.nn_kep_nghi_giay,
                          ch.nn_mat_do_cua_so_giay, ch.nn_mat_do_toi_thieu_giay,
                          theo_nguoi_chinh=ch.nn_dat_ten_nguoi_chinh)
    return gop_luot(ds, ch.nn_gop_luot_giay), so_doi


# --------------------------------------------------------------------------
#  DAT TEN
# --------------------------------------------------------------------------

def bang_ten(ds: list, ch, chinh: str | None = None) -> dict[str, str]:
    """
    Nhan goc (SPEAKER_00, spk_1...) -> ten de doc. `chinh` (nguoi noi lau nhat
    theo pyannote) la ten_nguoi_chinh; khong truyen thi tinh tren chinh ds.
    Nhung nguoi con lai danh so theo thu tu xuat hien.
    """
    thu_tu = []
    for x in sorted(ds, key=lambda x: x.bat_dau):
        if x.nguoi_noi is not None and x.nguoi_noi not in thu_tu:
            thu_tu.append(x.nguoi_noi)
    bang = {}
    if ch.nn_dat_ten_nguoi_chinh and thu_tu:
        if chinh not in thu_tu:
            chinh = nguoi_noi_chinh(ds)
        bang[chinh] = ch.nn_ten_nguoi_chinh
        for i, n in enumerate((n for n in thu_tu if n != chinh), 1):
            bang[n] = f"{ch.nn_ten_nguoi_khac} {i}"
    else:
        for i, n in enumerate(thu_tu, 1):
            bang[n] = f"{ch.nn_ten_chung} {i}"
    return bang


def phut_theo_nguoi(ds: list, bang: dict[str, str]) -> dict[str, float]:
    thoi_gian = defaultdict(float)
    for x in ds:
        thoi_gian[bang.get(x.nguoi_noi, KHONG_RO)] += x.ket_thuc - x.bat_dau
    return {k: round(v / 60, 1) for k, v in sorted(thoi_gian.items(), key=lambda kv: kv[1], reverse=True)}


# --------------------------------------------------------------------------
#  BAN DO NGUOI NOI GUI CHO GOOGLE (cach pyannote)
# --------------------------------------------------------------------------

def cat_theo_doan(ds: list[LuotNoi], bat_dau: float, ket_thuc: float,
                  toi_thieu: float = 0.3) -> list[LuotNoi]:
    """
    Cac luot nam trong [bat_dau, ket_thuc), moc tinh lai tu dau doan. Bo manh ngan
    hon toi_thieu giay: in ra "01:21.0 - 01:21.0" chi lam model roi them.
    """
    kq = []
    for l in ds:
        a, b = max(l.bat_dau, bat_dau), min(l.ket_thuc, ket_thuc)
        if b - a >= toi_thieu:
            kq.append(LuotNoi(round(a - bat_dau, 2), round(b - bat_dau, 2), l.nguoi_noi))
    return kq


def _mm_ss(giay: float) -> str:
    giay = max(0.0, giay)
    return f"{int(giay // 60):02d}:{giay % 60:04.1f}"


def ban_do_van_ban(ds_doan: list[LuotNoi], bang: dict[str, str]) -> str:
    """Noi dung file ban do gui cho Google (tieng Anh, ten nguoi noi giu nguyen)."""
    dong = ["SPEAKER MAP",
            "Times are mm:ss.s measured from the start of this audio clip.",
            ""]
    if not ds_doan:
        dong.append("(the diarization tool found no speech in this clip)")
    for l in ds_doan:
        dong.append(f"{_mm_ss(l.bat_dau)} - {_mm_ss(l.ket_thuc)}  {bang.get(l.nguoi_noi, KHONG_RO)}")
    return "\n".join(dong) + "\n"


def ten_trong_doan(ds_doan: list[LuotNoi], bang: dict[str, str]) -> list[str]:
    """Ten cac nguoi noi xuat hien trong doan, nguoi noi lau nhat truoc."""
    return list(phut_theo_nguoi(ds_doan, bang).keys()) if ds_doan else []


# --------------------------------------------------------------------------
#  DOC BAN GO CHU CUA MODEL DA NANG (cach pyannote)
# --------------------------------------------------------------------------

_MOC_DAU_DONG = re.compile(r"^\s*[\[(]\s*(?:(\d{1,2}):)?(\d{1,3}):(\d{2})(?:[.,]\d+)?\s*[\])]\s*")


def _tach_ten(dong: str, cac_ten: dict[str, str]) -> tuple[str | None, str]:
    """'**Giảng viên:** abc' -> ('Giảng viên', 'abc') neu ten nam trong cac_ten (khoa viet thuong)."""
    m = re.match(r"^\s*\**\s*([^:\n]{1,40}?)\s*\**\s*:\s*\**\s*", dong)
    if m:
        ten = cac_ten.get(m.group(1).strip().strip("*").strip().lower())
        if ten:
            return ten, dong[m.end():].strip()
    return None, dong.strip()


def doc_doan_van_prompt(van_ban: str, cac_ten: list[str], bat_dau_doan: float,
                        sang_goc) -> list[DoanVan]:
    """
    Tach ban go chu co ten nguoi noi thanh cac DoanVan, moi dong khong rong la mot
    doan. Moc "[mm:ss]" dau dong (tinh tu dau doan audio) doi thanh moc file goc:
    sang_goc(bat_dau_doan + moc). Dong khong ghi ten thi thuoc nguoi noi dong
    truoc; dong chi co "Ten:" thi ten (va moc) ap cho dong ke tiep.
    Chi nhan ten nam trong cac_ten, de "Ví dụ: ..." khong bi coi la nguoi noi.
    """
    tra_cuu = {t.lower(): t for t in cac_ten}
    kq: list[DoanVan] = []
    nguoi = None
    moc_cho = None
    for dong in van_ban.splitlines():
        if not dong.strip():
            continue
        moc = None
        m = _MOC_DAU_DONG.match(dong)
        if m:
            giay = int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            moc = sang_goc(bat_dau_doan + giay)
            dong = dong[m.end():]
        ten, noi_dung = _tach_ten(dong, tra_cuu)
        if ten is not None:
            nguoi = ten
        if moc is None:
            moc = moc_cho
        moc_cho = None
        if not noi_dung:
            moc_cho = moc
            continue
        kq.append(DoanVan(noi_dung, nguoi, moc))
    return kq


# --------------------------------------------------------------------------
#  TU CO MOC THOI GIAN (cach gemini va ket_hop)
# --------------------------------------------------------------------------

def tu_sang_cau(tu: list[dict], bu_moc: float = 0.0) -> list[Cau]:
    """word_info (google_ai.trich_tu) -> Cau, cong them bu_moc (moc dau doan tren audio da cat)."""
    return [Cau(t["bat_dau"] + bu_moc, t["ket_thuc"] + bu_moc, t["tu"], t.get("nguoi_noi"))
            for t in tu]


def gan_nguoi_noi(ds_cau: list[Cau], ds_luot: list[LuotNoi], khoang_gan: float = 1.0,
                  nguong_xem_lai: float = 0.4, xem_lai_toi_thieu: float = 1.5) -> list[Cau]:
    """
    Moi cau (tu) thuoc ve nguoi noi co THOI GIAN TRUNG nhieu nhat voi no. Khong
    trung ai thi lay luot gan nhat trong khoang_gan giay, van khong co thi None.
    Cau dai tu xem_lai_toi_thieu giay ma nguoi thu hai chiem >= nguong_xem_lai
    duoc danh dau xem_lai. Sua truc tiep va tra lai ds_cau.
    """
    # Luot noi "exclusive" cua pyannote khong chong lan, nen ket_thuc cung tang dan.
    ket_thucs = [l.ket_thuc for l in ds_luot]
    for c in ds_cau:
        trung = defaultdict(float)
        i = bisect.bisect_right(ket_thucs, c.bat_dau)
        j = i
        while j < len(ds_luot) and ds_luot[j].bat_dau < c.ket_thuc:
            l = ds_luot[j]
            do_trung = min(c.ket_thuc, l.ket_thuc) - max(c.bat_dau, l.bat_dau)
            if do_trung > 0:
                trung[l.nguoi_noi] += do_trung
            j += 1

        if trung:
            xep = sorted(trung.items(), key=lambda kv: kv[1], reverse=True)
            c.nguoi_noi = xep[0][0]
            do_dai = max(c.ket_thuc - c.bat_dau, 1e-6)
            c.xem_lai = (len(xep) > 1 and do_dai >= xem_lai_toi_thieu
                         and xep[1][1] / do_dai >= nguong_xem_lai)
            continue

        gan_nhat, khoang_cach = None, khoang_gan
        for k in (i - 1, i):
            if 0 <= k < len(ds_luot):
                l = ds_luot[k]
                kc = max(l.bat_dau - c.ket_thuc, c.bat_dau - l.ket_thuc, 0.0)
                if kc <= khoang_cach:
                    gan_nhat, khoang_cach = l.nguoi_noi, kc
        c.nguoi_noi = gan_nhat
    return ds_cau


_KHOANG_TRANG_TRUOC_DAU = re.compile(r"\s+([,.;:!?%…)\]}])")
_KHOANG_TRANG_SAU_MO = re.compile(r"([(\[{])\s+")


def noi_tu(a: str, b: str) -> str:
    s = f"{a} {b}" if a else b
    return _KHOANG_TRANG_SAU_MO.sub(r"\1", _KHOANG_TRANG_TRUOC_DAU.sub(r"\1", s))


def gop_cau(ds_cau: list[Cau], toi_da_giay: float = 60.0, khoang_lang_giay: float = 3.0) -> list[Cau]:
    """Gop cac cau (tu) lien nhau cua cung mot nguoi thanh mot doan."""
    ket_qua: list[Cau] = []
    for c in ds_cau:
        truoc = ket_qua[-1] if ket_qua else None
        if (truoc is not None
                and truoc.nguoi_noi == c.nguoi_noi
                and c.bat_dau - truoc.ket_thuc <= khoang_lang_giay
                and (toi_da_giay <= 0 or c.ket_thuc - truoc.bat_dau <= toi_da_giay)):
            truoc.ket_thuc = max(truoc.ket_thuc, c.ket_thuc)
            truoc.noi_dung = noi_tu(truoc.noi_dung, c.noi_dung)
            truoc.xem_lai = truoc.xem_lai or c.xem_lai
        else:
            ket_qua.append(Cau(c.bat_dau, c.ket_thuc, noi_tu("", c.noi_dung), c.nguoi_noi, c.xem_lai))
    return ket_qua


def doi_ten(ds: list, bang: dict[str, str]):
    for x in ds:
        x.nguoi_noi = bang.get(x.nguoi_noi, KHONG_RO) if x.nguoi_noi is not None else KHONG_RO


def cau_sang_doan_van(ds_cau: list[Cau], sang_goc) -> list[DoanVan]:
    return [DoanVan(c.noi_dung, c.nguoi_noi, sang_goc(c.bat_dau), c.xem_lai) for c in ds_cau]


# --------------------------------------------------------------------------
#  IN RA
# --------------------------------------------------------------------------

def hh_mm_ss(giay: float) -> str:
    giay = int(max(0.0, giay))
    return f"{giay // 3600:02d}:{giay % 3600 // 60:02d}:{giay % 60:02d}"


# Cap ngoac rong o dau mau thi bo ca khoang trang phia sau, o giua thi bo khoang trang phia truoc.
_NGOAC_RONG = re.compile(r"^\s*[\[(<{]\s*[\])>}]\s*|\s*[\[(<{]\s*[\])>}]")


def hien_thi_doan(d: DoanVan, mau: str, co_moc: bool, danh_dau_xem_lai: bool) -> str:
    moc = hh_mm_ss(d.moc) if co_moc and d.moc is not None else ""
    noi_dung = ("[?] " if danh_dau_xem_lai and d.xem_lai else "") + d.noi_dung
    if not d.nguoi_noi:
        return f"[{moc}] {noi_dung}" if moc else noi_dung
    s = mau.format(moc=moc, nguoi=d.nguoi_noi, noi_dung=noi_dung)
    if not moc:
        s = _NGOAC_RONG.sub("", s, count=1)
    return s.strip()
