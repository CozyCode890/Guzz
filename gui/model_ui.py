"""
model_ui.py
Dung chung cho cac o chon model: danh sach model goi y, mo ta khoa (het han muc,
qua tai...), dien combo va lam mo (khong cho chon) cac model dang bi khoa, ten
cac cach nhan dien nguoi noi va rang buoc model <-> cach nhan dien.
"""

from __future__ import annotations

import time

from qfluentwidgets import FluentIcon

import cau_hinh as chh
import han_muc
from i18n import tr

MODEL_GOI_Y = ["gemini-3.5-transcribe", "gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"]
CAC_CACH = [(chh.NN_PYANNOTE, "nn_mode_pyannote"), (chh.NN_GEMINI, "nn_mode_gemini"), (chh.NN_KET_HOP, "nn_mode_hybrid")]
_KEY_CACH = dict(CAC_CACH)


def ten_cach(cach: str) -> str:
    return tr(_KEY_CACH.get(cach, cach))


def kieu_model(model: str) -> str:
    return tr("model_kind_transcribe" if chh.la_model_go_chu(model) else "model_kind_general")


def goi_y_rang_buoc(model: str) -> str:
    return tr("rb_transcribe" if chh.la_model_go_chu(model) else "rb_general")


def cac_model_biet(ch: chh.CauHinh | None = None, them=()) -> list[str]:
    ds = list(MODEL_GOI_Y)
    if ch is not None:
        ds += [ch.model, *ch.model_du_phong, *ch.han_muc_model]
    ds += han_muc.so_theo_doi().cac_model()
    ds += list(them)
    return list(dict.fromkeys(m.strip() for m in ds if m and m.strip()))


def ly_do_khoa(ly_do: str) -> str:
    return tr("use_reason_" + ly_do) if ly_do else ""


def mo_ta_khoa(model: str) -> str | None:
    """'khoa toi 14:00 (con 3:12:05) — het han muc trong ngay', None neu model khong bi khoa."""
    khoa, den, ly_do, _ = han_muc.so_theo_doi().trang_thai_khoa(model)
    if not khoa:
        return None
    if den is None:
        return tr("model_locked_manual", ly_do_khoa(ly_do))
    bay_gio = time.time()
    return tr("model_locked_until", han_muc.gio_may(den, bay_gio), han_muc.dem_nguoc(den - bay_gio), ly_do_khoa(ly_do))


def dien_combo_model(combo, cac_model: list[str], chon: str, sua_duoc: bool = False):
    """
    Dien lai combo model, giu model dang chon. Model dang khoa bi mo, khong bam chon duoc.
    sua_duoc (EditableComboBox): chu cua muc chinh la ten model, danh dau khoa bang icon.
    Khong sua duoc (ComboBox): them "🔒 14:00" sau ten, ten model nam trong userData.
    """
    so = han_muc.so_theo_doi()
    if chon and chon not in cac_model:
        cac_model = [chon, *cac_model]
    combo.blockSignals(True)
    combo.clear()
    for m in cac_model:
        khoa, den, _, _ = so.trang_thai_khoa(m)
        if sua_duoc:
            combo.addItem(m, FluentIcon.CANCEL if khoa else None, m)
        else:
            chu = m + (f"  🔒 {han_muc.gio_may(den) if den else tr('model_locked_short')}" if khoa else "")
            combo.addItem(chu, userData=m)
        combo.setItemEnabled(combo.count() - 1, not khoa)
    if sua_duoc:
        combo.setText(chon)
    else:
        i = combo.findData(chon)
        combo.setCurrentIndex(i if i is not None and i >= 0 else 0)
    combo.blockSignals(False)
