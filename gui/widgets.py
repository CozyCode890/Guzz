"""
widgets.py
Cac khoi giao dien dung chung (lay tu GoogleAITranscribe, them the nhom, hang
combo co dich, hang chon thu muc / file).
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel, CardWidget, ComboBox, FluentIcon, LineEdit, PushButton, SingleDirectionScrollArea,
    StrongBodyLabel, SwitchButton,
)

from i18n import tr

MAU_GOI_Y = "#8a8a8a"
MAU_LOI = ("#c42b1c", "#ff99a4")
MAU_TOT = ("#0f7b0f", "#6ccb5f")


def dich_cong_tac(switch: SwitchButton):
    """SwitchButton mac dinh ghi "On/Off" bang tieng Anh."""
    switch.setOnText(tr("common_on"))
    switch.setOffText(tr("common_off"))


def chu_goi_y(key: str, parent=None, *tham_so) -> CaptionLabel:
    nhan = CaptionLabel(tr(key, *tham_so) if key else "", parent)
    nhan.setWordWrap(True)
    nhan.setTextColor(MAU_GOI_Y, MAU_GOI_Y)
    return nhan


def bool_txt(gia_tri: bool) -> str:
    return "true" if gia_tri else "false"


def mo_bang_windows(duong_dan: str):
    if duong_dan and os.path.exists(duong_dan):
        os.startfile(duong_dan)


def mo_thu_muc_chua(duong_dan: str):
    """Mo Explorer va chon san file (neu con)."""
    import subprocess
    if duong_dan and os.path.isfile(duong_dan):
        subprocess.Popen(["explorer", "/select,", os.path.normpath(duong_dan)])
    elif duong_dan:
        thu_muc = duong_dan if os.path.isdir(duong_dan) else os.path.dirname(duong_dan)
        if os.path.isdir(thu_muc):
            os.startfile(thu_muc)


class Hang(QFrame):
    """Nhan co do rong co dinh ben trai, o nhap ben phai."""

    def __init__(self, nhan_key: str, o_nhap: QWidget, parent=None, gian=False, rong_nhan=300):
        super().__init__(parent)
        self.nhan_key = nhan_key
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        self.nhan = CaptionLabel(tr(nhan_key), self)
        self.nhan.setFixedWidth(rong_nhan)
        self.nhan.setWordWrap(True)
        self.o_nhap = o_nhap
        o_nhap.setParent(self)
        lay.addWidget(self.nhan)
        lay.addWidget(o_nhap, 1 if gian else 0)
        if not gian:
            lay.addStretch(1)

    def doi_ngon_ngu(self):
        self.nhan.setText(tr(self.nhan_key))


class HangSwitch(QFrame):
    """Cong tac o ben phai, goi y (tuy chon) mau xam ben duoi."""

    def __init__(self, nhan_key: str, goi_y_key: str | None = None, parent=None):
        super().__init__(parent)
        self.nhan_key = nhan_key
        self.goi_y_key = goi_y_key
        self._tham_so_goi_y = ()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 6, 0, 6)
        hang = QHBoxLayout()
        self.nhan = CaptionLabel(tr(nhan_key), self)
        self.nhan.setWordWrap(True)
        self.switch = SwitchButton(self)
        dich_cong_tac(self.switch)
        hang.addWidget(self.nhan, 1)
        hang.addWidget(self.switch)
        root.addLayout(hang)
        self.goi_y = chu_goi_y(goi_y_key, self) if goi_y_key else None
        if self.goi_y:
            root.addWidget(self.goi_y)

    def dat_tham_so_goi_y(self, *tham_so):
        self._tham_so_goi_y = tham_so
        self.doi_ngon_ngu()

    def doi_ngon_ngu(self):
        self.nhan.setText(tr(self.nhan_key))
        dich_cong_tac(self.switch)
        if self.goi_y:
            self.goi_y.setText(tr(self.goi_y_key, *self._tham_so_goi_y))


class HangCombo(Hang):
    """
    ComboBox co danh sach (gia_tri trong config, key dich). gia_tri() tra ve gia
    tri config; doi ngon ngu thi dich lai chu ma khong mat lua chon.
    """

    doi = Signal(str)

    def __init__(self, nhan_key: str, cac_muc: list[tuple[str, str]], parent=None, rong=240):
        combo = ComboBox()
        combo.setMinimumWidth(rong)
        super().__init__(nhan_key, combo, parent)
        self.combo = combo
        self.cac_muc = list(cac_muc)
        self._dich_muc()
        self.combo.currentIndexChanged.connect(lambda i: self.doi.emit(self.gia_tri()))

    def _dich_muc(self):
        chi_so = self.combo.currentIndex()
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems([tr(k) if k else v for v, k in self.cac_muc])
        self.combo.setCurrentIndex(max(0, chi_so))
        self.combo.blockSignals(False)

    def gia_tri(self) -> str:
        i = self.combo.currentIndex()
        return self.cac_muc[i][0] if 0 <= i < len(self.cac_muc) else ""

    def dat(self, gia_tri: str):
        for i, (v, _) in enumerate(self.cac_muc):
            if v == gia_tri:
                self.combo.setCurrentIndex(i)
                return
        self.combo.setCurrentIndex(0)

    def doi_ngon_ngu(self):
        super().doi_ngon_ngu()
        self._dich_muc()


class HangDuongDan(QFrame):
    """Nhan + o duong dan + nut Chon. kieu: 'thu_muc' hoac bo loc file ('python.exe (python.exe)')."""

    da_sua = Signal(str)

    def __init__(self, nhan_key: str, parent=None, kieu: str = "thu_muc", goi_y_o_key: str | None = None,
                 rong_nhan=300):
        super().__init__(parent)
        self.nhan_key = nhan_key
        self.kieu = kieu
        self.goi_y_o_key = goi_y_o_key
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        self.nhan = CaptionLabel(tr(nhan_key), self)
        self.nhan.setFixedWidth(rong_nhan)
        self.nhan.setWordWrap(True)
        self.o = LineEdit(self)
        self.o.setClearButtonEnabled(True)
        if goi_y_o_key:
            self.o.setPlaceholderText(tr(goi_y_o_key))
        self.o.editingFinished.connect(lambda: self.da_sua.emit(self.o.text().strip()))
        self.nut = PushButton(FluentIcon.FOLDER, tr("common_browse"), self)
        self.nut.clicked.connect(self._chon)
        lay.addWidget(self.nhan)
        lay.addWidget(self.o, 1)
        lay.addWidget(self.nut)

    def _chon(self):
        hien_tai = os.path.expandvars(self.o.text().strip())
        if self.kieu == "thu_muc":
            chon = QFileDialog.getExistingDirectory(self, tr(self.nhan_key), hien_tai)
        else:
            chon, _ = QFileDialog.getOpenFileName(self, tr(self.nhan_key), hien_tai, self.kieu)
        if chon:
            self.o.setText(os.path.normpath(chon))
            self.da_sua.emit(self.o.text())

    def text(self) -> str:
        return self.o.text().strip()

    def setText(self, s: str):
        self.o.setText(s)

    def doi_ngon_ngu(self):
        self.nhan.setText(tr(self.nhan_key))
        self.nut.setText(tr("common_browse"))
        if self.goi_y_o_key:
            self.o.setPlaceholderText(tr(self.goi_y_o_key))


class TheNhom(CardWidget):
    """The co tieu de dam va (tuy chon) goi y; them hang vao self.lay."""

    def __init__(self, tieu_de_key: str, goi_y_key: str | None = None, parent=None):
        super().__init__(parent)
        self.tieu_de_key = tieu_de_key
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(20, 16, 20, 16)
        self.lay.setSpacing(4)
        self.nhan = StrongBodyLabel(tr(tieu_de_key), self)
        self.lay.addWidget(self.nhan)
        self.goi_y = chu_goi_y(goi_y_key, self) if goi_y_key else None
        self.goi_y_key = goi_y_key
        if self.goi_y:
            self.lay.addWidget(self.goi_y)
        self._con: list = []

    def them(self, *widget):
        for w in widget:
            self.lay.addWidget(w)
            if hasattr(w, "doi_ngon_ngu"):
                self._con.append(w)
        return widget[0] if len(widget) == 1 else widget

    def doi_ngon_ngu(self):
        self.nhan.setText(tr(self.tieu_de_key))
        if self.goi_y:
            self.goi_y.setText(tr(self.goi_y_key))
        for w in self._con:
            w.doi_ngon_ngu()


class TrangCuon(QWidget):
    """Trang co thanh cuon doc; them noi dung vao self.root."""

    def __init__(self, ten_doi_tuong: str, parent=None):
        super().__init__(parent)
        self.setObjectName(ten_doi_tuong)
        ngoai = QVBoxLayout(self)
        ngoai.setContentsMargins(0, 0, 0, 0)
        cuon = SingleDirectionScrollArea(self, orient=Qt.Vertical)
        cuon.setWidgetResizable(True)
        cuon.setStyleSheet("QScrollArea{background: transparent; border: none}")
        self.khung = QWidget(cuon)
        self.khung.setObjectName(ten_doi_tuong + "ScrollView")
        self.khung.setStyleSheet(f"#{ten_doi_tuong}ScrollView{{background: transparent}}")
        cuon.setWidget(self.khung)
        ngoai.addWidget(cuon)

        self.root = QVBoxLayout(self.khung)
        self.root.setContentsMargins(28, 24, 28, 24)
        self.root.setSpacing(12)
