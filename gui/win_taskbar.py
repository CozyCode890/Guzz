# -*- coding: utf-8 -*-
"""
win_taskbar.py
Gan AppUserModelID de Windows hien dung icon cho nut taskbar (lay tu GoogleAITranscribe).

Python ban Microsoft Store chay kem package identity
(PythonSoftwareFoundation.Python.3.12...). Windows gom nut taskbar theo
AppUserModelID, va voi tien trinh co package identity thi ID do lay tu goi ung
dung - nen taskbar hien icon Python, bo qua ca setWindowIcon() lan
SetCurrentProcessExplicitAppUserModelID().

Cach xu ly: dat AppUserModelID rieng o CAP CUA SO qua
SHGetPropertyStoreForWindow. Cua so duoc tach khoi nhom cua goi Python, luc do
Windows quay ve dung icon cua chinh cua so.

Viet bang ctypes de khong them phu thuoc (khong can pywin32).
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

APP_USER_MODEL_ID = "Guzz.Transcribe.GUI.1"

_VT_LPWSTR = 31


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]


class _PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", _GUID), ("pid", wintypes.DWORD)]


class _PROPVARIANT(ctypes.Structure):
    # vt + 3 truong reserved (8 byte) roi den union 16 byte; chi dung con tro chuoi.
    _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ubyte), ("r2", ctypes.c_ubyte),
                ("r3", ctypes.c_ulong), ("p", ctypes.c_void_p), ("pad", ctypes.c_void_p)]


def _guid(chuoi: str) -> _GUID:
    g = _GUID()
    ctypes.windll.ole32.CLSIDFromString(chuoi, ctypes.byref(g))
    return g


def dat_app_id_tien_trinh() -> None:
    """Dat AppUserModelID cap tien trinh. Du khong an voi Python ban Store, van
    can cho Python thuong va cho ban dong goi thanh .exe sau nay."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def dat_app_id_cua_so(hwnd: int) -> bool:
    """Dat AppUserModelID cho mot cua so cu the. Tra ve True neu thanh cong."""
    if sys.platform != "win32":
        return False
    try:
        IID_IPropertyStore = _guid("{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}")
        PKEY_AppUserModel_ID = _PROPERTYKEY(
            _guid("{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}"), 5)

        store = ctypes.c_void_p()
        hr = ctypes.windll.shell32.SHGetPropertyStoreForWindow(
            wintypes.HWND(hwnd), ctypes.byref(IID_IPropertyStore), ctypes.byref(store))
        if hr != 0 or not store:
            return False

        # IPropertyStore: 0-2 la IUnknown, 6 = SetValue, 7 = Commit.
        vtbl = ctypes.cast(store, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        Release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])
        SetValue = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p,
                                      ctypes.POINTER(_PROPERTYKEY),
                                      ctypes.POINTER(_PROPVARIANT))(vtbl[6])
        Commit = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p)(vtbl[7])

        cap_phat = ctypes.windll.ole32.CoTaskMemAlloc
        cap_phat.restype = ctypes.c_void_p          # bat buoc, neu khong con tro 64-bit bi cat
        cap_phat.argtypes = [ctypes.c_size_t]

        pv = _PROPVARIANT()
        pv.vt = _VT_LPWSTR
        so_byte = (len(APP_USER_MODEL_ID) + 1) * 2
        pv.p = cap_phat(so_byte)
        ctypes.memmove(pv.p, ctypes.create_unicode_buffer(APP_USER_MODEL_ID), so_byte)
        try:
            SetValue(store, ctypes.byref(PKEY_AppUserModel_ID), ctypes.byref(pv))
            Commit(store)
        finally:
            ctypes.windll.ole32.PropVariantClear(ctypes.byref(pv))
            Release(store)
        return True
    except Exception:
        return False
