#!/usr/bin/env python3
"""
xu_ly_am_thanh.py
Lam sach audio bai giang truoc khi go chu: loc dai tan giong nguoi, giam tieng
on nen, can bang am luong khi giang vien di lai, tang am luong, cat khoang lang.

Lay tu GoogleAITranscribe (ban goc: C:\\LecturerCleaner\\clean_lecture_audio.py).
Khac GoogleAITranscribe: lam_sach() tra them BanDoThoiGian ghi lai cac doan
duoc GIU LAI khi cat khoang lang. Nho do:
  - moc thoi gian trong ban go chu (tinh tren audio da cat) doi nguoc duoc ve
    moc cua file goc, mo file goc ra nghe dung cho;
  - nhan dien nguoi noi chay tren audio goc van ghep duoc voi audio da cat.

Chay tay (PowerShell):
    python xu_ly_am_thanh.py lop_hoc.m4a
    -> lop_hoc_processed.wav
"""

from __future__ import annotations

import argparse
import bisect
import os
import sys

import numpy as np
from scipy.signal import butter, sosfilt

from am_thanh_io import doc_audio, ghi_audio

_BIEN_DO_TOI_DA = 32768.0        # bien do toi da cua mau 16-bit
_KHOI_LOC = 1 << 20              # so mau moi khoi khi loc bandpass (~4MB float32)


def bandpass_filter(y: np.ndarray, sr: int, low=80, high=8000, order=5) -> np.ndarray:
    """
    Giu lai dai tan giong nguoi, cat bot rumble thap va hiss cao.
    Loc theo tung khoi va ghi de tai cho, tranh tao them mot ban float64 ca file.
    """
    nyq = 0.5 * sr
    high = min(high, nyq - 1)
    if low <= 0 or low >= high:
        return y
    sos = butter(order, [low / nyq, high / nyq], btype="band", output="sos")
    zi = np.zeros((sos.shape[0], 2))
    for i in range(0, len(y), _KHOI_LOC):
        doan, zi = sosfilt(sos, y[i:i + _KHOI_LOC], zi=zi)
        y[i:i + _KHOI_LOC] = doan
    return y


def reduce_noise(y: np.ndarray, sr: int, noise_sample_sec=2.0, prop_decrease=0.85) -> np.ndarray:
    """
    Giam tieng on nen bang spectral gating khong dung (non-stationary): san tieng
    on duoc uoc luong lai theo tung doan, hop voi giang duong vi on doi suot buoi.
    noise_sample_sec la time_constant_s cua noisereduce.
    """
    import noisereduce as nr  # import muon: nang, va chi can khi bat khu on

    return nr.reduce_noise(
        y=y, sr=sr, stationary=False,
        time_constant_s=max(0.2, float(noise_sample_sec)),
        prop_decrease=prop_decrease,
    )


def do_dbfs(y: np.ndarray) -> float:
    """dBFS trung binh cua ca doan, cung cach tinh nhu pydub."""
    if y.size == 0:
        return float("-inf")
    rms = float(np.sqrt(np.mean(np.square(y, dtype=np.float64))))
    return 20.0 * float(np.log10(rms)) if rms > 0 else float("-inf")


_KHOI_CAN_BANG_MS = 50           # do phan giai cua duong bao am luong
_TANG_TOI_DA_DB = 12.0           # khong keo doan xa len qua 12 dB (tranh day on len)
_GIAM_TOI_DA_DB = 6.0            # doan sat mic duoc ha toi da 6 dB
_LAM_MUOT_GAIN_SEC = 0.5         # lam muot duong gain cho khoi nghe "bom bup"
_NGUONG_LANG_DUOI_DINH_DB = 25.0 # thap hon doan to nhat qua muc nay = coi la lang


def _trung_binh_truot(x: np.ndarray, cua_so: int) -> np.ndarray:
    """Trung binh truot co can giua, cung do dai voi x (bien thi rut ngan cua so)."""
    if cua_so <= 1 or x.size == 0:
        return x
    cong_don = np.concatenate(([0.0], np.cumsum(x, dtype=np.float64)))
    i = np.arange(x.size)
    dau = np.maximum(0, i - cua_so // 2)
    cuoi = np.minimum(x.size, i + cua_so - cua_so // 2)
    return (cong_don[cuoi] - cong_don[dau]) / (cuoi - dau)


def level_loudness(y: np.ndarray, sr: int, window_sec=3.0) -> np.ndarray:
    """
    Can bang am luong theo thoi gian khi giang vien di lai: do duong bao nang
    luong theo khoi 50ms, lam muot bang cua so window_sec giay, roi dua moi vung
    co tieng noi ve muc chung (toi da +12 / -6 dB). Khoi im lang giu gain cua
    doan noi ben canh de on giua hai cau khong bi day len rieng.
    """
    if window_sec is None or window_sec <= 0:
        return y
    khoi = max(1, int(sr * _KHOI_CAN_BANG_MS / 1000))
    so_khoi = len(y) // khoi
    if so_khoi < 4:
        return y

    nang_luong = np.empty(so_khoi, dtype=np.float64)
    buoc = max(1, _KHOI_LOC // khoi)
    for k in range(0, so_khoi, buoc):
        m = min(so_khoi, k + buoc)
        doan = y[k * khoi:m * khoi].reshape(m - k, khoi)
        nang_luong[k:m] = np.mean(np.square(doan, dtype=np.float32), axis=1)

    bao = _trung_binh_truot(nang_luong, max(1, int(window_sec * 1000 / _KHOI_CAN_BANG_MS)))
    bao_db = 10.0 * np.log10(np.maximum(bao, 1e-12))

    co_tieng = bao_db > np.percentile(bao_db, 95) - _NGUONG_LANG_DUOI_DINH_DB
    if not np.any(co_tieng):
        return y
    muc_chung = np.percentile(bao_db[co_tieng], 75)

    gain_db = np.clip(muc_chung - bao_db, -_GIAM_TOI_DA_DB, _TANG_TOI_DA_DB)
    chi_so = np.arange(so_khoi)
    gain_db = np.interp(chi_so, chi_so[co_tieng], gain_db[co_tieng])
    gain_db = _trung_binh_truot(gain_db, max(1, int(_LAM_MUOT_GAIN_SEC * 1000 / _KHOI_CAN_BANG_MS)))
    gain = (10.0 ** (gain_db / 20.0)).astype(np.float32)

    tam_khoi = (chi_so * khoi + khoi / 2.0).astype(np.float64)
    for i in range(0, len(y), _KHOI_LOC):
        vi_tri = np.arange(i, min(len(y), i + _KHOI_LOC), dtype=np.float64)
        y[i:i + _KHOI_LOC] *= np.interp(vi_tri, tam_khoi, gain).astype(np.float32)
    return y


def boost_and_normalize(y: np.ndarray, target_dBFS=-16.0) -> np.ndarray:
    """Dua am luong tong the ve muc muc tieu, cat nguong ngay de khau do im lang nhin dung tin hieu se ghi ra."""
    hien_tai = do_dbfs(y)
    if hien_tai == float("-inf"):
        return y
    y *= np.float32(10.0 ** ((target_dBFS - hien_tai) / 20.0))
    return np.clip(y, -1.0, 1.0, out=y)


def tim_doan_co_tieng(y: np.ndarray, sr: int, min_silence_len=700,
                      silence_thresh_db=-32.0) -> list:
    """
    Tra ve danh sach [bat_dau_ms, ket_thuc_ms] cua cac doan CO tieng noi.
    Ket qua giong pydub.detect_nonsilent nhung tinh bang mang cong don, O(n).
    """
    do_dai_ms = round(len(y) / sr * 1000)
    W = int(min_silence_len)
    if W <= 0 or do_dai_ms < W:
        return [[0, do_dai_ms]]

    so_ms = int(len(y) / sr * 1000)
    moc = (np.arange(so_ms + 1, dtype=np.int64) * sr) // 1000
    moc[-1] = min(moc[-1], len(y))

    tong_ms = np.add.reduceat(np.square(y, dtype=np.float64), moc[:-1])
    dem_ms = np.diff(moc)
    cong_don_tong = np.concatenate(([0.0], np.cumsum(tong_ms)))
    cong_don_dem = np.concatenate(([0], np.cumsum(dem_ms)))

    n = min(do_dai_ms - W, so_ms - W)
    if n < 0:
        return [[0, do_dai_ms]]

    i = np.arange(n + 1)
    tong_cua_so = cong_don_tong[i + W] - cong_don_tong[i]
    dem_cua_so = cong_don_dem[i + W] - cong_don_dem[i]
    rms = np.floor(np.sqrt(tong_cua_so / np.maximum(dem_cua_so, 1)) * _BIEN_DO_TOI_DA)
    nguong = 10.0 ** (silence_thresh_db / 20.0) * _BIEN_DO_TOI_DA

    im_lang = np.flatnonzero(rms <= nguong)
    if im_lang.size == 0:
        return [[0, do_dai_ms]]

    cat = np.flatnonzero(np.diff(im_lang) > W)
    dau_khoang = np.concatenate(([im_lang[0]], im_lang[cat + 1]))
    cuoi_khoang = np.concatenate((im_lang[cat], [im_lang[-1]])) + W

    if dau_khoang[0] == 0 and cuoi_khoang[0] >= do_dai_ms:
        return []

    co_tieng = []
    truoc = 0
    for a, b in zip(dau_khoang.tolist(), cuoi_khoang.tolist()):
        if a > truoc:
            co_tieng.append([truoc, a])
        truoc = b
    if truoc < do_dai_ms:
        co_tieng.append([truoc, do_dai_ms])
    return co_tieng


class BanDoThoiGian:
    """
    Cac doan [bat_dau, ket_thuc] (giay, tren audio GOC) duoc giu lai sau khi cat
    khoang lang, theo thu tu. Audio da cat la cac doan nay noi lien nhau.
    Khong cat gi thi chi co mot doan [0, thoi_luong].
    """

    def __init__(self, doan: list[tuple[float, float]], thoi_luong_goc: float | None = None):
        self.doan = [(float(a), float(b)) for a, b in doan if b > a]
        self.thoi_luong_goc = thoi_luong_goc if thoi_luong_goc is not None else (
            self.doan[-1][1] if self.doan else 0.0)
        self._dau_sach = []       # moc bat dau cua tung doan tren audio da cat
        tong = 0.0
        for a, b in self.doan:
            self._dau_sach.append(tong)
            tong += b - a
        self.thoi_luong_sach = tong
        self._dau_goc = [a for a, _ in self.doan]

    @classmethod
    def khong_cat(cls, thoi_luong: float) -> "BanDoThoiGian":
        return cls([(0.0, thoi_luong)])

    def sang_goc(self, t: float) -> float:
        """Moc tren audio da cat -> moc tren file goc."""
        if not self.doan:
            return t
        k = max(0, bisect.bisect_right(self._dau_sach, t) - 1)
        a, b = self.doan[k]
        return min(b, a + max(0.0, t - self._dau_sach[k]))

    def sang_sach(self, t: float) -> float:
        """Moc tren file goc -> moc tren audio da cat. Roi vao khoang da cat thi lay dau doan ke tiep."""
        if not self.doan:
            return t
        k = bisect.bisect_right(self._dau_goc, t) - 1
        if k < 0:
            return 0.0
        a, b = self.doan[k]
        if t <= b:
            return self._dau_sach[k] + (t - a)
        return self._dau_sach[k + 1] if k + 1 < len(self.doan) else self.thoi_luong_sach

    def sang_json(self) -> list[list[float]]:
        return [[round(a, 3), round(b, 3)] for a, b in self.doan]


def trim_silence(y: np.ndarray, sr: int, silence_thresh_offset=16,
                 min_silence_len=700, keep_silence=300) -> tuple[np.ndarray, list[list[int]]]:
    """
    Cat cac doan im lang dai, giu keep_silence ms dem hai dau, gop cac doan de len nhau.
    Tra ve (audio da cat, cac doan [a, b] (chi so mau tren y) duoc giu lai).
    """
    ca_file = [[0, len(y)]]
    nguong = do_dbfs(y) - silence_thresh_offset
    khoang = tim_doan_co_tieng(y, sr, min_silence_len, nguong)
    if not khoang:
        return y, ca_file

    mau_moi_ms = sr / 1000.0
    gop = []
    for bat_dau_ms, ket_thuc_ms in khoang:
        a = max(0, int((bat_dau_ms - keep_silence) * mau_moi_ms))
        b = min(len(y), int((ket_thuc_ms + keep_silence) * mau_moi_ms))
        if b <= a:
            continue
        if gop and a <= gop[-1][1]:
            gop[-1][1] = max(gop[-1][1], b)
        else:
            gop.append([a, b])

    if not gop or gop == ca_file:
        return y, ca_file
    return np.concatenate([y[a:b] for a, b in gop]), gop


def lam_sach(
    input_path: str,
    khu_on: bool = True,
    target_dbfs: float = -16.0,
    cat_khoang_lang: bool = True,
    min_silence_len: int = 700,
    silence_thresh_offset: int = 16,
    keep_silence: int = 300,
    noise_sample_sec: float = 2.0,
    resample_hz: int = 16000,
    bandpass_low: int = 80,
    bandpass_high: int = 8000,
    prop_decrease: float = 0.85,
    level_window_sec: float = 0.0,
    progress_callback=None,
) -> tuple[np.ndarray, int, BanDoThoiGian]:
    """
    Doc va lam sach mot file. Tra ve (mang float32 mono [-1, 1], tan so lay mau,
    ban do thoi gian audio da cat -> file goc).
    progress_callback (tuy chon): ham nhan 1 chuoi de bao tien do.
    """
    def report(msg):
        if progress_callback:
            progress_callback(msg)

    sr = int(resample_hz) if resample_hz and resample_hz > 0 else 16000
    report(f"[1/6] Dang doc file: {os.path.basename(input_path)} ({sr}Hz mono)")
    y = doc_audio(input_path, sr)
    thoi_luong_goc = len(y) / sr

    if khu_on:
        report(f"[2/6] Dang loc dai tan giong noi (bandpass {bandpass_low}-{bandpass_high}Hz)...")
        y = bandpass_filter(y, sr, low=bandpass_low, high=bandpass_high)
        report("[3/6] Dang giam tieng on nen...")
        y = reduce_noise(y, sr, noise_sample_sec=noise_sample_sec, prop_decrease=prop_decrease)
        y = np.ascontiguousarray(y, dtype=np.float32)
    else:
        report("[2/6] Loc dai tan: tat, bo qua.")
        report("[3/6] Giam tieng on nen: tat, bo qua.")

    if level_window_sec and level_window_sec > 0:
        report(f"[4/6] Dang can bang am luong luc giang vien di xa/gan (cua so {level_window_sec:g}s)...")
        y = level_loudness(y, sr, window_sec=level_window_sec)
    else:
        report("[4/6] Can bang am luong theo thoi gian: tat, bo qua.")

    report("[5/6] Dang tang am luong giong noi...")
    y = boost_and_normalize(y, target_dBFS=target_dbfs)

    ban_do = BanDoThoiGian.khong_cat(thoi_luong_goc)
    if cat_khoang_lang:
        report("[6/6] Dang cat cac doan im lang...")
        y, giu = trim_silence(
            y, sr,
            silence_thresh_offset=silence_thresh_offset,
            min_silence_len=min_silence_len,
            keep_silence=keep_silence,
        )
        ban_do = BanDoThoiGian([(a / sr, b / sr) for a, b in giu], thoi_luong_goc)
    else:
        report("[6/6] Cat khoang lang: tat, bo qua.")

    report(f"   Thoi luong: {thoi_luong_goc:.1f}s (goc) -> {len(y) / sr:.1f}s (sau xu ly)")
    return y, sr, ban_do


def lam_sach_theo_cau_hinh(ch, input_path: str, progress_callback=None
                           ) -> tuple[np.ndarray, int, BanDoThoiGian]:
    """Goi lam_sach() voi cac tham so trong CauHinh (cau_hinh.py)."""
    return lam_sach(
        input_path,
        khu_on=ch.khu_on,
        target_dbfs=ch.target_dbfs,
        cat_khoang_lang=ch.cat_khoang_lang,
        min_silence_len=ch.min_silence_len,
        silence_thresh_offset=ch.silence_thresh_offset,
        keep_silence=ch.keep_silence,
        noise_sample_sec=ch.noise_sample_sec,
        resample_hz=ch.tan_so_lay_mau,
        bandpass_low=ch.bandpass_low,
        bandpass_high=ch.bandpass_high,
        prop_decrease=ch.prop_decrease,
        level_window_sec=ch.level_window_sec,
        progress_callback=progress_callback,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Lam sach audio bai giang theo config.txt, ghi ra mot file WAV de nghe thu."
    )
    parser.add_argument("input", help="File audio dau vao (m4a, flac, mp3, wav, ...)")
    parser.add_argument("-o", "--output", default=None,
                        help="File WAV dau ra (mac dinh: <ten_goc>_processed.wav)")
    parser.add_argument("--config", default=None, help="Duong dan config.txt")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if not os.path.exists(args.input):
        print(f"Khong tim thay file: {args.input}", file=sys.stderr)
        sys.exit(1)

    from cau_hinh import doc_cau_hinh
    from duong_dan import CONFIG_PATH

    try:
        ch = doc_cau_hinh(args.config or CONFIG_PATH)
        y, sr, _ = lam_sach_theo_cau_hinh(ch, args.input, progress_callback=print)
        ra = args.output or os.path.splitext(args.input)[0] + "_processed.wav"
        ghi_audio(y, sr, ra, "wav")
        print(f"Xong! File da luu tai: {ra}")
    except Exception as e:
        print(f"Loi: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
