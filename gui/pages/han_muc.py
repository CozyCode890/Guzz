from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QGridLayout, QHBoxLayout, QHeaderView, QTableWidgetItem, QWidget
from qfluentwidgets import (
    BodyLabel, CaptionLabel, FluentIcon, InfoBar, InfoBarPosition, LineEdit, PrimaryPushButton, PushButton,
    SpinBox, StrongBodyLabel, TableWidget, TitleLabel, TransparentToolButton, isDarkTheme,
)

import cau_hinh as chh
import config_io as cio
import google_ai as ga
import han_muc
import model_ui
from i18n import bo_dich, tr
from paths import CONFIG_PATH
from su_kien import su_kien
from widgets import MAU_LOI, MAU_TOT, TheNhom, TrangCuon, chu_goi_y

TEN_TRANG = "han_muc"

(COT_MODEL, COT_TRANG_THAI, COT_HOM_NAY, COT_TOKEN_HOM_NAY, COT_TOKEN_PHUT, COT_LOI,
 COT_LOI_CUOI) = range(7)
_TIEU_DE_COT = ["use_col_model", "use_col_status", "use_col_today", "use_col_tokens_today", "use_col_minute",
                "use_col_errors", "use_col_last_error"]
_LOAI_LOI = ["qua_tai", "han_muc", "han_muc_ngay", "bi_chan", "model", "cau_hinh", "tam_thoi", "khac"]


def _so(n) -> str:
    return f"{int(n or 0):,}".replace(",", ".")


def _bang(parent, so_cot: int) -> TableWidget:
    b = TableWidget(parent)
    b.setColumnCount(so_cot)
    b.setBorderVisible(True)
    b.setBorderRadius(6)
    b.setWordWrap(False)
    b.verticalHeader().hide()
    b.setEditTriggers(QAbstractItemView.NoEditTriggers)
    b.setSelectionBehavior(QAbstractItemView.SelectRows)
    b.setSelectionMode(QAbstractItemView.SingleSelection)
    return b


def _dat_o(bang: TableWidget, hang: int, cot: int, chu: str, mau: str | None = None, goi_y: str | None = None):
    o = bang.item(hang, cot)
    if o is None:
        o = QTableWidgetItem()
        bang.setItem(hang, cot, o)
    if o.text() != chu:
        o.setText(chu)
    o.setToolTip(goi_y if goi_y is not None else chu)
    o.setForeground(QColor(mau) if mau else QColor("#ffffff" if isDarkTheme() else "#000000"))


class TrangHanMuc(TrangCuon):
    can_mo_trang = Signal(str)

    def __init__(self, parent=None):
        super().__init__("usageInterface", parent)
        khung, root = self.khung, self.root
        self._ch = chh.CauHinh()
        self._cac_the: list[TheNhom] = []
        self._dau_su_kien_da_ve = None
        self._hang_han_muc: dict[str, dict] = {}
        self._cho_nap = False

        self.tieu_de = TitleLabel(tr("use_title"), khung)
        root.addWidget(self.tieu_de)
        self.phu_de = chu_goi_y("use_subtitle", khung)
        root.addWidget(self.phu_de)

        # ---- A. Bay gio ----
        the = self._the("use_section_now")
        self.nhan_cho = StrongBodyLabel("", the)
        self.nhan_cho.setWordWrap(True)
        the.lay.addWidget(self.nhan_cho)
        self.nhan_chuoi = BodyLabel("", the)
        self.nhan_chuoi.setWordWrap(True)
        the.lay.addWidget(self.nhan_chuoi)
        self.nhan_dat_lai = CaptionLabel("", the)
        self.nhan_dat_lai.setWordWrap(True)
        the.lay.addWidget(self.nhan_dat_lai)

        # ---- B. Cac model ----
        the = self._the("use_section_models")
        self.bang_model = _bang(the, len(_TIEU_DE_COT))
        dau = self.bang_model.horizontalHeader()
        dau.setMinimumSectionSize(110)
        for cot in range(len(_TIEU_DE_COT)):
            dau.setSectionResizeMode(cot, QHeaderView.Interactive)
        # Trang thai dai (gio mo khoa + ly do) thi cat bot, di chuot vao de xem du.
        for cot, rong in ((COT_MODEL, 190), (COT_TRANG_THAI, 330), (COT_HOM_NAY, 120), (COT_TOKEN_HOM_NAY, 120),
                          (COT_TOKEN_PHUT, 130), (COT_LOI, 170)):
            self.bang_model.setColumnWidth(cot, rong)
        dau.setSectionResizeMode(COT_LOI_CUOI, QHeaderView.Stretch)
        self.bang_model.setTextElideMode(Qt.ElideRight)
        self.bang_model.setMinimumHeight(190)
        self.bang_model.itemSelectionChanged.connect(self._cap_nhat_nut)
        the.lay.addWidget(self.bang_model)
        hang = QHBoxLayout()
        self.nut_mo_khoa = PrimaryPushButton(FluentIcon.ACCEPT, tr("use_btn_unlock"), the)
        self.nut_quen = PushButton(FluentIcon.BROOM, tr("use_btn_forget"), the)
        self.nut_dat_lai = PushButton(FluentIcon.SYNC, tr("use_btn_reset_counts"), the)
        self.nut_nhat_ky = PushButton(FluentIcon.HISTORY, tr("use_btn_open_log"), the)
        self.nut_mo_khoa.clicked.connect(self._mo_khoa)
        self.nut_quen.clicked.connect(self._quen_han_muc)
        self.nut_dat_lai.clicked.connect(self._dat_lai_bo_dem)
        self.nut_nhat_ky.clicked.connect(lambda: self.can_mo_trang.emit("nhat_ky"))
        for n in (self.nut_mo_khoa, self.nut_quen, self.nut_dat_lai):
            hang.addWidget(n)
        hang.addStretch(1)
        hang.addWidget(self.nut_nhat_ky)
        the.lay.addLayout(hang)

        # ---- C. Han muc tung model ----
        self.the_han_muc = the = self._the("use_section_limits", "use_limits_hint")
        self.khung_luoi = QWidget(the)
        self.luoi = QGridLayout(self.khung_luoi)
        self.luoi.setContentsMargins(0, 8, 0, 0)
        self.luoi.setHorizontalSpacing(12)
        self.luoi.setVerticalSpacing(6)
        the.lay.addWidget(self.khung_luoi)
        hang = QHBoxLayout()
        self.o_model_moi = LineEdit(the)
        self.o_model_moi.setPlaceholderText(tr("use_add_model_placeholder"))
        self.o_model_moi.setMinimumWidth(260)
        self.o_model_moi.returnPressed.connect(self._them_dong_han_muc)
        self.nut_them = PushButton(FluentIcon.ADD, tr("use_btn_add"), the)
        self.nut_them.clicked.connect(self._them_dong_han_muc)
        self.nut_luu_han_muc = PrimaryPushButton(FluentIcon.SAVE, tr("common_save"), the)
        self.nut_luu_han_muc.clicked.connect(self._luu_han_muc)
        hang.addWidget(self.o_model_moi)
        hang.addWidget(self.nut_them)
        hang.addStretch(1)
        hang.addWidget(self.nut_luu_han_muc)
        the.lay.addLayout(hang)

        # ---- D. Lich su ----
        the = self._the("use_section_events")
        self.bang_su_kien = _bang(the, 4)
        dau = self.bang_su_kien.horizontalHeader()
        for cot in range(3):
            dau.setSectionResizeMode(cot, QHeaderView.ResizeToContents)
        dau.setSectionResizeMode(3, QHeaderView.Stretch)
        self.bang_su_kien.setMinimumHeight(260)
        the.lay.addWidget(self.bang_su_kien)
        hang = QHBoxLayout()
        hang.addStretch(1)
        self.nut_xoa_lich_su = PushButton(FluentIcon.DELETE, tr("use_btn_clear_events"), the)
        self.nut_xoa_lich_su.clicked.connect(self._xoa_lich_su)
        hang.addWidget(self.nut_xoa_lich_su)
        the.lay.addLayout(hang)
        root.addStretch(1)

        self._dat_tieu_de_cot()
        self.dong_ho = QTimer(self)
        self.dong_ho.setInterval(1000)
        self.dong_ho.timeout.connect(self._ve)
        bo_dich.doi_ngon_ngu.connect(self._doi_ngon_ngu)
        # Trang dang an thi khong ve gi: showEvent dung lai luoi va ve lai tu dau khi mo ra.
        # Ve lai trang nay kha dat (dung lai ca luoi SpinBox + bang 200 dong su kien).
        su_kien.cau_hinh_doi.connect(self._cau_hinh_doi)
        su_kien.han_muc_doi.connect(lambda: self.isVisible() and self._ve())
        self._nap_du_lieu()

    def _cau_hinh_doi(self, nguon: str):
        if nguon == TEN_TRANG:
            return
        if self.isVisible():
            self._nap_du_lieu()
        else:
            self._cho_nap = True

    def _the(self, tieu_de_key, goi_y_key=None) -> TheNhom:
        the = TheNhom(tieu_de_key, goi_y_key, self.khung)
        self.root.addWidget(the)
        self._cac_the.append(the)
        return the

    def showEvent(self, e):
        super().showEvent(e)
        if self._cho_nap:
            self._cho_nap = False
            self._nap_du_lieu()
        else:
            self._ve(ve_lai_su_kien=True)
        self.dong_ho.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.dong_ho.stop()

    # ------------------------------------------------------------ nap

    def _nap_du_lieu(self):
        try:
            self._ch = chh.doc_cau_hinh(CONFIG_PATH)
        except Exception:
            self._ch = chh.CauHinh()
        self._dung_luoi_han_muc()
        self._ve(ve_lai_su_kien=True)

    def _cac_model(self) -> list[str]:
        return model_ui.cac_model_biet(self._ch)

    # ------------------------------------------------------------ ve

    def _ve(self, ve_lai_su_kien: bool = False):
        so = han_muc.so_theo_doi()
        anh = so.anh_chup()
        bay_gio = time.time()
        self._ve_bay_gio(anh, bay_gio)
        self._ve_bang_model(so, anh, bay_gio)
        if ve_lai_su_kien or self._dau_su_kien(anh["su_kien"]) != self._dau_su_kien_da_ve:
            self._ve_su_kien(anh["su_kien"])

    @staticmethod
    def _dau_su_kien(cac_su_kien: list[dict]):
        """
        Dau hieu "lich su da doi". KHONG dung len(): danh sach bi cat cung o
        SO_SU_KIEN_TOI_DA = 300, day du roi thi them su kien moi do dai van la 300 nen
        bang lich su dung im khong ve lai nua.
        """
        cuoi = cac_su_kien[-1] if cac_su_kien else None
        return len(cac_su_kien), (cuoi or {}).get("luc"), (cuoi or {}).get("loai")

    def _ve_bay_gio(self, anh: dict, bay_gio: float):
        cho = anh.get("dang_cho")
        if cho:
            con = han_muc.dem_nguoc(cho["den"] - bay_gio)
            ly_do = cho["ly_do"]
            if ly_do == "tpm":
                chu = tr("use_wait_tpm", con, cho["chi_tiet"], cho["model"])
            elif ly_do == "rpm":
                chu = tr("use_wait_rpm", con, cho["chi_tiet"], cho["model"])
            elif ly_do == "thu_lai":
                chu = tr("use_wait_retry", con, cho["model"], tr("use_err_" + cho["chi_tiet"]))
            else:
                chu = tr("use_wait_all_locked", con, han_muc.gio_may(cho["den"], bay_gio), cho["chi_tiet"])
            self.nhan_cho.setText(chu)
            if ly_do == "het_model":
                self.nhan_cho.setTextColor(*MAU_LOI)
            else:
                self.nhan_cho.setTextColor(QColor(0, 0, 0), QColor(255, 255, 255))
        else:
            self.nhan_cho.setText(tr("use_wait_none"))
            self.nhan_cho.setTextColor(*MAU_TOT)
        phan = []
        for m in self._ch.chuoi_model():
            mo_ta = model_ui.mo_ta_khoa(m)
            phan.append(f"{m} ({mo_ta})" if mo_ta else m)
        self.nhan_chuoi.setText(tr("use_chain", "  →  ".join(phan)))
        dat_lai = han_muc.luc_dat_lai_ngay(bay_gio)
        self.nhan_dat_lai.setText(tr("use_reset", han_muc.gio_may(dat_lai, bay_gio),
                                     han_muc.dem_nguoc(dat_lai - bay_gio)))

    def _ve_bang_model(self, so: han_muc.SoTheoDoi, anh: dict, bay_gio: float):
        cac_model = self._cac_model()
        if [self.bang_model.item(h, COT_MODEL).text() for h in range(self.bang_model.rowCount())
                if self.bang_model.item(h, COT_MODEL)] != cac_model:
            chon = self._model_dang_chon()
            self.bang_model.setRowCount(len(cac_model))
            for h, m in enumerate(cac_model):
                _dat_o(self.bang_model, h, COT_MODEL, m)
                if m == chon:
                    self.bang_model.selectRow(h)
        mau_loi, mau_tot = MAU_LOI[1 if isDarkTheme() else 0], MAU_TOT[1 if isDarkTheme() else 0]
        for h, m in enumerate(cac_model):
            du_lieu = anh["model"].get(m, {})
            khoa, den, ly_do, chi_tiet = so.trang_thai_khoa(m)
            if khoa and den is None:
                _dat_o(self.bang_model, h, COT_TRANG_THAI, tr("use_status_locked_manual", model_ui.ly_do_khoa(ly_do)),
                       mau_loi, chi_tiet)
            elif khoa:
                _dat_o(self.bang_model, h, COT_TRANG_THAI,
                       tr("use_status_locked", han_muc.gio_may(den, bay_gio), han_muc.dem_nguoc(den - bay_gio),
                          model_ui.ly_do_khoa(ly_do)), mau_loi, chi_tiet)
            else:
                _dat_o(self.bang_model, h, COT_TRANG_THAI, tr("use_status_ok"), mau_tot)
            gh = so.gioi_han(self._ch, m)
            hom_nay = int(du_lieu.get("yeu_cau_hom_nay") or 0)
            _dat_o(self.bang_model, h, COT_HOM_NAY, f"{hom_nay} / {gh.rpd}" if gh.rpd else str(hom_nay),
                   mau_loi if gh.rpd and hom_nay >= gh.rpd else None)
            _dat_o(self.bang_model, h, COT_TOKEN_HOM_NAY, _so(du_lieu.get("token_hom_nay")))
            da_dung = ga.dieu_tiet_cua_model(m).da_dung()
            _dat_o(self.bang_model, h, COT_TOKEN_PHUT, f"{_so(da_dung)} / {_so(gh.tpm)}" if gh.tpm else _so(da_dung))
            dem = du_lieu.get("dem_loi") or {}
            _dat_o(self.bang_model, h, COT_LOI, " · ".join(f"{tr('use_err_' + k)} {dem[k]}" for k in _LOAI_LOI
                                                          if dem.get(k)) or "0")
            loi_cuoi = du_lieu.get("loi_cuoi") or ""
            luc = du_lieu.get("luc_loi_cuoi")
            _dat_o(self.bang_model, h, COT_LOI_CUOI,
                   f"{datetime.fromtimestamp(luc):%H:%M} {loi_cuoi}".replace("\n", " ") if luc and loi_cuoi else "",
                   goi_y=loi_cuoi)
        self._cap_nhat_nut()

    def _ve_su_kien(self, cac_su_kien: list[dict]):
        self._dau_su_kien_da_ve = self._dau_su_kien(cac_su_kien)
        ds = list(reversed(cac_su_kien))[:200]
        self.bang_su_kien.setRowCount(len(ds))
        mau_loi = MAU_LOI[1 if isDarkTheme() else 0]
        for h, sk in enumerate(ds):
            loai = sk.get("loai", "")
            if loai == han_muc.SK_KHOA:
                ten = tr("use_ev_khoa", model_ui.ly_do_khoa(sk.get("ly_do", "")))
            elif loai == han_muc.SK_DOI_MODEL:
                ten = tr("use_ev_doi_model", sk.get("tu_model", "?"), sk.get("model", "?"))
                sk = dict(sk, noi_dung=model_ui.ly_do_khoa(sk.get("noi_dung", "")))
            elif loai == han_muc.SK_LOI:
                ten = tr("use_ev_loi", tr("use_err_" + sk.get("loai_loi", "khac")))
            else:
                ten = tr("use_ev_" + loai)
            mau = mau_loi if loai in (han_muc.SK_KHOA, han_muc.SK_LOI) else None
            luc = datetime.fromtimestamp(sk.get("luc") or 0)
            _dat_o(self.bang_su_kien, h, 0, luc.strftime("%d/%m %H:%M:%S"))
            _dat_o(self.bang_su_kien, h, 1, sk.get("model", ""))
            _dat_o(self.bang_su_kien, h, 2, ten, mau)
            _dat_o(self.bang_su_kien, h, 3, str(sk.get("noi_dung", "")).replace("\n", " "), goi_y=sk.get("noi_dung", ""))

    # ------------------------------------------------------------ nut

    def _model_dang_chon(self) -> str | None:
        hang = self.bang_model.currentRow()
        o = self.bang_model.item(hang, COT_MODEL) if hang >= 0 else None
        return o.text() if o and self.bang_model.selectedItems() else None

    def _cap_nhat_nut(self):
        m = self._model_dang_chon()
        self.nut_mo_khoa.setEnabled(bool(m) and han_muc.so_theo_doi().bi_khoa(m))

    def _mo_khoa(self):
        m = self._model_dang_chon()
        if not m:
            InfoBar.warning(tr("use_title"), tr("use_select_model"), parent=self, position=InfoBarPosition.TOP)
            return
        han_muc.so_theo_doi().mo_khoa(m)
        su_kien.han_muc_doi.emit()
        InfoBar.success(tr("use_title"), tr("use_unlocked", m), parent=self, position=InfoBarPosition.TOP)

    def _quen_han_muc(self):
        han_muc.so_theo_doi().quen_han_muc(self._model_dang_chon())
        self._dung_luoi_han_muc()
        su_kien.han_muc_doi.emit()

    def _dat_lai_bo_dem(self):
        han_muc.so_theo_doi().dat_lai_bo_dem(self._model_dang_chon())
        su_kien.han_muc_doi.emit()

    def _xoa_lich_su(self):
        han_muc.so_theo_doi().xoa_lich_su()
        self._ve(ve_lai_su_kien=True)

    # ------------------------------------------------------------ luoi han muc

    def _dung_luoi_han_muc(self, them: str | None = None):
        # Giu so dang sua tren man hinh khi chi them mot dong.
        cu = {m: ((d["tpm"].value(), d["rpm"].value(), d["rpd"].value()), d["khai_bao"])
              for m, d in self._hang_han_muc.items()} if them else {}
        while self.luoi.count():
            w = self.luoi.takeAt(0).widget()
            if w is not None:
                # An ngay: deleteLater chi xoa khi ve toi vong su kien, trong luc do dong cu van hien de len.
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self._hang_han_muc = {}
        for cot, key in enumerate(("use_col_model", "use_col_tpm", "use_col_rpm", "use_col_rpd", "use_col_learned")):
            self.luoi.addWidget(StrongBodyLabel(tr(key), self.khung_luoi), 0, cot)
        cac_model = list(dict.fromkeys([*self._ch.han_muc_model, *self._ch.chuoi_model(), *model_ui.MODEL_GOI_Y,
                                        *cu, *([them] if them else [])]))
        so = han_muc.so_theo_doi()
        for h, m in enumerate(cac_model, 1):
            khai_bao = self._ch.han_muc_model.get(m)
            gia_tri, da_khai_bao = cu.get(m) or (khai_bao or (0, 0, 0), bool(khai_bao) or m == them)
            nhan = BodyLabel(m if da_khai_bao else f"{m}  {tr('use_not_declared')}", self.khung_luoi)
            self.luoi.addWidget(nhan, h, 0)
            o = {}
            for cot, (truong, toi_da, buoc) in enumerate((("tpm", 100_000_000, 1000), ("rpm", 100_000, 1),
                                                          ("rpd", 10_000_000, 1)), 1):
                spin = SpinBox(self.khung_luoi)
                spin.setRange(0, toi_da)
                spin.setSingleStep(buoc)
                spin.setMinimumWidth(150)
                spin.setValue(int(gia_tri[cot - 1]))
                self.luoi.addWidget(spin, h, cot)
                o[truong] = spin
            hoc = so.hoc_duoc(m)
            self.luoi.addWidget(CaptionLabel(", ".join(f"{k} {v}" for k, v in hoc.items()) or "—", self.khung_luoi),
                                h, 4)
            nut_bo = TransparentToolButton(FluentIcon.DELETE, self.khung_luoi)
            nut_bo.setToolTip(tr("use_btn_remove_row"))
            nut_bo.setEnabled(da_khai_bao)
            nut_bo.clicked.connect(lambda _=False, m=m: self._bo_dong_han_muc(m))
            self.luoi.addWidget(nut_bo, h, 5)
            o["khai_bao"] = da_khai_bao
            self._hang_han_muc[m] = o
        self.luoi.setColumnStretch(4, 1)

    def _them_dong_han_muc(self):
        m = self.o_model_moi.text().strip()
        if not m:
            return
        self.o_model_moi.clear()
        self._dung_luoi_han_muc(them=m)

    def _bo_dong_han_muc(self, model: str):
        try:
            cio.xoa_key("HAN_MUC", [model], CONFIG_PATH)
        except Exception as e:
            InfoBar.error(tr("use_title"), str(e), parent=self, position=InfoBarPosition.TOP)
            return
        su_kien.cau_hinh_doi.emit(TEN_TRANG)
        self._nap_du_lieu()

    def _luu_han_muc(self):
        ghi = {}
        for m, o in self._hang_han_muc.items():
            so = (o["tpm"].value(), o["rpm"].value(), o["rpd"].value())
            # Model chua khai bao ma de ca ba so 0 thi khong ghi (van dung han muc mac dinh / Google bao).
            if o["khai_bao"] or any(so):
                ghi[("HAN_MUC", m)] = ", ".join(str(x) for x in so)
        try:
            cio.dat_nhieu_gia_tri(ghi, CONFIG_PATH)
            chh.doc_cau_hinh(CONFIG_PATH)
        except Exception as e:
            InfoBar.error(tr("use_title"), str(e), parent=self, position=InfoBarPosition.TOP)
            return
        su_kien.cau_hinh_doi.emit(TEN_TRANG)
        self._nap_du_lieu()
        InfoBar.success(tr("use_title"), tr("common_saved"), parent=self, position=InfoBarPosition.TOP)

    # ------------------------------------------------------------ ngon ngu

    def _dat_tieu_de_cot(self):
        self.bang_model.setHorizontalHeaderLabels([tr(k) for k in _TIEU_DE_COT])
        self.bang_su_kien.setHorizontalHeaderLabels([tr("use_col_time"), tr("use_col_model"), tr("use_col_event"),
                                                     tr("use_col_detail")])

    def _doi_ngon_ngu(self, _ma):
        self.tieu_de.setText(tr("use_title"))
        self.phu_de.setText(tr("use_subtitle"))
        for the in self._cac_the:
            the.doi_ngon_ngu()
        self.nut_mo_khoa.setText(tr("use_btn_unlock"))
        self.nut_quen.setText(tr("use_btn_forget"))
        self.nut_dat_lai.setText(tr("use_btn_reset_counts"))
        self.nut_nhat_ky.setText(tr("use_btn_open_log"))
        self.o_model_moi.setPlaceholderText(tr("use_add_model_placeholder"))
        self.nut_them.setText(tr("use_btn_add"))
        self.nut_luu_han_muc.setText(tr("common_save"))
        self.nut_xoa_lich_su.setText(tr("use_btn_clear_events"))
        self._dat_tieu_de_cot()
        self._dung_luoi_han_muc()
        self._ve(ve_lai_su_kien=True)
