from __future__ import annotations

import os
import time

from PySide6.QtCore import Qt, QStandardPaths, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QStackedWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    Action, BodyLabel, CaptionLabel, CardWidget, ComboBox, FluentIcon, IconWidget, InfoBar, InfoBarPosition,
    LineEdit, PlainTextEdit, PrimaryPushButton, ProgressBar, PushButton, RoundMenu, StrongBodyLabel,
    SwitchButton, TableWidget, TitleLabel, TransparentToolButton, isDarkTheme,
)

import cau_hinh as chh
import google_ai as ga
import han_muc
import model_ui
import nhan_dien
import presets
from i18n import bo_dich, tr
from log_bridge import QtLogHandler
from luong import LuongChuyenDoi, LuongDoThoiLuong
from paths import CONFIG_PATH
import config_io as cio
from su_kien import doc_trang_thai, ghi_trang_thai, su_kien
from widgets import MAU_GOI_Y, MAU_LOI, bool_txt, chu_goi_y, dich_cong_tac, mo_bang_windows, mo_thu_muc_chua

TEN_TRANG = "chuyen_doi"

COT_TEP, COT_THOI_LUONG, COT_TRANG_THAI, COT_TIEN_DO, COT_KET_QUA = range(5)

TT_CHO, TT_CHAY, TT_XONG, TT_BO_QUA, TT_LOI, TT_HUY = "cho", "chay", "xong", "bo_qua", "loi", "huy"
_CAN_CHAY = (TT_CHO, TT_LOI, TT_HUY)

_CACH_NHAN_DIEN = model_ui.CAC_CACH
_TEN_PRESET = {"gan_giang_vien": "audio_preset_near_lecturer", "gan_loa": "audio_preset_near_speaker",
               "giang_vien_di_lai": "audio_preset_moving", "tuy_chinh": "audio_preset_custom"}


def _hms(giay) -> str:
    if giay is None:
        return "—"
    giay = int(round(giay))
    return f"{giay // 3600}:{giay % 3600 // 60:02d}:{giay % 60:02d}"


class TrangChuyenDoi(QWidget):
    het_hang_doi = Signal(int, int, bool)
    can_mo_trang = Signal(str)          # ten trang can mo (vd khi chua co API key)

    def __init__(self, log_handler: QtLogHandler, parent=None):
        super().__init__(parent)
        self.setObjectName("conversionInterface")
        self.setAcceptDrops(True)
        self.luong: LuongChuyenDoi | None = None
        self.cac_luong_do: list[LuongDoThoiLuong] = []
        self._dong: dict[int, dict] = {}
        self._ma_ke_tiep = 1
        self._lan_chay: list[int] = []
        self._dang_nap = False

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(12)

        hang_tieu_de = QHBoxLayout()
        cot = QVBoxLayout()
        self.tieu_de = TitleLabel(tr("conv_title"), self)
        self.phu_de = chu_goi_y("conv_subtitle", self)
        cot.addWidget(self.tieu_de)
        cot.addWidget(self.phu_de)
        hang_tieu_de.addLayout(cot, 1)
        root.addLayout(hang_tieu_de)

        root.addWidget(self._tao_the_tep(), 3)
        root.addWidget(self._tao_the_nhanh())
        root.addWidget(self._tao_thanh_chay())

        self.nhan_hoat_dong = StrongBodyLabel(tr("conv_activity"), self)
        root.addWidget(self.nhan_hoat_dong)
        self.khung_hoat_dong = PlainTextEdit(self)
        self.khung_hoat_dong.setReadOnly(True)
        self.khung_hoat_dong.setMaximumBlockCount(500)
        self.khung_hoat_dong.setMinimumHeight(90)
        root.addWidget(self.khung_hoat_dong, 2)

        log_handler.dong_moi.connect(lambda dong, _lv: self.khung_hoat_dong.appendPlainText(dong))
        bo_dich.doi_ngon_ngu.connect(self._doi_ngon_ngu)
        su_kien.cau_hinh_doi.connect(lambda nguon: nguon != TEN_TRANG and self._nap_nhanh())
        su_kien.co_nhat_ky_doi.connect(self._dat_co_chu)
        su_kien.han_muc_doi.connect(self._nap_nhanh)
        self._nap_nhanh()
        self._cap_nhat_trang_thai_chay()

    # ------------------------------------------------------------ the tep

    def _tao_the_tep(self) -> CardWidget:
        the = CardWidget(self)
        lay = QVBoxLayout(the)
        lay.setContentsMargins(16, 12, 16, 12)

        hang = QHBoxLayout()
        self.nhan_tep = StrongBodyLabel(tr("conv_files"), the)
        self.nhan_tong = CaptionLabel("", the)
        hang.addWidget(self.nhan_tep)
        hang.addSpacing(8)
        hang.addWidget(self.nhan_tong)
        hang.addStretch(1)
        self.nut_them = PrimaryPushButton(FluentIcon.ADD, tr("conv_btn_add_files"), the)
        self.nut_them_thu_muc = PushButton(FluentIcon.FOLDER_ADD, tr("conv_btn_add_folder"), the)
        self.nut_bo = PushButton(FluentIcon.REMOVE_FROM, tr("conv_btn_remove"), the)
        self.nut_don = PushButton(FluentIcon.BROOM, tr("conv_btn_clear_done"), the)
        self.nut_xoa_het = TransparentToolButton(FluentIcon.DELETE, the)
        self.nut_xoa_het.setToolTip(tr("conv_btn_clear_all"))
        self.nut_them.clicked.connect(self._chon_file)
        self.nut_them_thu_muc.clicked.connect(self._chon_thu_muc)
        self.nut_bo.clicked.connect(self._bo_dong_chon)
        self.nut_don.clicked.connect(self._don_dong_xong)
        self.nut_xoa_het.clicked.connect(self._xoa_het)
        for n in (self.nut_them, self.nut_them_thu_muc, self.nut_bo, self.nut_don, self.nut_xoa_het):
            hang.addWidget(n)
        lay.addLayout(hang)

        self.chong = QStackedWidget(the)
        # Trang 0: chua co file
        trong = QWidget(self.chong)
        lay_trong = QVBoxLayout(trong)
        lay_trong.addStretch(1)
        icon = IconWidget(FluentIcon.MUSIC_FOLDER, trong)
        icon.setFixedSize(48, 48)
        lay_trong.addWidget(icon, 0, Qt.AlignHCenter)
        self.nhan_trong = BodyLabel(tr("conv_drop_hint"), trong)
        self.nhan_trong.setAlignment(Qt.AlignCenter)
        self.nhan_trong.setWordWrap(True)
        lay_trong.addWidget(self.nhan_trong)
        self.goi_y_trong = chu_goi_y("conv_drop_formats", trong, "")
        self.goi_y_trong.setAlignment(Qt.AlignCenter)
        lay_trong.addWidget(self.goi_y_trong)
        lay_trong.addStretch(1)
        self.chong.addWidget(trong)

        # Trang 1: bang
        self.bang = TableWidget(self.chong)
        self.bang.setColumnCount(5)
        self.bang.setBorderVisible(True)
        self.bang.setBorderRadius(6)
        self.bang.setWordWrap(False)
        self.bang.verticalHeader().hide()
        self.bang.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.bang.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.bang.setEditTriggers(QAbstractItemView.NoEditTriggers)
        dau = self.bang.horizontalHeader()
        dau.setSectionResizeMode(COT_TEP, QHeaderView.Stretch)
        dau.setSectionResizeMode(COT_THOI_LUONG, QHeaderView.ResizeToContents)
        dau.setSectionResizeMode(COT_TRANG_THAI, QHeaderView.Interactive)
        dau.setSectionResizeMode(COT_TIEN_DO, QHeaderView.Fixed)
        dau.setSectionResizeMode(COT_KET_QUA, QHeaderView.Stretch)
        self.bang.setColumnWidth(COT_TRANG_THAI, 230)
        self.bang.setColumnWidth(COT_TIEN_DO, 130)
        self.bang.setContextMenuPolicy(Qt.CustomContextMenu)
        self.bang.customContextMenuRequested.connect(self._menu_dong)
        self.bang.cellDoubleClicked.connect(self._nhan_dup)
        self.bang.itemSelectionChanged.connect(self._cap_nhat_nut)
        self._dat_tieu_de_cot()
        self.chong.addWidget(self.bang)
        lay.addWidget(self.chong, 1)
        return the

    def _dat_tieu_de_cot(self):
        self.bang.setHorizontalHeaderLabels([tr("conv_col_file"), tr("conv_col_duration"), tr("conv_col_status"),
                                             tr("conv_col_progress"), tr("conv_col_result")])

    # ------------------------------------------------------------ thiet lap nhanh

    def _tao_the_nhanh(self) -> CardWidget:
        the = CardWidget(self)
        lay = QVBoxLayout(the)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        hang_ra = QHBoxLayout()
        self.nhan_luu_vao = CaptionLabel(tr("conv_save_to"), the)
        self.o_thu_muc_ra = LineEdit(the)
        self.o_thu_muc_ra.setClearButtonEnabled(True)
        self.o_thu_muc_ra.setPlaceholderText(tr("conv_save_to_placeholder"))
        self.o_thu_muc_ra.editingFinished.connect(self._luu_thu_muc_ra)
        self.nut_chon_ra = PushButton(FluentIcon.FOLDER, tr("common_browse"), the)
        self.nut_chon_ra.clicked.connect(self._chon_thu_muc_ra)
        hang_ra.addWidget(self.nhan_luu_vao)
        hang_ra.addWidget(self.o_thu_muc_ra, 1)
        hang_ra.addWidget(self.nut_chon_ra)
        hang_ra.addSpacing(18)
        # Model chinh: model dang khoa (het han muc...) bi mo, khong chon duoc.
        self.nhan_model = CaptionLabel(tr("conv_model"), the)
        self.combo_model = ComboBox(the)
        self.combo_model.setMinimumWidth(250)
        self.combo_model.currentIndexChanged.connect(self._doi_model)
        hang_ra.addWidget(self.nhan_model)
        hang_ra.addWidget(self.combo_model)
        lay.addLayout(hang_ra)

        hang_cong_tac = QHBoxLayout()
        hang_cong_tac.setSpacing(6)

        def cong_tac(key):
            nhan = CaptionLabel(tr(key), the)
            sw = SwitchButton(the)
            dich_cong_tac(sw)
            hang_cong_tac.addWidget(nhan)
            hang_cong_tac.addWidget(sw)
            hang_cong_tac.addSpacing(18)
            return nhan, sw

        self.nhan_khu_on, self.sw_khu_on = cong_tac("conv_quick_denoise")
        self.nhan_cat_lang, self.sw_cat_lang = cong_tac("conv_quick_trim")
        self.nhan_nguoi_noi, self.sw_nguoi_noi = cong_tac("conv_quick_speakers")
        self.combo_cach = ComboBox(the)
        self.combo_cach.addItems([tr(k) for _, k in _CACH_NHAN_DIEN])
        self.combo_cach.setMinimumWidth(220)
        hang_cong_tac.addWidget(self.combo_cach)
        hang_cong_tac.addStretch(1)
        lay.addLayout(hang_cong_tac)

        self.nhan_tom_tat = chu_goi_y("", the)
        lay.addWidget(self.nhan_tom_tat)

        self.sw_khu_on.checkedChanged.connect(lambda v: self._dat_nhanh("XU_LY_AM_THANH", "khu_on", bool_txt(v)))
        self.sw_cat_lang.checkedChanged.connect(
            lambda v: self._dat_nhanh("XU_LY_AM_THANH", "cat_khoang_lang", bool_txt(v)))
        self.sw_nguoi_noi.checkedChanged.connect(self._bat_tat_nguoi_noi)
        self.combo_cach.currentIndexChanged.connect(
            lambda i: self._dat_nhanh("NGUOI_NOI", "cach_nhan_dien", _CACH_NHAN_DIEN[i][0]))
        return the

    def _nap_nhanh(self):
        try:
            ch = chh.doc_cau_hinh(CONFIG_PATH)
            thu_muc = cio.lay_gia_tri("KET_QUA", "thu_muc_ra", CONFIG_PATH) or ""
        except Exception as e:
            self.nhan_tom_tat.setText(f"config.txt: {e}")
            return
        self._dang_nap = True
        self.o_thu_muc_ra.setText(thu_muc)
        self.sw_khu_on.setChecked(ch.khu_on)
        self.sw_cat_lang.setChecked(ch.cat_khoang_lang)
        self.sw_nguoi_noi.setChecked(ch.nn_bat)
        model_ui.dien_combo_model(self.combo_model, model_ui.cac_model_biet(ch), ch.model)
        # Model khong phai *-transcribe thi khoa tach giong tren Google (gemini, ket_hop), va nguoc lai.
        for i, (cach, key) in enumerate(_CACH_NHAN_DIEN):
            hop = chh.model_hop_voi_cach(ch.model, cach)
            self.combo_cach.setItemEnabled(i, hop)
            self.combo_cach.setItemText(i, tr(key) + ("" if hop else "  🔒"))
        self.combo_cach.setCurrentIndex([c for c, _ in _CACH_NHAN_DIEN].index(ch.nn_cach))
        self.combo_cach.setEnabled(ch.nn_bat and not self.dang_chay())
        self.combo_model.setEnabled(not self.dang_chay())
        self._dang_nap = False
        self._dat_co_chu(ch.co_chu_nhat_ky)
        self.goi_y_trong.setText(tr("conv_drop_formats", " ".join(ch.duoi_file_nhan)))

        gia_tri_preset = {
            "target_dbfs": ch.target_dbfs, "silence_thresh_offset": ch.silence_thresh_offset,
            "min_silence_len": ch.min_silence_len, "keep_silence": ch.keep_silence,
            "noise_sample_sec": ch.noise_sample_sec, "bandpass_thap": ch.bandpass_low,
            "bandpass_cao": ch.bandpass_high, "ty_le_giam_on": ch.prop_decrease,
            "can_bang_am_luong_giay": ch.level_window_sec,
        }
        preset = tr(_TEN_PRESET[presets.nhan_dien_preset(gia_tri_preset)])
        chuoi = ch.chuoi_model()
        ten_model = ch.model + (f" ({tr('conv_summary_fallback', ', '.join(chuoi[1:]))})" if len(chuoi) > 1 else "")
        tom_tat = tr("conv_summary", ten_model, preset, f"{ch.phut_moi_doan:g}")
        if ch.nn_bat and ch.can_pyannote() and nhan_dien.loi_thieu_python(ch):
            tom_tat += "  ·  " + tr("conv_summary_no_runtime")
        loi = chh.loi_rang_buoc(ch)
        if loi:
            tom_tat += "\n" + tr("rb_transcribe" if ch.la_model_go_chu() else "rb_general")
        self.nhan_tom_tat.setText(tom_tat)
        self.nhan_tom_tat.setTextColor(*(MAU_LOI if loi else (MAU_GOI_Y, MAU_GOI_Y)))

    def _dat_nhanh(self, muc: str, key: str, gia_tri: str):
        if self._dang_nap:
            return
        try:
            cio.dat_gia_tri(muc, key, gia_tri, CONFIG_PATH)
        except Exception as e:
            InfoBar.error(tr("conv_title"), str(e), parent=self, position=InfoBarPosition.TOP)
            return
        su_kien.cau_hinh_doi.emit(TEN_TRANG)
        self._nap_nhanh()

    def _bat_tat_nguoi_noi(self, bat: bool):
        if self._dang_nap:
            return
        try:
            ch = chh.doc_cau_hinh(CONFIG_PATH)
        except Exception:
            self._dat_nhanh("NGUOI_NOI", "bat", bool_txt(bat))
            return
        # Cach da luu khong hop model (vd config cu) thi bat len la chuyen luon sang cach hop le.
        cach_moi = chh.cach_thay_the(ch.model, ch.nn_cach)
        if not bat or cach_moi == ch.nn_cach:
            self._dat_nhanh("NGUOI_NOI", "bat", bool_txt(bat))
            return
        try:
            cio.dat_nhieu_gia_tri({("NGUOI_NOI", "bat"): "true", ("NGUOI_NOI", "cach_nhan_dien"): cach_moi}, CONFIG_PATH)
        except Exception as e:
            InfoBar.error(tr("conv_title"), str(e), parent=self, position=InfoBarPosition.TOP)
            return
        su_kien.cau_hinh_doi.emit(TEN_TRANG)
        self._nap_nhanh()
        InfoBar.warning(tr("conv_title"), tr("rb_auto_switched", ch.model, model_ui.ten_cach(ch.nn_cach),
                                             model_ui.ten_cach(cach_moi)),
                        parent=self, position=InfoBarPosition.TOP, duration=10000)

    def _doi_model(self, i: int):
        if self._dang_nap or i < 0:
            return
        model = self.combo_model.itemData(i)
        try:
            ch = chh.doc_cau_hinh(CONFIG_PATH)
        except Exception as e:
            InfoBar.error(tr("conv_title"), f"config.txt: {e}", parent=self, position=InfoBarPosition.TOP)
            return
        if not model or model == ch.model:
            return
        gia_tri = {("GOOGLE_AI", "model"): model}
        cach_moi = chh.cach_thay_the(model, ch.nn_cach)
        if cach_moi != ch.nn_cach:
            gia_tri[("NGUOI_NOI", "cach_nhan_dien")] = cach_moi
        try:
            cio.dat_nhieu_gia_tri(gia_tri, CONFIG_PATH)
        except Exception as e:
            InfoBar.error(tr("conv_title"), str(e), parent=self, position=InfoBarPosition.TOP)
            return
        su_kien.cau_hinh_doi.emit(TEN_TRANG)
        self._nap_nhanh()
        if cach_moi != ch.nn_cach and ch.nn_bat:
            InfoBar.warning(tr("conv_title"), tr("rb_auto_switched", model, model_ui.ten_cach(ch.nn_cach),
                                                 model_ui.ten_cach(cach_moi)),
                            parent=self, position=InfoBarPosition.TOP, duration=10000)

    def _luu_thu_muc_ra(self):
        self._dat_nhanh("KET_QUA", "thu_muc_ra", self.o_thu_muc_ra.text().strip())

    def _chon_thu_muc_ra(self):
        chon = QFileDialog.getExistingDirectory(self, tr("conv_save_to"), self.o_thu_muc_ra.text().strip())
        if chon:
            self.o_thu_muc_ra.setText(os.path.normpath(chon))
            self._luu_thu_muc_ra()

    def _dat_co_chu(self, co: int):
        f = self.khung_hoat_dong.font()
        f.setFamilies(["Cascadia Mono", "Consolas"])
        f.setPixelSize(co)
        self.khung_hoat_dong.setFont(f)

    # ------------------------------------------------------------ thanh chay

    def _tao_thanh_chay(self) -> QWidget:
        khung = QWidget(self)
        lay = QHBoxLayout(khung)
        lay.setContentsMargins(0, 0, 0, 0)
        self.nut_bat_dau = PrimaryPushButton(FluentIcon.PLAY, tr("conv_btn_start"), khung)
        self.nut_dung = PushButton(FluentIcon.PAUSE, tr("conv_btn_stop"), khung)
        self.nut_bat_dau.setMinimumWidth(130)
        self.nut_bat_dau.clicked.connect(self._bat_dau)
        self.nut_dung.clicked.connect(self._dung)
        cot = QVBoxLayout()
        cot.setSpacing(4)
        self.nhan_tien_do = CaptionLabel("", khung)
        self.thanh_tong = ProgressBar(khung)
        self.thanh_tong.setRange(0, 1000)
        cot.addWidget(self.nhan_tien_do)
        cot.addWidget(self.thanh_tong)
        lay.addWidget(self.nut_bat_dau)
        lay.addWidget(self.nut_dung)
        lay.addSpacing(12)
        lay.addLayout(cot, 1)
        return khung

    def dang_chay(self) -> bool:
        return bool(self.luong and self.luong.isRunning())

    def _cap_nhat_trang_thai_chay(self):
        chay = self.dang_chay()
        self.nut_bat_dau.setEnabled(not chay)
        self.nut_dung.setEnabled(chay and not self.luong.dang_dung())
        for w in (self.sw_khu_on, self.sw_cat_lang, self.sw_nguoi_noi, self.combo_cach, self.o_thu_muc_ra,
                  self.nut_chon_ra, self.combo_model):
            w.setEnabled(not chay)
        if not chay:
            self.combo_cach.setEnabled(self.sw_nguoi_noi.isChecked())
        self._cap_nhat_nut()

    def _cap_nhat_nut(self):
        chon = self._ma_dang_chon()
        self.nut_bo.setEnabled(any(self._dong[m]["trang_thai"] != TT_CHAY for m in chon))
        self.nut_don.setEnabled(any(d["trang_thai"] in (TT_XONG, TT_BO_QUA) for d in self._dong.values()))
        self.nut_xoa_het.setEnabled(bool(self._dong) and not self.dang_chay())
        self.chong.setCurrentIndex(1 if self._dong else 0)
        tong = sum(d["thoi_luong"] or 0 for d in self._dong.values())
        self.nhan_tong.setText(tr("conv_total", len(self._dong), _hms(tong)) if self._dong else "")

    # ------------------------------------------------------------ them / bo file

    def _duoi_nhan(self) -> tuple:
        try:
            return chh.doc_cau_hinh(CONFIG_PATH).duoi_file_nhan
        except Exception:
            return chh.CauHinh().duoi_file_nhan

    def _thu_muc_mo_san(self) -> str:
        try:
            ch = chh.doc_cau_hinh(CONFIG_PATH)
        except Exception:
            ch = chh.CauHinh()
        if ch.nho_thu_muc_chon_file:
            cuoi = doc_trang_thai().get("thu_muc_chon_file_cuoi", "")
            if cuoi and os.path.isdir(cuoi):
                return cuoi
        if ch.thu_muc_chon_file and os.path.isdir(os.path.expandvars(ch.thu_muc_chon_file)):
            return os.path.expandvars(ch.thu_muc_chon_file)
        tai_ve = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        return tai_ve if tai_ve and os.path.isdir(tai_ve) else ""

    def _chon_file(self):
        loc = f"{tr('conv_filter_audio')} (*" + " *".join(self._duoi_nhan()) + f");;{tr('conv_filter_all')} (*)"
        ds, _ = QFileDialog.getOpenFileNames(self, tr("conv_btn_add_files"), self._thu_muc_mo_san(), loc)
        if ds:
            ghi_trang_thai(thu_muc_chon_file_cuoi=os.path.dirname(ds[0]))
            self.them_file(ds)

    def _chon_thu_muc(self):
        thu_muc = QFileDialog.getExistingDirectory(self, tr("conv_btn_add_folder"), self._thu_muc_mo_san())
        if thu_muc:
            ghi_trang_thai(thu_muc_chon_file_cuoi=thu_muc)
            self.them_file([thu_muc])

    def _mo_rong(self, ds: list[str]) -> list[str]:
        """Thu muc -> cac file audio ben trong (co the ca thu muc con, theo cai dat)."""
        try:
            ch = chh.doc_cau_hinh(CONFIG_PATH)
        except Exception:
            ch = chh.CauHinh()
        kq = []
        for p in ds:
            if os.path.isdir(p):
                if ch.them_thu_muc_con:
                    for goc, _, cac_ten in os.walk(p):
                        kq += [os.path.join(goc, t) for t in sorted(cac_ten)]
                else:
                    kq += [os.path.join(p, t) for t in sorted(os.listdir(p))]
            else:
                kq.append(p)
        return [p for p in kq if os.path.isfile(p) and os.path.splitext(p)[1].lower() in ch.duoi_file_nhan]

    def them_file(self, ds: list[str]):
        hien_co = {os.path.normcase(os.path.abspath(d["duong_dan"])) for d in self._dong.values()}
        moi = []
        for p in self._mo_rong(ds):
            khoa = os.path.normcase(os.path.abspath(p))
            if khoa in hien_co:
                continue
            hien_co.add(khoa)
            moi.append((self._them_dong(os.path.abspath(p)), p))
        if ds and not moi:
            InfoBar.warning(tr("conv_title"), tr("conv_no_new_files"), parent=self, position=InfoBarPosition.TOP)
            return
        if self.dang_chay():
            for ma, p in moi:
                self.luong.them(ma, p)
                self._lan_chay.append(ma)
        if moi:
            try:
                ffmpeg = chh.doc_cau_hinh(CONFIG_PATH).duong_dan_ffmpeg
            except Exception:
                ffmpeg = "auto"
            luong = LuongDoThoiLuong(moi, ffmpeg, self)
            luong.co_ket_qua.connect(self._co_thoi_luong)
            luong.finished.connect(lambda l=luong: self.cac_luong_do.remove(l) if l in self.cac_luong_do else None)
            self.cac_luong_do.append(luong)
            luong.start()
        self._cap_nhat_nut()

    def _them_dong(self, duong_dan: str) -> int:
        ma = self._ma_ke_tiep
        self._ma_ke_tiep += 1
        self._dong[ma] = {"ma": ma, "duong_dan": duong_dan, "trang_thai": TT_CHO, "chi_tiet": "",
                          "ty_le": 0.0, "file_ra": None, "thoi_luong": None}
        hang = self.bang.rowCount()
        self.bang.insertRow(hang)
        o_ten = QTableWidgetItem(os.path.basename(duong_dan))
        o_ten.setData(Qt.UserRole, ma)
        o_ten.setToolTip(duong_dan)
        self.bang.setItem(hang, COT_TEP, o_ten)
        self.bang.setItem(hang, COT_THOI_LUONG, QTableWidgetItem("…"))
        self.bang.setItem(hang, COT_TRANG_THAI, QTableWidgetItem(""))
        thanh = ProgressBar()
        thanh.setRange(0, 1000)
        khung = QWidget()
        lay = QHBoxLayout(khung)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.addWidget(thanh)
        self.bang.setCellWidget(hang, COT_TIEN_DO, khung)
        self._dong[ma]["thanh"] = thanh
        self.bang.setItem(hang, COT_KET_QUA, QTableWidgetItem(""))
        self._ve_dong(ma)
        return ma

    def _hang_cua(self, ma: int) -> int | None:
        for h in range(self.bang.rowCount()):
            o = self.bang.item(h, COT_TEP)
            if o and o.data(Qt.UserRole) == ma:
                return h
        return None

    def _ma_dang_chon(self) -> list[int]:
        hang = sorted({i.row() for i in self.bang.selectedIndexes()})
        return [self.bang.item(h, COT_TEP).data(Qt.UserRole) for h in hang if self.bang.item(h, COT_TEP)]

    def _bo_ma(self, ma: int):
        if self._dong.get(ma, {}).get("trang_thai") == TT_CHAY:
            return
        if self.dang_chay():
            self.luong.bo(ma)
        h = self._hang_cua(ma)
        if h is not None:
            self.bang.removeRow(h)
        self._dong.pop(ma, None)
        if ma in self._lan_chay:
            self._lan_chay.remove(ma)

    def _bo_dong_chon(self):
        for ma in self._ma_dang_chon():
            self._bo_ma(ma)
        self._cap_nhat_nut()

    def _don_dong_xong(self):
        for ma in [m for m, d in self._dong.items() if d["trang_thai"] in (TT_XONG, TT_BO_QUA)]:
            self._bo_ma(ma)
        self._cap_nhat_nut()

    def _xoa_het(self):
        if self.dang_chay():
            return
        self.bang.setRowCount(0)
        self._dong.clear()
        self._cap_nhat_nut()

    def _co_thoi_luong(self, ma: int, giay: float):
        if ma in self._dong:
            self._dong[ma]["thoi_luong"] = giay
            self._ve_dong(ma)
            self._cap_nhat_nut()

    # ------------------------------------------------------------ ve mot dong

    def _chu_trang_thai(self, d: dict) -> str:
        tt = d["trang_thai"]
        if tt == TT_CHAY:
            return d["chi_tiet"] or tr("conv_status_running")
        if tt == TT_LOI:
            return tr("conv_status_error") + (f": {d['chi_tiet']}" if d["chi_tiet"] else "")
        return tr({TT_CHO: "conv_status_waiting", TT_XONG: "conv_status_done", TT_BO_QUA: "conv_status_skipped",
                   TT_HUY: "conv_status_stopped"}[tt])

    def _ve_dong(self, ma: int):
        d = self._dong.get(ma)
        h = self._hang_cua(ma)
        if d is None or h is None:
            return
        self.bang.item(h, COT_THOI_LUONG).setText(_hms(d["thoi_luong"]) if d["thoi_luong"] else "…")
        o_tt = self.bang.item(h, COT_TRANG_THAI)
        o_tt.setText(self._chu_trang_thai(d))
        o_tt.setToolTip(o_tt.text())
        toi = isDarkTheme()
        mau = {TT_XONG: "#6ccb5f" if toi else "#0f7b0f", TT_LOI: "#ff99a4" if toi else "#c42b1c",
               TT_BO_QUA: "#8a8a8a", TT_HUY: "#8a8a8a"}.get(d["trang_thai"])
        o_tt.setForeground(QColor(mau) if mau else QColor("#ffffff" if toi else "#000000"))
        d["thanh"].setValue(int(d["ty_le"] * 1000))
        d["thanh"].setError(d["trang_thai"] == TT_LOI)
        o_kq = self.bang.item(h, COT_KET_QUA)
        o_kq.setText(os.path.basename(d["file_ra"]) if d["file_ra"] else "")
        o_kq.setToolTip(d["file_ra"] or "")

    # ------------------------------------------------------------ menu dong

    def _menu_dong(self, vi_tri):
        h = self.bang.rowAt(vi_tri.y())
        if h < 0:
            return
        ma = self.bang.item(h, COT_TEP).data(Qt.UserRole)
        d = self._dong[ma]
        menu = RoundMenu(parent=self)
        mo_kq = Action(FluentIcon.DOCUMENT, tr("conv_menu_open_result"))
        mo_kq.setEnabled(bool(d["file_ra"] and os.path.exists(d["file_ra"])))
        mo_kq.triggered.connect(lambda: mo_bang_windows(d["file_ra"]))
        mo_thu_muc = Action(FluentIcon.FOLDER, tr("conv_menu_open_folder"))
        mo_thu_muc.triggered.connect(lambda: mo_thu_muc_chua(d["file_ra"] or d["duong_dan"]))
        nghe = Action(FluentIcon.PLAY, tr("conv_menu_play"))
        nghe.triggered.connect(lambda: mo_bang_windows(d["duong_dan"]))
        lam_lai = Action(FluentIcon.SYNC, tr("conv_menu_redo"))
        lam_lai.setEnabled(d["trang_thai"] in (TT_XONG, TT_BO_QUA, TT_LOI, TT_HUY))
        lam_lai.triggered.connect(lambda: self._dat_lai(ma))
        bo = Action(FluentIcon.REMOVE_FROM, tr("conv_menu_remove"))
        bo.setEnabled(d["trang_thai"] != TT_CHAY)
        bo.triggered.connect(lambda: (self._bo_ma(ma), self._cap_nhat_nut()))
        for a in (mo_kq, mo_thu_muc, nghe):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(lam_lai)
        menu.addAction(bo)
        menu.exec(self.bang.viewport().mapToGlobal(vi_tri))

    def _dat_lai(self, ma: int):
        d = self._dong[ma]
        d.update(trang_thai=TT_CHO, chi_tiet="", ty_le=0.0, file_ra=None)
        self._ve_dong(ma)
        if self.dang_chay():
            self.luong.them(ma, d["duong_dan"])
            self._lan_chay.append(ma)

    def _nhan_dup(self, h: int, _cot: int):
        ma = self.bang.item(h, COT_TEP).data(Qt.UserRole)
        d = self._dong[ma]
        mo_bang_windows(d["file_ra"] if d["file_ra"] and os.path.exists(d["file_ra"]) else d["duong_dan"])

    # ------------------------------------------------------------ chay

    def _bat_dau(self):
        if self.dang_chay():
            return
        cho = [m for m in self._thu_tu_dong() if self._dong[m]["trang_thai"] in _CAN_CHAY]
        if not cho:
            InfoBar.warning(tr("conv_title"), tr("conv_nothing_to_do"), parent=self, position=InfoBarPosition.TOP)
            return
        try:
            ch = chh.doc_cau_hinh(CONFIG_PATH)
        except Exception as e:
            InfoBar.error(tr("conv_title"), f"config.txt: {e}", parent=self, position=InfoBarPosition.TOP)
            return
        if not ga.lay_api_key():
            thanh = InfoBar.error(tr("conv_title"), tr("conv_no_key"), parent=self,
                                  position=InfoBarPosition.TOP, duration=8000)
            nut = PushButton(tr("conv_go_google"))
            nut.clicked.connect(lambda: self.can_mo_trang.emit("google"))
            thanh.addWidget(nut)
            return
        loi = chh.loi_rang_buoc(ch)
        if loi:
            thanh = InfoBar.error(tr("conv_title"), tr("conv_constraint", loi), parent=self,
                                  position=InfoBarPosition.TOP, duration=10000)
            nut = PushButton(tr("conv_go_speakers"))
            nut.clicked.connect(lambda: self.can_mo_trang.emit("nguoi_noi"))
            thanh.addWidget(nut)
            return
        if not self._con_model_dung_duoc(ch):
            return
        if ch.can_pyannote():
            loi = nhan_dien.loi_thieu_python(ch)
            if loi:
                thanh = InfoBar.error(tr("conv_title"), tr("conv_no_runtime"), parent=self,
                                      position=InfoBarPosition.TOP, duration=8000)
                nut = PushButton(tr("conv_go_speakers"))
                nut.clicked.connect(lambda: self.can_mo_trang.emit("nguoi_noi"))
                thanh.addWidget(nut)
                return

        self.luong = LuongChuyenDoi(self)
        self._lan_chay = list(cho)
        for ma in cho:
            d = self._dong[ma]
            d.update(trang_thai=TT_CHO, chi_tiet="", ty_le=0.0)
            self._ve_dong(ma)
            self.luong.them(ma, d["duong_dan"])
        self.luong.bat_dau_file.connect(self._bat_dau_file)
        self.luong.tien_do.connect(self._tien_do)
        self.luong.xong_file.connect(self._xong_file)
        self.luong.loi_file.connect(self._loi_file)
        self.luong.huy_file.connect(self._huy_file)
        self.luong.het.connect(self._het)
        self.luong.finished.connect(self._cap_nhat_trang_thai_chay)
        self.luong.start()
        self._cap_nhat_trang_thai_chay()
        self._cap_nhat_tong()

    def _con_model_dung_duoc(self, ch: chh.CauHinh) -> bool:
        """Moi model trong chuoi deu khoa lau hon muc cho phep thi bao ngay, khong bat dau."""
        so = han_muc.so_theo_doi()
        cac_luc = []
        for m in ch.chuoi_model():
            khoa, den, _, _ = so.trang_thai_khoa(m)
            if not khoa:
                return True
            cac_luc.append(den)
        mo_som = min((d for d in cac_luc if d is not None), default=None)
        if mo_som is not None and mo_som - time.time() <= ch.cho_toi_da_khi_het_model_phut * 60:
            return True
        mo_ta = "; ".join(f"{m} {model_ui.mo_ta_khoa(m)}" for m in ch.chuoi_model())
        thanh = InfoBar.error(tr("conv_title"), tr("conv_all_locked", mo_ta), parent=self,
                              position=InfoBarPosition.TOP, duration=12000)
        nut = PushButton(tr("conv_go_usage"))
        nut.clicked.connect(lambda: self.can_mo_trang.emit("han_muc"))
        thanh.addWidget(nut)
        return False

    def _thu_tu_dong(self) -> list[int]:
        return [self.bang.item(h, COT_TEP).data(Qt.UserRole) for h in range(self.bang.rowCount())]

    def _dung(self):
        if self.dang_chay():
            self.luong.yeu_cau_dung()
            self.nhan_tien_do.setText(tr("conv_stopping"))
            self._cap_nhat_trang_thai_chay()

    def yeu_cau_dung_va_cho(self, ms: int = 15000):
        """
        Goi luc thoat app. Dang tai mot doan len Google thi khong cat ngang duoc;
        qua thoi gian cho thi terminate(), vi de QThread con song luc Python don doi
        tuong la app do ngay khi thoat. Cat ngang khong hong gi: cac doan da xong
        van nam trong thu muc tam, lan sau lam tiep.
        """
        for luong in self.cac_luong_do:
            luong.wait(3000)
        if not self.dang_chay():
            return
        self.luong.yeu_cau_dung()
        if not self.luong.wait(ms):
            self.luong.terminate()
            self.luong.wait(3000)

    def _bat_dau_file(self, ma: int):
        if ma in self._dong:
            self._dong[ma].update(trang_thai=TT_CHAY, chi_tiet=tr("conv_stage_prepare"), ty_le=0.0)
            self._ve_dong(ma)
            h = self._hang_cua(ma)
            if h is not None:
                self.bang.scrollToItem(self.bang.item(h, COT_TEP))
        self._cap_nhat_tong()

    def _tien_do(self, ma: int, giai_doan: str, ty_le: float, ts: dict):
        d = self._dong.get(ma)
        if d is None:
            return
        if giai_doan == "lam_sach":
            chi_tiet = tr("conv_stage_clean", ts["buoc"]) if "buoc" in ts else tr("conv_stage_clean_short")
        elif giai_doan == "nguoi_noi":
            buoc = ts.get("buoc")
            chi_tiet = tr("conv_stage_diarize") + (f" · {tr('diar_step_' + buoc)}" if buoc else "")
        elif giai_doan == "go_chu":
            if ts.get("model"):
                chi_tiet = tr("conv_stage_transcribe_model", ts.get("doan", "?"), ts.get("tong", "?"), ts["model"])
            else:
                chi_tiet = tr("conv_stage_transcribe", ts.get("doan", "?"), ts.get("tong", "?"))
        else:
            chi_tiet = tr("conv_stage_merge")
        d.update(trang_thai=TT_CHAY, chi_tiet=chi_tiet, ty_le=ty_le)
        self._ve_dong(ma)
        self._cap_nhat_tong()

    def _xong_file(self, ma: int, kq):
        d = self._dong.get(ma)
        if d is None:
            return
        d.update(trang_thai=TT_BO_QUA if kq.bo_qua else TT_XONG, chi_tiet="", ty_le=1.0, file_ra=kq.file_ra)
        self._ve_dong(ma)
        self._cap_nhat_tong()
        self._cap_nhat_nut()
        if kq.bo_qua or not kq.file_ra:
            return
        try:
            mo = chh.doc_cau_hinh(CONFIG_PATH).mo_khi_xong
        except Exception:
            mo = "khong"
        if mo == "file":
            mo_bang_windows(kq.file_ra)
        elif mo == "thu_muc":
            mo_thu_muc_chua(kq.file_ra)

    def _loi_file(self, ma: int, loi: str):
        d = self._dong.get(ma)
        if d is None:
            return
        d.update(trang_thai=TT_LOI, chi_tiet=loi if len(loi) <= 160 else loi[:157] + "...")
        self._ve_dong(ma)
        self._cap_nhat_tong()

    def _huy_file(self, ma: int):
        d = self._dong.get(ma)
        if d is None:
            return
        d.update(trang_thai=TT_HUY if d["trang_thai"] == TT_CHAY else TT_CHO, chi_tiet="")
        self._ve_dong(ma)

    def _het(self, so_xong: int, so_loi: int, bi_dung: bool):
        if bi_dung:
            self.nhan_tien_do.setText(tr("conv_stopped_summary", so_xong, so_loi))
        else:
            self.nhan_tien_do.setText(tr("conv_done_summary", so_xong, so_loi))
            if so_loi == 0:
                self.thanh_tong.setValue(1000)
        ham = InfoBar.warning if so_loi else InfoBar.success
        ham(tr("conv_title"), self.nhan_tien_do.text(), parent=self, position=InfoBarPosition.TOP, duration=6000)
        self.het_hang_doi.emit(so_xong, so_loi, bi_dung)
        self._cap_nhat_nut()

    def _cap_nhat_tong(self):
        ds = [self._dong[m] for m in self._lan_chay if m in self._dong]
        if not ds:
            return
        tong = sum(1.0 if d["trang_thai"] in (TT_XONG, TT_BO_QUA, TT_LOI) else d["ty_le"] for d in ds)
        self.thanh_tong.setValue(int(1000 * tong / len(ds)))
        dang = next((d for d in ds if d["trang_thai"] == TT_CHAY), None)
        so_xong = sum(1 for d in ds if d["trang_thai"] in (TT_XONG, TT_BO_QUA, TT_LOI))
        if dang and not (self.luong and self.luong.dang_dung()):
            self.nhan_tien_do.setText(tr("conv_progress", min(len(ds), so_xong + 1), len(ds),
                                         os.path.basename(dang["duong_dan"]), dang["chi_tiet"],
                                         int(100 * tong / len(ds))))

    # ------------------------------------------------------------ keo tha

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        ds = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if ds:
            e.acceptProposedAction()
            self.them_file(ds)

    # ------------------------------------------------------------ ngon ngu

    def _doi_ngon_ngu(self, _ma):
        self.tieu_de.setText(tr("conv_title"))
        self.phu_de.setText(tr("conv_subtitle"))
        self.nhan_tep.setText(tr("conv_files"))
        self.nut_them.setText(tr("conv_btn_add_files"))
        self.nut_them_thu_muc.setText(tr("conv_btn_add_folder"))
        self.nut_bo.setText(tr("conv_btn_remove"))
        self.nut_don.setText(tr("conv_btn_clear_done"))
        self.nut_xoa_het.setToolTip(tr("conv_btn_clear_all"))
        self.nhan_trong.setText(tr("conv_drop_hint"))
        self._dat_tieu_de_cot()
        self.nhan_luu_vao.setText(tr("conv_save_to"))
        self.o_thu_muc_ra.setPlaceholderText(tr("conv_save_to_placeholder"))
        self.nut_chon_ra.setText(tr("common_browse"))
        self.nhan_model.setText(tr("conv_model"))
        self.nhan_khu_on.setText(tr("conv_quick_denoise"))
        self.nhan_cat_lang.setText(tr("conv_quick_trim"))
        self.nhan_nguoi_noi.setText(tr("conv_quick_speakers"))
        for sw in (self.sw_khu_on, self.sw_cat_lang, self.sw_nguoi_noi):
            dich_cong_tac(sw)
        i = self.combo_cach.currentIndex()
        self.combo_cach.blockSignals(True)
        self.combo_cach.clear()
        self.combo_cach.addItems([tr(k) for _, k in _CACH_NHAN_DIEN])
        self.combo_cach.setCurrentIndex(i)
        self.combo_cach.blockSignals(False)
        self.nut_bat_dau.setText(tr("conv_btn_start"))
        self.nut_dung.setText(tr("conv_btn_stop"))
        self.nhan_hoat_dong.setText(tr("conv_activity"))
        self._nap_nhanh()
        for ma in self._dong:
            self._ve_dong(ma)
        self._cap_nhat_nut()
