"""
cat_doan.py
Cat audio da lam sach thanh cac doan ~N phut de gui len Google AI tung doan.

Khong cat dung phut thu 10: cat ngang giua mot tu thi ca hai doan deu nghe
duoc nua tu, model doan bay hoac bo di, noi lai se sai. Thay vao do, tim cho
LANG NHAT (nang luong trung binh 400ms thap nhat) trong khoang +-giay_tim quanh
moc, roi cat giua cho do.

Moc cua doan sau tinh tu diem cat THAT cua doan truoc, nen do dai cac doan
luon nam trong [N - giay_tim, N + giay_tim], khong bi troi dan.
Doan cuoi ngan hon giay_doan_cuoi_toi_thieu thi gop vao doan truoc.
"""

from __future__ import annotations

import os

import numpy as np

from am_thanh_io import ghi_audio

_KHOI_MS = 50            # do phan giai khi do nang luong
_CUA_SO_LANG_MS = 400    # "cho lang" phai lang lien tuc chung nay


def _nang_luong_theo_khoi(y: np.ndarray, khoi: int) -> np.ndarray:
    so_khoi = len(y) // khoi
    nang_luong = np.empty(so_khoi, dtype=np.float64)
    buoc = max(1, (1 << 20) // khoi)
    for k in range(0, so_khoi, buoc):
        m = min(so_khoi, k + buoc)
        doan = y[k * khoi:m * khoi].reshape(m - k, khoi)
        nang_luong[k:m] = np.mean(np.square(doan, dtype=np.float32), axis=1)
    return nang_luong


def _trung_binh_truot(x: np.ndarray, cua_so: int) -> np.ndarray:
    if cua_so <= 1 or x.size == 0:
        return x
    cong_don = np.concatenate(([0.0], np.cumsum(x, dtype=np.float64)))
    i = np.arange(x.size)
    dau = np.maximum(0, i - cua_so // 2)
    cuoi = np.minimum(x.size, i + cua_so - cua_so // 2)
    return (cong_don[cuoi] - cong_don[dau]) / (cuoi - dau)


def tim_diem_cat(y: np.ndarray, sr: int, phut_moi_doan: float = 10.0,
                 giay_tim: float = 20.0, giay_doan_cuoi_toi_thieu: float = 60.0) -> list[int]:
    """
    Tra ve danh sach chi so mau [0, c1, c2, ..., len(y)]; doan i la y[diem[i]:diem[i+1]].
    """
    n = len(y)
    dai = int(round(phut_moi_doan * 60 * sr))
    cuoi_toi_thieu = int(max(0.0, giay_doan_cuoi_toi_thieu) * sr)
    tim = int(max(0.0, giay_tim) * sr)
    if dai <= 0 or n <= dai + cuoi_toi_thieu:
        return [0, n]

    khoi = max(1, sr * _KHOI_MS // 1000)
    muot = _trung_binh_truot(_nang_luong_theo_khoi(y, khoi), max(1, _CUA_SO_LANG_MS // _KHOI_MS))

    diem = [0]
    while n - diem[-1] > dai + cuoi_toi_thieu:
        truoc = diem[-1]
        dich = truoc + dai
        # Khong lui qua nua doan (doan qua ngan), khong tien sat cuoi file (doan
        # cuoi qua ngan). Vi n - truoc > dai + cuoi_toi_thieu nen luon co a <= dich < b.
        a = max(truoc + dai // 2, dich - tim)
        b = min(dich + tim, n - cuoi_toi_thieu)

        ka, kb = a // khoi, min(len(muot), b // khoi)
        if tim == 0 or ka >= kb:
            cat = dich
        else:
            k = ka + int(np.argmin(muot[ka:kb]))
            cat = k * khoi + khoi // 2
        diem.append(min(max(cat, truoc + 1), n - 1))
    diem.append(n)
    return diem


def ghi_cac_doan(y: np.ndarray, sr: int, diem: list[int], thu_muc: str,
                 dinh_dang: str = "flac", progress_callback=None) -> list[dict]:
    """
    Ghi tung doan ra thu_muc/doan_001.<dinh_dang>... Tra ve danh sach
    {"file", "bat_dau_giay", "ket_thuc_giay"} (moc tinh tren audio DA lam sach).
    """
    os.makedirs(thu_muc, exist_ok=True)
    tong = len(diem) - 1
    doan = []
    for i in range(tong):
        a, b = diem[i], diem[i + 1]
        ten = f"doan_{i + 1:03d}.{dinh_dang}"
        ghi_audio(y[a:b], sr, os.path.join(thu_muc, ten), dinh_dang)
        doan.append({
            "file": ten,
            "bat_dau_giay": round(a / sr, 3),
            "ket_thuc_giay": round(b / sr, 3),
        })
        if progress_callback:
            progress_callback(f"Da ghi {ten} ({doan[-1]['bat_dau_giay'] / 60:.1f} - "
                              f"{doan[-1]['ket_thuc_giay'] / 60:.1f} phut)")
    return doan
