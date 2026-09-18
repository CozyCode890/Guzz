from __future__ import annotations

import logging
import os

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import ComboBox, FluentIcon, PlainTextEdit, PushButton, SearchLineEdit, TitleLabel

import cau_hinh as chh
from i18n import bo_dich, tr
from log_bridge import QtLogHandler
from paths import CONFIG_PATH, duong_dan_nhat_ky
from su_kien import su_kien
from widgets import mo_bang_windows, mo_thu_muc_chua

_MUC = [(0, "logs_level_all"), (logging.WARNING, "logs_level_warning"), (logging.ERROR, "logs_level_error")]
_TEN_MUC = {"WARNING": logging.WARNING, "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL}


def _muc_cua_dong(dong: str) -> int:
    phan = dong.split("|")
    return _TEN_MUC.get(phan[1].strip(), logging.INFO) if len(phan) > 2 else logging.INFO


class TrangNhatKy(QWidget):
    def __init__(self, log_handler: QtLogHandler, parent=None):
        super().__init__(parent)
        self.setObjectName("logsInterface")
        self._duong_dan_log = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(10)

        self.tieu_de = TitleLabel(tr("logs_title"), self)
        root.addWidget(self.tieu_de)

        hang_tim = QHBoxLayout()
        self.o_tim = SearchLineEdit(self)
        self.o_tim.setPlaceholderText(tr("logs_search_placeholder"))
        self.o_tim.textChanged.connect(self._ve_lai)
        self.o_muc = ComboBox(self)
        self.o_muc.addItems([tr(k) for _, k in _MUC])
        self.o_muc.currentIndexChanged.connect(self._ve_lai)
        self.nut_mo_file = PushButton(FluentIcon.DOCUMENT, tr("logs_btn_open_file"), self)
        self.nut_mo_file.clicked.connect(lambda: mo_bang_windows(self._duong_dan_log))
        self.nut_mo_thu_muc = PushButton(FluentIcon.FOLDER, tr("logs_btn_open_folder"), self)
        self.nut_mo_thu_muc.clicked.connect(lambda: mo_thu_muc_chua(self._duong_dan_log))
        self.nut_xoa_man_hinh = PushButton(FluentIcon.BROOM, tr("logs_btn_clear_view"), self)
        self.nut_xoa_man_hinh.clicked.connect(self._xoa_man_hinh)
        hang_tim.addWidget(self.o_tim, 1)
        hang_tim.addWidget(self.o_muc)
        hang_tim.addWidget(self.nut_mo_file)
        hang_tim.addWidget(self.nut_mo_thu_muc)
        hang_tim.addWidget(self.nut_xoa_man_hinh)
        root.addLayout(hang_tim)

        self.khung = PlainTextEdit(self)
        self.khung.setReadOnly(True)
        self.khung.setLineWrapMode(PlainTextEdit.LineWrapMode.NoWrap)
        root.addWidget(self.khung, 1)

        self._dong_goc: list[tuple[str, int]] = []
        log_handler.dong_moi.connect(self._them_dong)
        bo_dich.doi_ngon_ngu.connect(self._doi_ngon_ngu)
        su_kien.co_nhat_ky_doi.connect(self._dat_co_chu)
        self._nap_file_log()

    def _nap_file_log(self):
        try:
            ch = chh.doc_cau_hinh(CONFIG_PATH)
        except Exception:
            ch = chh.CauHinh()
        self._duong_dan_log = duong_dan_nhat_ky(ch.file_log)
        self._dat_co_chu(ch.co_chu_nhat_ky)
        if os.path.exists(self._duong_dan_log):
            try:
                with open(self._duong_dan_log, "r", encoding="utf-8", errors="replace") as f:
                    dong = f.readlines()[-1000:]
                self._dong_goc = [(d.rstrip("\n"), _muc_cua_dong(d)) for d in dong]
            except OSError:
                self._dong_goc = []
        self._ve_lai()

    def _dat_co_chu(self, co: int):
        f = self.khung.font()
        f.setFamilies(["Cascadia Mono", "Consolas"])
        f.setPixelSize(co)
        self.khung.setFont(f)

    def _hien(self, dong: str, muc: int) -> bool:
        loc = self.o_tim.text().strip().lower()
        return muc >= _MUC[max(0, self.o_muc.currentIndex())][0] and (not loc or loc in dong.lower())

    def _them_dong(self, dong: str, muc: int):
        self._dong_goc.append((dong, muc))
        if len(self._dong_goc) > 3000:
            self._dong_goc = self._dong_goc[-2000:]
        if self._hien(dong, muc):
            self.khung.appendPlainText(dong)

    def _ve_lai(self, *_):
        self.khung.setPlainText("\n".join(d for d, m in self._dong_goc if self._hien(d, m)))
        self.khung.verticalScrollBar().setValue(self.khung.verticalScrollBar().maximum())

    def _xoa_man_hinh(self):
        self._dong_goc = []
        self.khung.clear()

    def _doi_ngon_ngu(self, _ma):
        self.tieu_de.setText(tr("logs_title"))
        self.o_tim.setPlaceholderText(tr("logs_search_placeholder"))
        i = self.o_muc.currentIndex()
        self.o_muc.blockSignals(True)
        self.o_muc.clear()
        self.o_muc.addItems([tr(k) for _, k in _MUC])
        self.o_muc.setCurrentIndex(max(0, i))
        self.o_muc.blockSignals(False)
        self.nut_mo_file.setText(tr("logs_btn_open_file"))
        self.nut_mo_thu_muc.setText(tr("logs_btn_open_folder"))
        self.nut_xoa_man_hinh.setText(tr("logs_btn_clear_view"))
