"""
google_ai.py
Goi Google AI Studio (Gemini API) bang REST, chi dung thu vien chuan (urllib).
Lay tu GoogleAITranscribe, them:
  - gui kem mot file van ban (ban do nguoi noi) canh file audio;
  - model *-transcribe: che do tu tach nguoi noi (diarization_mode) va moc thoi
    gian tung tu (timestamp_granularities), doc ket qua tu cac annotation word_info.

Moi doan audio di qua 3 buoc:
    (1) Files API        : POST /upload/v1beta/files (resumable: start roi upload, finalize)
    (2) Interactions API : POST /v1beta/interactions voi audio (+ file kem) vua tai len
    (3) Files API        : DELETE /v1beta/files/... (neu bat xoa_file_tren_server)

Hai kieu model:
    *-transcribe (vd gemini-3.5-transcribe): chi nhan audio + transcription_config
        (che do smart/verbatim, ma ngon ngu, tu vung, tach nguoi noi, moc tung tu).
        Khong nhan prompt, khong nhan file kem. Tach nguoi noi / moc tung tu bat
        buoc verbatim va khong dung duoc tu vung (Google tra 400).
    model da nang (vd gemini-3.8-flash): gui prompt + audio (+ file van ban).

Phan loai loi (LoiGoogleAI.loai):
    LOI_TAM_THOI : mang, 408                   -> thu lai, het so lan thi bao file loi
    LOI_QUA_TAI  : 5xx (high demand...)        -> thu lai, roi doi model du phong (chuyen_doi.py)
    LOI_HAN_MUC  : 429 RESOURCE_EXHAUSTED      -> han muc phut: cho roi thu lai; han muc ngay: khong
                                                  thu lai, khoa model toi luc Google tinh lai, doi model
    LOI_BI_CHAN  : 400 "Input blocked" (bo loc) -> doi model du phong cho rieng doan do
    LOI_MODEL    : 404 model khong ton tai      -> khoa model, doi model du phong
    LOI_CAU_HINH : 400/401/403 khac            -> API key hay tham so sai; dung ca hang doi
    LOI_KHAC     : model bao that bai...       -> file loi

API key KHONG nam trong config.txt. Thu tu tim:
    1. %LOCALAPPDATA%\\Guzz\\api_key.txt (trang Google AI cua app ghi vao day)
    2. bien moi truong GEMINI_API_KEY, roi GOOGLE_API_KEY
    3. key da luu boi GoogleAITranscribe (%LOCALAPPDATA%\\GoogleAITranscribe\\api_key.txt)
"""

from __future__ import annotations

import http.client
import json
import logging
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

log = logging.getLogger("Guzz")

API_GOC = "https://generativelanguage.googleapis.com"
PHIEN_BAN = "v1beta"

LOI_TAM_THOI = "tam_thoi"
LOI_QUA_TAI = "qua_tai"
LOI_HAN_MUC = "han_muc"
LOI_BI_CHAN = "bi_chan"
LOI_MODEL = "model"
LOI_CAU_HINH = "cau_hinh"
LOI_KHAC = "khac"

# Loi rieng cua mot model: con model du phong thi doi sang model khac thay vi bao file loi.
CAC_LOI_DOI_MODEL = (LOI_QUA_TAI, LOI_HAN_MUC, LOI_BI_CHAN, LOI_MODEL)

BIEN_MOI_TRUONG = ("GEMINI_API_KEY", "GOOGLE_API_KEY")

_MIME = {
    ".flac": "audio/flac",
    ".wav": "audio/wav",
    ".mp3": "audio/mp3",
    ".ogg": "audio/ogg",
    ".m4a": "audio/m4a",
    ".aac": "audio/aac",
    ".txt": "text/plain",
    ".json": "application/json",
}

_CHO_TOI_DA_GIUA_HAI_LAN_THU = 300


@dataclass
class ViPhamHanMuc:
    """Mot dong "Quota exceeded for metric: ..., limit: 25, model: ..." trong loi 429."""
    metric: str = ""
    gioi_han: int = 0
    model: str = ""
    quota_id: str = ""

    @property
    def la_token(self) -> bool:
        return "token" in (self.metric + " " + self.quota_id).lower()

    @property
    def theo(self) -> str:
        """'ngay' / 'phut' neu Google noi ro (quotaId ...PerDay... / ...PerMinute...), khong thi ''."""
        s = (self.quota_id + " " + self.metric).lower()
        if "perday" in s or "per_day" in s:
            return "ngay"
        if "perminute" in s or "per_minute" in s:
            return "phut"
        return ""


class LoiGoogleAI(Exception):
    def __init__(self, thong_bao: str, loai: str = LOI_KHAC, ma_http: int | None = None,
                 cho_giay: float = 0.0, vi_pham: list[ViPhamHanMuc] | None = None,
                 dung_hang_doi: bool | None = None):
        super().__init__(thong_bao)
        self.loai = loai
        self.ma_http = ma_http
        self.cho_giay = cho_giay
        self.vi_pham = list(vi_pham or [])
        # Loi 429 het han muc trong ngay (MayKhach doan ra): thu lai vo ich.
        self.theo_ngay = False
        # True = loi se lap lai o moi file (key sai, moi model deu khoa lau): dung ca hang doi.
        self.dung_hang_doi = loai == LOI_CAU_HINH if dung_hang_doi is None else dung_hang_doi

    @property
    def thu_lai_duoc(self) -> bool:
        return self.loai in (LOI_TAM_THOI, LOI_QUA_TAI) or (self.loai == LOI_HAN_MUC and not self.theo_ngay)


class DaDung(Exception):
    """Nguoi dung bam Dung giua chung. Khong phai loi."""


# --------------------------------------------------------------------------
#  API KEY
# --------------------------------------------------------------------------

def _thu_muc_ho_so(ten_app: str) -> str:
    goc = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(goc, ten_app)


def duong_dan_file_api_key() -> str:
    return os.path.join(_thu_muc_ho_so("Guzz"), "api_key.txt")


def duong_dan_key_google_ai_transcribe() -> str:
    return os.path.join(_thu_muc_ho_so("GoogleAITranscribe"), "api_key.txt")


def _doc_file_key(p: str) -> str | None:
    try:
        with open(p, "r", encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def nguon_api_key() -> tuple[str | None, str | None]:
    """Tra ve (api_key, noi tim thay) hoac (None, None)."""
    p = duong_dan_file_api_key()
    key = _doc_file_key(p)
    if key:
        return key, p
    for bien in BIEN_MOI_TRUONG:
        key = (os.environ.get(bien) or "").strip()
        if key:
            return key, bien
    p = duong_dan_key_google_ai_transcribe()
    key = _doc_file_key(p)
    if key:
        return key, p
    return None, None


def lay_api_key() -> str | None:
    return nguon_api_key()[0]


def luu_api_key(key: str):
    """Ghi key vao file rieng trong ho so nguoi dung. Key rong = xoa file."""
    p = duong_dan_file_api_key()
    key = (key or "").strip()
    if not key:
        try:
            os.remove(p)
        except OSError:
            pass
        return
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(key)
    os.replace(tmp, p)


def che_api_key(key: str | None) -> str:
    if not key:
        return ""
    return key[:4] + "…" + key[-4:] if len(key) > 10 else "…"


# --------------------------------------------------------------------------
#  TIEN ICH
# --------------------------------------------------------------------------

def doan_mime(duong_dan: str) -> str:
    return _MIME.get(os.path.splitext(duong_dan)[1].lower(), "application/octet-stream")


def la_model_go_chu(model: str) -> bool:
    return "transcribe" in (model or "").lower()


def ngu(so_giay: float, nen_dung=None):
    """Ngu tung giay mot de nut Dung co tac dung ngay ca khi dang cho thu lai."""
    het = time.monotonic() + max(0.0, so_giay)
    while True:
        if nen_dung is not None and nen_dung():
            raise DaDung()
        con = het - time.monotonic()
        if con <= 0:
            return
        time.sleep(min(1.0, con))


def _giay(chuoi) -> float:
    """'30s', '1.5s', 30, {"seconds": 1, "nanos": 5e8} -> so giay."""
    if isinstance(chuoi, dict):
        try:
            return float(chuoi.get("seconds") or 0) + float(chuoi.get("nanos") or 0) / 1e9
        except (TypeError, ValueError):
            return 0.0
    try:
        return float(re.sub(r"[^0-9.]", "", str(chuoi)) or 0)
    except ValueError:
        return 0.0


def _json(than: bytes) -> dict:
    try:
        du_lieu = json.loads(than.decode("utf-8") or "{}")
    except (UnicodeDecodeError, ValueError):
        raise LoiGoogleAI("Google AI tra ve du lieu khong phai JSON: "
                          + than[:200].decode("utf-8", "replace"), LOI_TAM_THOI) from None
    return du_lieu if isinstance(du_lieu, dict) else {}


_VI_PHAM_TRONG_MESSAGE = re.compile(
    r"Quota exceeded for metric:\s*([^\s,]+)\s*,\s*limit:\s*(\d+)(?:\s*,\s*model:\s*([^\s,]+))?", re.IGNORECASE)
_TU_BI_CHAN = ("blocked", "prohibited_content", "blocklist")


def doc_vi_pham(thong_bao: str, cac_chi_tiet: list) -> list[ViPhamHanMuc]:
    """Cac han muc bi vuot: tu QuotaFailure trong details, khong co thi doc trong message."""
    kq = []
    for chi_tiet in cac_chi_tiet or []:
        if not isinstance(chi_tiet, dict):
            continue
        for v in chi_tiet.get("violations") or []:
            if not isinstance(v, dict) or not (v.get("quotaMetric") or v.get("quotaId")):
                continue
            chieu = v.get("quotaDimensions") if isinstance(v.get("quotaDimensions"), dict) else {}
            try:
                gioi_han = int(float(v.get("quotaValue") or 0))
            except (TypeError, ValueError):
                gioi_han = 0
            kq.append(ViPhamHanMuc(str(v.get("quotaMetric") or ""), gioi_han, str(chieu.get("model") or ""),
                                   str(v.get("quotaId") or "")))
    if not kq:
        for m in _VI_PHAM_TRONG_MESSAGE.finditer(thong_bao or ""):
            kq.append(ViPhamHanMuc(m.group(1), int(m.group(2)), (m.group(3) or "").rstrip(".")))
    return kq


def loi_tu_http(ma: int, than: bytes, headers=None) -> LoiGoogleAI:
    """Dich mot phan hoi HTTP loi thanh LoiGoogleAI, kem thoi gian nen cho (neu Google bao)."""
    thong_bao, trang_thai, cho, cac_chi_tiet = "", "", 0.0, []
    try:
        du_lieu = json.loads((than or b"").decode("utf-8", "replace") or "{}")
        loi = du_lieu.get("error", du_lieu) if isinstance(du_lieu, dict) else {}
        if not isinstance(loi, dict):
            loi = {"message": str(loi)}
        thong_bao = str(loi.get("message") or "")
        trang_thai = str(loi.get("status") or "")
        cac_chi_tiet = loi.get("details") if isinstance(loi.get("details"), list) else []
        for chi_tiet in cac_chi_tiet:
            if not isinstance(chi_tiet, dict):
                continue
            if chi_tiet.get("retryDelay"):
                cho = max(cho, _giay(chi_tiet["retryDelay"]))
            if chi_tiet.get("reason"):
                trang_thai = f"{trang_thai} {chi_tiet['reason']}".strip()
    except ValueError:
        thong_bao = (than or b"")[:300].decode("utf-8", "replace")
    if headers is not None and headers.get("Retry-After"):
        cho = max(cho, _giay(headers.get("Retry-After")))
    # Loi 429 cua Interactions API khong co RetryInfo trong details, chi ghi
    # "Please retry in 17.099322891s." trong message.
    m = re.search(r"retry in\s+([\d.]+)\s*s", thong_bao, re.IGNORECASE)
    if m:
        cho = max(cho, _giay(m.group(1)))

    mo_ta = f"HTTP {ma}" + (f" {trang_thai}" if trang_thai else "") + (f": {thong_bao}" if thong_bao else "")
    vi_pham = []
    chu = f"{trang_thai} {thong_bao}".lower()
    if ma == 429:
        loai = LOI_HAN_MUC
        vi_pham = doc_vi_pham(thong_bao, cac_chi_tiet)
    elif ma >= 500:
        loai = LOI_QUA_TAI
    elif ma == 408:
        loai = LOI_TAM_THOI
    elif ma == 400 and any(t in chu for t in _TU_BI_CHAN):
        # Loi that 2026-09-17 voi gemini-3.8-flash: "Input blocked: This request was blocked by
        # Gemini's filters..." Chi rieng yeu cau do bi chan, model van dung duoc.
        loai = LOI_BI_CHAN
    elif ma == 404 and "model" in chu:
        loai = LOI_MODEL
    elif ma in (400, 401, 403, 404):
        loai = LOI_CAU_HINH
    else:
        loai = LOI_KHAC
    return LoiGoogleAI(mo_ta, loai, ma, cho, vi_pham)


def _cac_noi_dung_model(tra_ve: dict):
    for buoc in tra_ve.get("steps") or []:
        if not isinstance(buoc, dict) or buoc.get("type") != "model_output":
            continue
        for noi_dung in buoc.get("content") or []:
            if isinstance(noi_dung, dict) and noi_dung.get("type") == "text":
                yield noi_dung


def trich_van_ban(tra_ve: dict) -> str:
    """Lay chu tu mot Interaction: cac noi dung text trong buoc model_output."""
    if isinstance(tra_ve.get("output_text"), str):
        return tra_ve["output_text"]
    return "".join(nd["text"] for nd in _cac_noi_dung_model(tra_ve) if nd.get("text"))


def trich_tu(tra_ve: dict) -> list[dict]:
    """
    Cac tu co moc thoi gian (annotation type word_info) cua model *-transcribe:
        [{"tu", "nguoi_noi" (hoac None), "bat_dau", "ket_thuc"}, ...] theo thu tu noi.
    Moc tinh bang giay tu dau doan audio gui len.
    """
    tu = []
    for nd in _cac_noi_dung_model(tra_ve):
        for ghi_chu in nd.get("annotations") or []:
            if not isinstance(ghi_chu, dict) or ghi_chu.get("type") != "word_info":
                continue
            chu = str(ghi_chu.get("text") or "").strip()
            if not chu:
                continue
            bat_dau = _giay(ghi_chu.get("start_offset"))
            ket_thuc = max(bat_dau, _giay(ghi_chu.get("end_offset")))
            tu.append({"tu": chu, "nguoi_noi": ghi_chu.get("speaker") or None,
                       "bat_dau": round(bat_dau, 3), "ket_thuc": round(ket_thuc, 3)})
    return tu


def kiem_tra_trang_thai(tra_ve: dict) -> dict:
    """Nem LoiGoogleAI neu Interaction khong xong. 'incomplete' ma co chu thi van nhan."""
    trang_thai = str(tra_ve.get("status") or "completed").lower()
    if trang_thai == "completed":
        return tra_ve

    chi_tiet = "; ".join(
        str(e.get("message") or e.get("code") or e) if isinstance(e, dict) else str(e)
        for e in tra_ve.get("errors") or []
    )
    if trang_thai == "incomplete" and trich_van_ban(tra_ve).strip():
        log.warning("   Google AI tra ve ket qua chua tron ven (status incomplete%s). "
                    "Van giu phan da co.", f": {chi_tiet}" if chi_tiet else "")
        return tra_ve
    if trang_thai in ("in_progress", "queued"):
        loai = LOI_TAM_THOI
    elif any(t in f"{trang_thai} {chi_tiet}".lower() for t in _TU_BI_CHAN):
        loai = LOI_BI_CHAN
    else:
        loai = LOI_KHAC
    raise LoiGoogleAI(f"Google AI bao viec go chu '{trang_thai}'"
                      + (f": {chi_tiet}" if chi_tiet else ""), loai)


def doc_ket_qua(tra_ve: dict) -> str:
    return trich_van_ban(kiem_tra_trang_thai(tra_ve))


def tao_yeu_cau(ch, file_uri: str, mime: str, prompt: str | None = None, *,
                model: str | None = None, tach_nguoi_noi: bool = False, moc_tung_tu: bool = False,
                tai_lieu: tuple[str, str] | None = None, van_ban_kem: str | None = None) -> dict:
    """
    ch: CauHinh (cau_hinh.py), chi doc cac truong cua muc [GOOGLE_AI].
    model: mac dinh ch.model. tai_lieu: (uri, mime) cua file van ban tai len kem.
    van_ban_kem: chen vao cuoi prompt (thay cho tai_lieu).
    tach_nguoi_noi / moc_tung_tu: chi co nghia voi model *-transcribe.
    """
    model = model or ch.model
    am_thanh = {"type": "audio", "uri": file_uri, "mime_type": mime}
    yeu_cau = {"model": model}
    if la_model_go_chu(model):
        che_do = {"type": ch.che_do_go_chu or "smart"}
        co_moc = tach_nguoi_noi or moc_tung_tu
        if co_moc:
            # Google: smart khong di cung diarization / timestamps.
            che_do["type"] = "verbatim"
            if tach_nguoi_noi:
                che_do["diarization_mode"] = "speaker"
            che_do["timestamp_granularities"] = ["word"]
        cau_hinh_go_chu = {"mode": che_do}
        if ch.ngon_ngu:
            cau_hinh_go_chu["language_codes"] = list(ch.ngon_ngu)
        # Google: custom_vocabulary khong di cung diarization / timestamps.
        if ch.tu_vung and not co_moc:
            cau_hinh_go_chu["custom_vocabulary"] = list(ch.tu_vung)
        yeu_cau["input"] = [am_thanh]
        yeu_cau["generation_config"] = {"transcription_config": cau_hinh_go_chu}
    else:
        noi_dung = (prompt or "Transcribe this audio.").strip()
        if ch.ngon_ngu:
            noi_dung += f"\nSpoken language(s): {', '.join(ch.ngon_ngu)}."
        if ch.tu_vung:
            noi_dung += f"\nTerms that may appear: {', '.join(ch.tu_vung)}."
        if van_ban_kem:
            noi_dung += "\n\nSPEAKER MAP:\n" + van_ban_kem.strip()
        yeu_cau["input"] = [{"type": "text", "text": noi_dung}, am_thanh]
        if tai_lieu:
            yeu_cau["input"].append({"type": "document", "uri": tai_lieu[0], "mime_type": tai_lieu[1]})
    if not ch.luu_tren_server:
        yeu_cau["store"] = False
    return yeu_cau


def doc_so_token_dau_vao(tra_ve: dict) -> int:
    """So token dau vao Google tinh cho mot Interaction, 0 neu phan hoi khong co."""
    usage = tra_ve.get("usage") or tra_ve.get("usageMetadata") or {}
    for truong in ("total_input_tokens", "input_tokens", "promptTokenCount"):
        try:
            so = int(usage.get(truong) or 0)
        except (TypeError, ValueError):
            so = 0
        if so > 0:
            return so
    return 0


# --------------------------------------------------------------------------
#  DIEU TIET (han muc token / yeu cau moi phut, rieng tung model)
# --------------------------------------------------------------------------

class DieuTiet:
    """
    Giu nhip gui de khong vuot han muc token dau vao va so yeu cau MOI PHUT cua mot model
    (goi mien phi cua gemini-3.5-transcribe: 10000 token/phut).

    Cach lam: nho (luc gui, so token) cua cac lan gui trong 60 giay qua. So token
    lay tu "usage" trong phan hoi, va suy ra so token moi giay audio de uoc luong
    doan sau. Chua biet (doan dau, hoac phan hoi khong co usage) thi coi nhu lan
    gui do da dung het han muc ca phut, tuc la hai lan gui cach nhau >= 60 giay:
    cham hon mot chut nhung khong bao gio dinh 429.

    Moi model mot DieuTiet (dieu_tiet_cua_model), dung chung cho ca tien trinh: Google
    tinh han muc theo API key va theo model, nen doi sang model du phong thi khong phai
    cho han muc cua model cu.
    """

    CUA_SO_GIAY = 60.0
    DU_PHONG_GIAY = 1.0

    def __init__(self, dong_ho=time.monotonic):
        self.dong_ho = dong_ho
        self._khoa = threading.Lock()
        self._lich_su: list[tuple[float, int]] = []
        self.token_moi_giay_audio: float | None = None

    def _con_trong_cua_so(self, bay_gio: float) -> list[tuple[float, int]]:
        self._lich_su = [(t, n) for t, n in self._lich_su if bay_gio - t < self.CUA_SO_GIAY]
        return self._lich_su

    def da_dung(self) -> int:
        with self._khoa:
            return sum(n for _, n in self._con_trong_cua_so(self.dong_ho()))

    def so_yeu_cau(self) -> int:
        """So yeu cau da gui trong 60 giay qua (ke ca yeu cau bi loi)."""
        with self._khoa:
            return len(self._con_trong_cua_so(self.dong_ho()))

    def uoc_luong(self, so_giay_audio: float | None, gioi_han: int) -> int:
        if self.token_moi_giay_audio and so_giay_audio:
            # Them 10% phong khi doan nay nhieu tieng noi hon doan truoc.
            return int(self.token_moi_giay_audio * so_giay_audio * 1.1)
        return gioi_han

    def thoi_gian_can_cho(self, gioi_han: int, du_kien: int) -> float:
        if gioi_han <= 0:
            return 0.0
        with self._khoa:
            bay_gio = self.dong_ho()
            lich_su = self._con_trong_cua_so(bay_gio)
            # Mot doan to hon ca han muc thi chi can cua so trong la gui (Google van nhan).
            can = sum(n for _, n in lich_su) + min(du_kien, gioi_han) - gioi_han
            if not lich_su or can <= 0:
                return 0.0
            giai_phong = 0
            for t, n in lich_su:
                giai_phong += n
                if giai_phong >= can:
                    return max(0.0, t + self.CUA_SO_GIAY + self.DU_PHONG_GIAY - bay_gio)
            return 0.0

    def thoi_gian_can_cho_yeu_cau(self, gioi_han: int) -> float:
        """Cho bao lau de gui them mot yeu cau ma khong vuot gioi_han yeu cau/phut."""
        if gioi_han <= 0:
            return 0.0
        with self._khoa:
            bay_gio = self.dong_ho()
            lich_su = self._con_trong_cua_so(bay_gio)
            thua = len(lich_su) - gioi_han + 1
            if thua <= 0:
                return 0.0
            return max(0.0, lich_su[thua - 1][0] + self.CUA_SO_GIAY + self.DU_PHONG_GIAY - bay_gio)

    def ghi(self, luc_gui: float, so_token: int, so_giay_audio: float | None = None,
            thuc_te: bool = True):
        with self._khoa:
            self._lich_su.append((luc_gui, int(so_token)))
            self._lich_su.sort()
            if thuc_te and so_token > 0 and so_giay_audio:
                self.token_moi_giay_audio = so_token / so_giay_audio


_DIEU_TIET_THEO_MODEL: dict[str, DieuTiet] = {}
_KHOA_DIEU_TIET = threading.Lock()


def dieu_tiet_cua_model(model: str) -> DieuTiet:
    with _KHOA_DIEU_TIET:
        if model not in _DIEU_TIET_THEO_MODEL:
            _DIEU_TIET_THEO_MODEL[model] = DieuTiet()
        return _DIEU_TIET_THEO_MODEL[model]


# --------------------------------------------------------------------------
#  MAY KHACH
# --------------------------------------------------------------------------

class MayKhach:
    def __init__(self, api_key: str, timeout: float = 600, mo_url=None, dieu_tiet=None, so_theo_doi=None):
        self.api_key = api_key
        self.timeout = timeout
        # Cho phep test thay urlopen bang ham gia.
        self._mo_url = mo_url or urllib.request.urlopen
        # Test truyen mot DieuTiet (dong ho gia) dung cho moi model; binh thuong moi model mot cai.
        self._dieu_tiet = dieu_tiet
        # han_muc.SoTheoDoi: ghi luot dung, loi, han muc Google bao. None = khong ghi.
        self.so_theo_doi = so_theo_doi
        self.so_token_lan_cuoi = 0

    def dieu_tiet_cho(self, model: str) -> DieuTiet:
        return self._dieu_tiet or dieu_tiet_cua_model(model)

    def gioi_han(self, ch, model: str) -> tuple[int, int, int]:
        """(token/phut, yeu cau/phut, yeu cau/ngay) dang ap dung cho model."""
        if self.so_theo_doi is not None:
            h = self.so_theo_doi.gioi_han(ch, model)
            return h.tpm, h.rpm, h.rpd
        return ch.han_muc_cua(model)

    def _goi(self, method: str, url: str, du_lieu: bytes | None = None, headers=None,
             json_body=None, timeout: float | None = None):
        h = {"x-goog-api-key": self.api_key}
        if json_body is not None:
            du_lieu = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        yeu_cau = urllib.request.Request(url, data=du_lieu, headers=h, method=method)
        try:
            with self._mo_url(yeu_cau, timeout=timeout or self.timeout) as phan_hoi:
                return phan_hoi.status, phan_hoi.headers, phan_hoi.read()
        except urllib.error.HTTPError as e:
            try:
                than = e.read()
            except Exception:
                than = b""
            raise loi_tu_http(e.code, than, e.headers) from None
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError,
                http.client.HTTPException) as e:
            ly_do = getattr(e, "reason", None) or e
            raise LoiGoogleAI(f"Khong ket noi duoc toi Google AI: {ly_do}", LOI_TAM_THOI) from None

    # ---------- Files API ----------

    def tai_len(self, duong_dan: str, mime: str | None = None) -> dict:
        mime = mime or doan_mime(duong_dan)
        with open(duong_dan, "rb") as f:
            du_lieu = f.read()

        _, headers, _ = self._goi(
            "POST", f"{API_GOC}/upload/{PHIEN_BAN}/files",
            json_body={"file": {"display_name": os.path.basename(duong_dan)}},
            headers={
                "X-Goog-Upload-Protocol": "resumable",
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": str(len(du_lieu)),
                "X-Goog-Upload-Header-Content-Type": mime,
            },
            timeout=60,
        )
        url_tai_len = headers.get("X-Goog-Upload-URL") if headers is not None else None
        if not url_tai_len:
            raise LoiGoogleAI("Google AI khong tra ve dia chi tai len (X-Goog-Upload-URL).",
                              LOI_TAM_THOI)

        _, _, than = self._goi(
            "POST", url_tai_len, du_lieu=du_lieu,
            headers={
                "Content-Length": str(len(du_lieu)),
                "X-Goog-Upload-Offset": "0",
                "X-Goog-Upload-Command": "upload, finalize",
            },
        )
        file = _json(than).get("file") or {}
        if not file.get("name") or not file.get("uri"):
            raise LoiGoogleAI("Tai len xong nhung Google AI khong tra ve ten/uri cua file.",
                              LOI_TAM_THOI)
        return file

    def cho_file_san_sang(self, file: dict, toi_da_giay: float = 300, nen_dung=None) -> dict:
        het = time.monotonic() + toi_da_giay
        while str(file.get("state") or "ACTIVE").upper() == "PROCESSING":
            if time.monotonic() > het:
                raise LoiGoogleAI(f"File {file.get('name')} van dang xu ly sau "
                                  f"{toi_da_giay:.0f} giay.", LOI_TAM_THOI)
            ngu(2, nen_dung)
            _, _, than = self._goi("GET", f"{API_GOC}/{PHIEN_BAN}/{file['name']}", timeout=60)
            file = _json(than) or file
        if str(file.get("state") or "").upper() == "FAILED":
            raise LoiGoogleAI(f"Google AI khong xu ly duoc file {file.get('name')}.", LOI_KHAC)
        return file

    def xoa_file(self, ten: str):
        try:
            self._goi("DELETE", f"{API_GOC}/{PHIEN_BAN}/{ten}", timeout=60)
        except LoiGoogleAI as e:
            # Khong xoa duoc thi Google cung tu xoa sau 48 gio, khong dang de dung viec.
            log.warning("   Khong xoa duoc %s tren Google AI (%s).", ten, e)

    # ---------- Models ----------

    def liet_ke_model(self) -> list[str]:
        ten, token = [], ""
        while True:
            url = f"{API_GOC}/{PHIEN_BAN}/models?pageSize=1000"
            if token:
                url += "&pageToken=" + urllib.parse.quote(token)
            du_lieu = _json(self._goi("GET", url, timeout=30)[2])
            for m in du_lieu.get("models") or []:
                n = str(m.get("name") or "")
                ten.append(n[len("models/"):] if n.startswith("models/") else n)
            token = du_lieu.get("nextPageToken")
            if not token:
                return [t for t in ten if t]

    # ---------- Han muc ----------

    def thoi_gian_cho_han_muc(self, ch, model: str, so_giay_audio: float | None) -> float:
        """Phai cho bao lau truoc khi gui mot doan cho model (han muc token/phut va yeu cau/phut)."""
        tpm, rpm, _ = self.gioi_han(ch, model)
        dt = self.dieu_tiet_cho(model)
        return max(dt.thoi_gian_can_cho(tpm, dt.uoc_luong(so_giay_audio, tpm)), dt.thoi_gian_can_cho_yeu_cau(rpm))

    def _cho(self, model: str, ly_do: str, giay: float, nen_dung, chi_tiet: str = ""):
        """Ngu, dong thoi bao cho trang Han muc biet dang cho gi, toi luc nao."""
        if self.so_theo_doi is not None:
            self.so_theo_doi.dat_dang_cho(model, ly_do, self.so_theo_doi.dong_ho() + giay, chi_tiet)
        try:
            ngu(giay, nen_dung)
        finally:
            if self.so_theo_doi is not None:
                self.so_theo_doi.xoa_dang_cho()

    def _cho_han_muc(self, ch, model: str, so_giay_audio: float | None, nen_dung):
        tpm, rpm, _ = self.gioi_han(ch, model)
        dt = self.dieu_tiet_cho(model)
        du_kien = dt.uoc_luong(so_giay_audio, tpm)
        cho_token = dt.thoi_gian_can_cho(tpm, du_kien)
        cho_yeu_cau = dt.thoi_gian_can_cho_yeu_cau(rpm)
        if cho_token <= 0 and cho_yeu_cau <= 0:
            return
        if cho_token >= cho_yeu_cau:
            log.info("   Cho %.0f giay cho khoi vuot han muc %d token/phut cua %s (60 giay qua da dung "
                     "%d token, doan nay uoc %s token).", cho_token, tpm, model, dt.da_dung(),
                     du_kien if dt.token_moi_giay_audio else "chua ro")
            self._cho(model, "tpm", cho_token, nen_dung, f"{tpm}")
        else:
            log.info("   Cho %.0f giay cho khoi vuot han muc %d yeu cau/phut cua %s.", cho_yeu_cau, rpm, model)
            self._cho(model, "rpm", cho_yeu_cau, nen_dung, f"{rpm}")

    def _xu_ly_429(self, e: LoiGoogleAI, model: str):
        """Doan loi 429 la het han muc theo ngay hay theo phut; ghi nho han muc Google bao."""
        so_60s = self.dieu_tiet_cho(model).so_yeu_cau()
        for v in e.vi_pham:
            theo = v.theo
            if not theo:
                # "generate_content_free_tier_requests, limit: 25" khong noi phut hay ngay. Trong 60 giay
                # qua gui chua toi 25 yeu cau thi khong the la han muc phut: la han muc ngay (loi that
                # 2026-09-17, app gui moi phut mot doan). Token thi Google gioi han theo phut.
                theo = "phut" if v.la_token or not v.gioi_han or so_60s >= v.gioi_han else "ngay"
            if theo == "ngay":
                e.theo_ngay = True
            if self.so_theo_doi is not None and v.gioi_han > 0:
                truong = ("tpm" if theo == "phut" else "") if v.la_token else ("rpm" if theo == "phut" else "rpd")
                if truong:
                    self.so_theo_doi.hoc_han_muc(v.model or model, truong, v.gioi_han)

    def _ghi_loi(self, model: str, e: LoiGoogleAI):
        if self.so_theo_doi is not None:
            self.so_theo_doi.ghi_loi(model, "han_muc_ngay" if e.theo_ngay else e.loai, str(e))

    # ---------- Go chu ----------

    def _go_chu_mot_lan(self, duong_dan_audio: str, ch, prompt, nen_dung, so_giay_audio,
                        tuy_chon: dict, file_kem: str | None) -> dict:
        model = tuy_chon.get("model") or ch.model
        tpm = self.gioi_han(ch, model)[0]
        dt = self.dieu_tiet_cho(model)
        # Cho TRUOC khi tai len, de file khong nam khong tren Google trong luc cho.
        self._cho_han_muc(ch, model, so_giay_audio, nen_dung)
        da_tai_len = []
        try:
            file = self.tai_len(duong_dan_audio)
            da_tai_len.append(file["name"])
            tai_lieu = None
            if file_kem:
                kem = self.tai_len(file_kem, doan_mime(file_kem))
                da_tai_len.append(kem["name"])
                kem = self.cho_file_san_sang(kem, nen_dung=nen_dung)
                tai_lieu = (kem["uri"], kem.get("mimeType") or kem.get("mime_type") or doan_mime(file_kem))
            file = self.cho_file_san_sang(file, nen_dung=nen_dung)
            if nen_dung is not None and nen_dung():
                raise DaDung()
            mime = file.get("mimeType") or file.get("mime_type") or doan_mime(duong_dan_audio)
            yeu_cau = tao_yeu_cau(ch, file["uri"], mime, prompt, tai_lieu=tai_lieu, **tuy_chon)
            log.debug("   Yeu cau: %s", json.dumps(yeu_cau, ensure_ascii=False)[:2000])
            luc_gui = dt.dong_ho()
            try:
                _, _, than = self._goi("POST", f"{API_GOC}/{PHIEN_BAN}/interactions",
                                       json_body=yeu_cau, timeout=ch.timeout_giay or self.timeout)
            except LoiGoogleAI as e:
                # Yeu cau loi van tinh vao so yeu cau/phut. Bi 429 thi coi ca phut nay la da dung het token.
                dt.ghi(luc_gui, tpm if e.ma_http == 429 else 0, thuc_te=False)
                if e.ma_http == 429:
                    self._xu_ly_429(e, model)
                self._ghi_loi(model, e)
                raise
            tra_ve = _json(than)
            self.so_token_lan_cuoi = doc_so_token_dau_vao(tra_ve)
            dt.ghi(luc_gui, self.so_token_lan_cuoi or tpm, so_giay_audio, thuc_te=self.so_token_lan_cuoi > 0)
            try:
                tra_ve = kiem_tra_trang_thai(tra_ve)
            except LoiGoogleAI as e:
                self._ghi_loi(model, e)
                raise
            if self.so_theo_doi is not None:
                self.so_theo_doi.ghi_yeu_cau(model, self.so_token_lan_cuoi)
            return tra_ve
        finally:
            if ch.xoa_file_tren_server:
                for ten in da_tai_len:
                    self.xoa_file(ten)

    def go_chu_tho(self, duong_dan_audio: str, ch, prompt: str | None = None, nen_dung=None,
                   so_giay_audio: float | None = None, *, model: str | None = None,
                   tach_nguoi_noi: bool = False, moc_tung_tu: bool = False,
                   file_kem: str | None = None, van_ban_kem: str | None = None, so_lan_thu: int = 0) -> dict:
        """
        Gui mot doan audio, tra ve nguyen Interaction (dict) da kiem tra trang thai.
        Truoc khi gui thi cho du han muc token/phut va yeu cau/phut. Loi tam thoi thi thu lai
        toi da ch.so_lan_thu_moi_doan lan, cho dung thoi gian Google yeu cau (hoac lau dan).
        Het han muc trong ngay thi khong thu lai (nem LoiGoogleAI co theo_ngay = True).
        so_lan_thu > 0: loi qua tai / het han muc chi thu chung do lan, vi con model du phong
        de doi (loi mang van thu du so lan).
        file_kem: file van ban tai len canh audio (chi model da nang).
        """
        model = model or ch.model
        tuy_chon = {"model": model, "tach_nguoi_noi": tach_nguoi_noi,
                    "moc_tung_tu": moc_tung_tu, "van_ban_kem": van_ban_kem}
        so_lan = max(1, ch.so_lan_thu_moi_doan)
        so_lan_rieng_model = min(so_lan, so_lan_thu) if so_lan_thu > 0 else so_lan
        self.so_token_lan_cuoi = 0
        lan = 0
        while True:
            lan += 1
            try:
                return self._go_chu_mot_lan(duong_dan_audio, ch, prompt, nen_dung, so_giay_audio,
                                            tuy_chon, file_kem)
            except LoiGoogleAI as e:
                toi_da = so_lan_rieng_model if e.loai in (LOI_QUA_TAI, LOI_HAN_MUC) else so_lan
                if not e.thu_lai_duoc or lan >= toi_da:
                    raise
                # Google noi ro phai cho bao lau thi cho dung chung do (them 2 giay
                # du phong); khong noi thi cho lau dan 15, 30, 60... giay.
                if e.cho_giay > 0:
                    cho = min(_CHO_TOI_DA_GIUA_HAI_LAN_THU, e.cho_giay + 2)
                else:
                    cho = min(_CHO_TOI_DA_GIUA_HAI_LAN_THU, 15 * 2 ** (lan - 1))
                log.warning("   Loi tam thoi voi %s (%s). Thu lai lan %d/%d sau %.0f giay.",
                            model, e, lan + 1, toi_da, cho)
                self._cho(model, "thu_lai", cho, nen_dung, e.loai)

    def go_chu(self, duong_dan_audio: str, ch, prompt: str | None = None, nen_dung=None,
               so_giay_audio: float | None = None, **tuy_chon) -> str:
        """Nhu go_chu_tho nhung chi tra ve chu."""
        return trich_van_ban(self.go_chu_tho(duong_dan_audio, ch, prompt, nen_dung,
                                             so_giay_audio, **tuy_chon))
