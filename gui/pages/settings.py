from __future__ import annotations

import dataclasses
import os
import shutil
import sys
from datetime import datetime

from PySide6 import __version__ as PYSIDE_VERSION
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout
from qfluentwidgets import (
    CaptionLabel, ColorPickerButton, FluentIcon, InfoBar, InfoBarPosition, LineEdit, MessageBox, PushButton,
    SpinBox, Theme, TitleLabel, setTheme, setThemeColor,
)

import am_thanh_io
import cau_hinh as chh
import chuyen_doi as cd
import config_io as cio
from duong_dan import FFMPEG_CUC_BO, PYTHON_NGUOI_NOI, RUNTIME_DIR
from i18n import bo_dich, dat_ngon_ngu, tr
from paths import CONFIG_MAU, CONFIG_PATH, DATA_DIR, DIR_CHUNG, PHIEN_BAN, dam_bao_du_lieu
from su_kien import su_kien
from widgets import (
    MAU_LOI, Hang, HangCombo, HangDuongDan, HangSwitch, TheNhom, TrangCuon, bool_txt, chu_goi_y, mo_bang_windows,
)

TEN_TRANG = "cai_dat"
MAU_NHAN_MAC_DINH = "#009faa"

CHU_DE = {"auto": Theme.AUTO, "light": Theme.LIGHT, "dark": Theme.DARK}


def ap_dung_giao_dien(ch: chh.CauHinh):
    """Chu de va mau nhan theo cau hinh. main.py goi luc mo app."""
    setTheme(CHU_DE.get(ch.chu_de, Theme.AUTO), lazy=True)
    mau = QColor(ch.mau_nhan) if ch.mau_nhan else QColor(MAU_NHAN_MAC_DINH)
    setThemeColor(mau if mau.isValid() else QColor(MAU_NHAN_MAC_DINH), lazy=True)


class TrangCaiDat(TrangCuon):
    can_khoi_dong_lai = Signal()
    doi_mica = Signal(bool)

    def __init__(self, parent=None):
        super().__init__("settingsInterface", parent)
        khung, root = self.khung, self.root
        self._dang_nap = True
        self._cho_nap = False
        self._cac_the: list[TheNhom] = []

        self.tieu_de = TitleLabel(tr("set_title"), khung)
        root.addWidget(self.tieu_de)

        # ---- Giao dien ----
        the = self._the("set_section_appearance")
        self.hang_ngon_ngu = the.them(HangCombo("set_language", [("vi", "lang_vi"), ("en", "lang_en")], the))
        self.hang_chu_de = the.them(HangCombo("set_theme", [("auto", "set_theme_auto"), ("light", "set_theme_light"),
                                                            ("dark", "set_theme_dark")], the))
        hang_mau = QHBoxLayout()
        self.o_mau = ColorPickerButton(QColor(MAU_NHAN_MAC_DINH), tr("set_accent"), the)
        self.nut_mau_mac_dinh = PushButton(FluentIcon.RETURN, tr("common_restore_default"), the)
        hang_mau.addWidget(self.o_mau)
        hang_mau.addWidget(self.nut_mau_mac_dinh)
        hang_mau.addStretch(1)
        khung_mau = self._hang_tu_layout("set_accent", hang_mau, the)
        the.them(khung_mau)
        self.hang_mica = the.them(HangSwitch("set_mica", "set_mica_hint", the))
        self.hang_ty_le = the.them(HangCombo("set_scale", [(v, "set_scale_auto" if v == "auto" else None)
                                                           for v in chh.CAC_TY_LE], the))
        for i, (v, _) in enumerate(self.hang_ty_le.cac_muc):
            if v != "auto":
                self.hang_ty_le.combo.setItemText(i, f"{float(v) * 100:.0f}%")
        self.o_co_chu = SpinBox()
        self.o_co_chu.setRange(8, 32)
        self.hang_co_chu = the.them(Hang("set_log_font", self.o_co_chu, the))
        self.hang_nho_cua_so = the.them(HangSwitch("set_remember_window", parent=the))

        # ---- Ban go chu ----
        the = self._the("set_section_output")
        self.hang_thu_muc_ra = the.them(HangDuongDan("set_output_folder", the, "thu_muc", "conv_save_to_placeholder"))
        self.o_mau_ten = LineEdit()
        self.o_mau_ten.setMinimumWidth(300)
        self.hang_mau_ten = the.them(Hang("set_name_template", self.o_mau_ten, the))
        self.xem_truoc_ten = chu_goi_y("", the)
        the.lay.addWidget(self.xem_truoc_ten)
        self.hang_duoi = the.them(HangCombo("set_extension", [(".txt", None), (".md", None)], the))
        self.hang_trung_ten = the.them(HangCombo("set_on_conflict", [
            ("danh_so", "set_conflict_number"), ("ghi_de", "set_conflict_overwrite"),
            ("bo_qua", "set_conflict_skip")], the, rong=300))
        self.hang_ma_hoa = the.them(HangCombo("set_encoding", [("utf-8", "set_encoding_utf8"),
                                                               ("utf-8-sig", "set_encoding_bom")], the, rong=300))
        self.hang_xuong_dong = the.them(HangCombo("set_newline", [("crlf", "set_newline_crlf"),
                                                                  ("lf", "set_newline_lf")], the))
        self.hang_mo_khi_xong = the.them(HangCombo("set_open_when_done", [
            ("khong", "set_open_nothing"), ("file", "set_open_file"), ("thu_muc", "set_open_folder")], the))
        self.hang_phan_dau = the.them(HangSwitch("set_header", "set_header_hint", the))
        self.hang_danh_dau = the.them(HangSwitch("set_chunk_markers", "set_chunk_markers_hint", the))
        self.hang_luu_ban_do = the.them(HangSwitch("set_save_map", "set_save_map_hint", the))
        self.hang_luu_sach = the.them(HangSwitch("set_save_clean", "set_save_clean_hint", the))

        # ---- Hang doi ----
        the = self._the("set_section_queue")
        self.hang_khi_loi = the.them(HangCombo("set_on_error", [("tiep_tuc", "set_on_error_continue"),
                                                                ("dung", "set_on_error_stop")], the, rong=300))
        self.hang_thong_bao = the.them(HangSwitch("set_notify", "set_notify_hint", the))
        self.hang_am_bao = the.them(HangSwitch("set_sound", parent=the))
        self.hang_chong_ngu = the.them(HangSwitch("set_keep_awake", "set_keep_awake_hint", the))
        self.hang_nho_thu_muc = the.them(HangSwitch("set_remember_folder", parent=the))
        self.hang_thu_muc_mo = the.them(HangDuongDan("set_open_dialog_folder", the, "thu_muc",
                                                     "set_open_dialog_folder_placeholder"))
        self.hang_thu_muc_con = the.them(HangSwitch("set_subfolders", parent=the))
        self.o_duoi_nhan = LineEdit()
        self.o_duoi_nhan.setMinimumWidth(360)
        self.hang_duoi_nhan = the.them(Hang("set_accepted_ext", self.o_duoi_nhan, the))
        self.o_duoi_video = LineEdit()
        self.o_duoi_video.setMinimumWidth(360)
        self.hang_duoi_video = the.them(Hang("video_ext", self.o_duoi_video, the))

        # ---- He thong ----
        the = self._the("set_section_system")
        self.hang_tam = the.them(HangDuongDan("set_temp_folder", the, "thu_muc", "set_temp_placeholder"))
        hang_don = QHBoxLayout()
        self.nut_don_tam = PushButton(FluentIcon.BROOM, tr("set_btn_clean_temp"), the)
        self.nut_mo_tam = PushButton(FluentIcon.FOLDER, tr("set_btn_open_temp"), the)
        self.nut_don_tam.clicked.connect(self._don_tam)
        self.nut_mo_tam.clicked.connect(self._mo_tam)
        self.nhan_tam = CaptionLabel("", the)
        hang_don.addWidget(self.nut_don_tam)
        hang_don.addWidget(self.nut_mo_tam)
        hang_don.addWidget(self.nhan_tam, 1)
        the.lay.addLayout(hang_don)
        self.hang_xoa_tam = the.them(HangSwitch("set_delete_temp", "set_delete_temp_hint", the))
        self.hang_ffmpeg = the.them(HangDuongDan("set_ffmpeg", the, "ffmpeg.exe (ffmpeg.exe)", "nn_auto"))
        self.nhan_ffmpeg = chu_goi_y("", the)
        the.lay.addWidget(self.nhan_ffmpeg)
        self.hang_muc_log = the.them(HangCombo("set_log_level", [("INFO", "set_log_info"),
                                                                 ("DEBUG", "set_log_debug")], the))
        self.o_log_mb = SpinBox()
        self.o_log_mb.setRange(1, 100)
        self.o_log_so = SpinBox()
        self.o_log_so.setRange(0, 50)
        self.hang_log_mb = the.them(Hang("set_log_size", self.o_log_mb, the))
        self.hang_log_so = the.them(Hang("set_log_count", self.o_log_so, the))

        # ---- Thong tin ----
        the = self._the("set_section_about")
        self.nhan_phien_ban = CaptionLabel("", the)
        self.nhan_phien_ban.setWordWrap(True)
        self.nhan_phien_ban.setTextInteractionFlags(Qt.TextSelectableByMouse)
        the.lay.addWidget(self.nhan_phien_ban)
        hang_nut = QHBoxLayout()
        self.nut_mo_du_lieu = PushButton(FluentIcon.FOLDER, tr("set_btn_open_data"), the)
        self.nut_mo_config = PushButton(FluentIcon.EDIT, tr("set_btn_open_config"), the)
        self.nut_khoi_dong_lai = PushButton(FluentIcon.UPDATE, tr("set_btn_restart"), the)
        self.nut_mac_dinh = PushButton(FluentIcon.CANCEL, tr("set_btn_reset"), the)
        self.nut_mo_du_lieu.clicked.connect(lambda: mo_bang_windows(DATA_DIR))
        self.nut_mo_config.clicked.connect(lambda: mo_bang_windows(CONFIG_PATH))
        self.nut_khoi_dong_lai.clicked.connect(self.can_khoi_dong_lai.emit)
        self.nut_mac_dinh.clicked.connect(self._khoi_phuc_mac_dinh)
        for n in (self.nut_mo_du_lieu, self.nut_mo_config, self.nut_khoi_dong_lai, self.nut_mac_dinh):
            hang_nut.addWidget(n)
        hang_nut.addStretch(1)
        the.lay.addLayout(hang_nut)
        root.addStretch(1)

        bo_dich.doi_ngon_ngu.connect(self._doi_ngon_ngu)
        su_kien.cau_hinh_doi.connect(self._cau_hinh_doi)
        self._noi_tin_hieu()
        self._nap_du_lieu()

    def _cau_hinh_doi(self, nguon: str):
        """Trang dang an thi de danh: _nap_du_lieu con do ca thu muc tam."""
        if nguon == TEN_TRANG:
            return
        if self.isVisible():
            self._nap_du_lieu()
        else:
            self._cho_nap = True

    def showEvent(self, e):
        super().showEvent(e)
        if self._cho_nap:
            self._cho_nap = False
            self._nap_du_lieu()

    def _the(self, key, goi_y=None) -> TheNhom:
        the = TheNhom(key, goi_y, self.khung)
        self.root.addWidget(the)
        self._cac_the.append(the)
        return the

    @staticmethod
    def _hang_tu_layout(nhan_key, layout, parent):
        from PySide6.QtWidgets import QWidget
        o = QWidget()
        o.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        return Hang(nhan_key, o, parent, gian=True)

    # ------------------------------------------------------------ tin hieu

    def _noi_tin_hieu(self):
        def sw(hang, muc, key):
            hang.switch.checkedChanged.connect(lambda v: self._dat(muc, key, bool_txt(v)))

        def combo(hang, muc, key, sau=None):
            def doi(v):
                if self._dat(muc, key, v) and sau:
                    sau(v)
            hang.doi.connect(doi)

        combo(self.hang_ngon_ngu, "GIAO_DIEN", "ngon_ngu", dat_ngon_ngu)
        combo(self.hang_chu_de, "GIAO_DIEN", "chu_de", lambda v: setTheme(CHU_DE[v], lazy=True))
        self.o_mau.colorChanged.connect(self._doi_mau)
        self.nut_mau_mac_dinh.clicked.connect(lambda: self._doi_mau(QColor(MAU_NHAN_MAC_DINH), mac_dinh=True))
        self.hang_mica.switch.checkedChanged.connect(
            lambda v: self._dat("GIAO_DIEN", "hieu_ung_mica", bool_txt(v)) and self.doi_mica.emit(v))
        combo(self.hang_ty_le, "GIAO_DIEN", "ty_le_hien_thi", lambda _: self._bao_khoi_dong_lai())
        self.o_co_chu.valueChanged.connect(
            lambda v: self._dat("GIAO_DIEN", "co_chu_nhat_ky", v) and su_kien.co_nhat_ky_doi.emit(v))
        sw(self.hang_nho_cua_so, "GIAO_DIEN", "nho_kich_thuoc_cua_so")

        self.hang_thu_muc_ra.da_sua.connect(lambda v: self._dat("KET_QUA", "thu_muc_ra", v))
        self.o_mau_ten.textChanged.connect(self._xem_truoc_ten)
        self.o_mau_ten.editingFinished.connect(self._luu_mau_ten)
        combo(self.hang_duoi, "KET_QUA", "duoi_file_ra", lambda _: self._xem_truoc_ten())
        combo(self.hang_trung_ten, "KET_QUA", "khi_trung_ten")
        combo(self.hang_ma_hoa, "KET_QUA", "ma_hoa")
        combo(self.hang_xuong_dong, "KET_QUA", "xuong_dong")
        combo(self.hang_mo_khi_xong, "KET_QUA", "mo_khi_xong")
        sw(self.hang_phan_dau, "KET_QUA", "them_phan_dau")
        sw(self.hang_danh_dau, "KET_QUA", "danh_dau_doan")
        sw(self.hang_luu_ban_do, "KET_QUA", "luu_ban_do_nguoi_noi")
        sw(self.hang_luu_sach, "KET_QUA", "luu_audio_da_lam_sach")

        combo(self.hang_khi_loi, "HANG_DOI", "khi_file_loi")
        sw(self.hang_thong_bao, "HANG_DOI", "thong_bao_khi_xong")
        sw(self.hang_am_bao, "HANG_DOI", "am_bao_khi_xong")
        sw(self.hang_chong_ngu, "HANG_DOI", "chong_ngu")
        sw(self.hang_nho_thu_muc, "HANG_DOI", "nho_thu_muc_chon_file")
        self.hang_thu_muc_mo.da_sua.connect(lambda v: self._dat("HANG_DOI", "thu_muc_chon_file", v))
        sw(self.hang_thu_muc_con, "HANG_DOI", "them_thu_muc_con")
        self.o_duoi_nhan.editingFinished.connect(
            lambda: self._luu_duoi(self.o_duoi_nhan, "XU_LY_AM_THANH", "duoi_file_nhan"))
        self.o_duoi_video.editingFinished.connect(
            lambda: self._luu_duoi(self.o_duoi_video, "XU_LY_VIDEO", "duoi_file_video"))

        self.hang_tam.da_sua.connect(lambda v: self._dat("HE_THONG", "thu_muc_tam", v or "tmp")
                                     and self._cap_nhat_tam())
        sw(self.hang_xoa_tam, "HE_THONG", "xoa_thu_muc_tam_khi_xong")
        self.hang_ffmpeg.da_sua.connect(lambda v: self._dat("HE_THONG", "duong_dan_ffmpeg", v or "auto")
                                        and self._cap_nhat_ffmpeg())
        combo(self.hang_muc_log, "HE_THONG", "muc_nhat_ky", lambda _: self._ap_dung_log())
        self.o_log_mb.valueChanged.connect(lambda v: self._dat("HE_THONG", "dung_luong_log_mb", v)
                                           and self._ap_dung_log())
        self.o_log_so.valueChanged.connect(lambda v: self._dat("HE_THONG", "so_file_log_cu", v)
                                           and self._ap_dung_log())

    # ------------------------------------------------------------ nap / ghi

    def _nap_du_lieu(self):
        self._dang_nap = True
        try:
            ch = chh.doc_cau_hinh(CONFIG_PATH)
            tho = {k: cio.lay_gia_tri(m, k, CONFIG_PATH) or "" for m, k in (
                ("KET_QUA", "thu_muc_ra"), ("HANG_DOI", "thu_muc_chon_file"), ("HE_THONG", "thu_muc_tam"),
                ("HE_THONG", "duong_dan_ffmpeg"))}
        except Exception as e:
            InfoBar.error(tr("set_title"), f"config.txt: {e}", parent=self, position=InfoBarPosition.TOP)
            self._dang_nap = False
            return
        self._ch = ch
        self.hang_ngon_ngu.dat(ch.ngon_ngu_giao_dien)
        self.hang_chu_de.dat(ch.chu_de)
        mau = QColor(ch.mau_nhan) if ch.mau_nhan else QColor(MAU_NHAN_MAC_DINH)
        self.o_mau.setColor(mau if mau.isValid() else QColor(MAU_NHAN_MAC_DINH))
        self.hang_mica.switch.setChecked(ch.mica)
        self.hang_ty_le.dat(ch.ty_le)
        self.o_co_chu.setValue(ch.co_chu_nhat_ky)
        self.hang_nho_cua_so.switch.setChecked(ch.nho_cua_so)

        self.hang_thu_muc_ra.setText(tho["thu_muc_ra"])
        self.o_mau_ten.setText(ch.mau_ten_file)
        self.hang_duoi.dat(ch.duoi_file_ra)
        self.hang_trung_ten.dat(ch.khi_trung_ten)
        self.hang_ma_hoa.dat(ch.ma_hoa)
        self.hang_xuong_dong.dat(ch.xuong_dong)
        self.hang_mo_khi_xong.dat(ch.mo_khi_xong)
        self.hang_phan_dau.switch.setChecked(ch.them_phan_dau)
        self.hang_danh_dau.switch.setChecked(ch.danh_dau_doan)
        self.hang_luu_ban_do.switch.setChecked(ch.luu_ban_do_nguoi_noi)
        self.hang_luu_sach.switch.setChecked(ch.luu_audio_da_lam_sach)

        self.hang_khi_loi.dat(ch.khi_file_loi)
        self.hang_thong_bao.switch.setChecked(ch.thong_bao_khi_xong)
        self.hang_am_bao.switch.setChecked(ch.am_bao_khi_xong)
        self.hang_chong_ngu.switch.setChecked(ch.chong_ngu)
        self.hang_nho_thu_muc.switch.setChecked(ch.nho_thu_muc_chon_file)
        self.hang_thu_muc_mo.setText(tho["thu_muc_chon_file"])
        self.hang_thu_muc_con.switch.setChecked(ch.them_thu_muc_con)
        self.o_duoi_nhan.setText(", ".join(ch.duoi_file_nhan))
        self.o_duoi_video.setText(", ".join(ch.duoi_file_video))

        self.hang_tam.setText("" if tho["thu_muc_tam"] == "tmp" else tho["thu_muc_tam"])
        self.hang_xoa_tam.switch.setChecked(ch.xoa_thu_muc_tam_khi_xong)
        self.hang_ffmpeg.setText("" if tho["duong_dan_ffmpeg"].lower() == "auto" else tho["duong_dan_ffmpeg"])
        self.hang_muc_log.dat(ch.muc_nhat_ky)
        self.o_log_mb.setValue(ch.dung_luong_log_mb)
        self.o_log_so.setValue(ch.so_file_log_cu)
        self._dang_nap = False

        self._xem_truoc_ten()
        self._cap_nhat_tam()
        self._cap_nhat_ffmpeg()
        self._cap_nhat_thong_tin()

    def _dat(self, muc: str, key: str, gia_tri) -> bool:
        """Ghi mot gia tri. Tra ve True neu da ghi (de noi tiep hanh dong ap dung)."""
        if self._dang_nap:
            return False
        try:
            cio.dat_gia_tri(muc, key, gia_tri, CONFIG_PATH)
            self._ch = chh.doc_cau_hinh(CONFIG_PATH)
        except Exception as e:
            InfoBar.error(tr("set_title"), str(e), parent=self, position=InfoBarPosition.TOP)
            return False
        su_kien.cau_hinh_doi.emit(TEN_TRANG)
        return True

    def _doi_mau(self, mau: QColor, mac_dinh=False):
        if mac_dinh:
            self._dang_nap = True
            self.o_mau.setColor(mau)
            self._dang_nap = False
        if self._dat("GIAO_DIEN", "mau_nhan", "" if mac_dinh else mau.name()):
            setThemeColor(mau, lazy=True)

    def _bao_khoi_dong_lai(self):
        thanh = InfoBar.info(tr("set_title"), tr("set_restart_needed"), parent=self,
                             position=InfoBarPosition.TOP, duration=10000)
        nut = PushButton(tr("set_btn_restart"))
        nut.clicked.connect(self.can_khoi_dong_lai.emit)
        thanh.addWidget(nut)

    def _xem_truoc_ten(self, *_):
        ch = dataclasses.replace(getattr(self, "_ch", chh.CauHinh()), mau_ten_file=self.o_mau_ten.text().strip()
                                 or "{ten}", duoi_file_ra=self.hang_duoi.gia_tri() or ".txt")
        try:
            chh.kiem_tra(dataclasses.replace(ch, nn_bat=False))
            vi_du = ch.ten_file_ra(r"C:\Recording (3).m4a", luc_ghi=datetime(2026, 9, 10, 8, 11))
            self.xem_truoc_ten.setText(tr("set_name_preview", vi_du))
            self.xem_truoc_ten.setTextColor("#8a8a8a", "#8a8a8a")
        except ValueError:
            self.xem_truoc_ten.setText(tr("set_name_invalid"))
            self.xem_truoc_ten.setTextColor(*MAU_LOI)

    def _luu_mau_ten(self):
        mau = self.o_mau_ten.text().strip() or "{ten}"
        try:
            chh.kiem_tra(dataclasses.replace(chh.CauHinh(), mau_ten_file=mau))
        except ValueError as e:
            InfoBar.error(tr("set_title"), str(e), parent=self, position=InfoBarPosition.TOP)
            return
        self._dat("KET_QUA", "mau_ten_file", mau)

    def _luu_duoi(self, o: LineEdit, muc: str, key: str):
        """Danh sach duoi file: bo trong, chen dau cham con thieu. Xoa trang het thi lay lai gia tri cu."""
        duoi = [d.strip().lower() for d in o.text().replace(";", ",").split(",") if d.strip()]
        duoi = [d if d.startswith(".") else "." + d for d in duoi]
        if duoi:
            self._dat(muc, key, ",".join(duoi))
        o.setText(", ".join(duoi or getattr(self._ch, key)))

    def _ap_dung_log(self):
        try:
            cd.cai_dat_log(chh.doc_cau_hinh(CONFIG_PATH))
        except Exception as e:
            InfoBar.error(tr("set_title"), str(e), parent=self, position=InfoBarPosition.TOP)

    # ------------------------------------------------------------ thu muc tam, ffmpeg, thong tin

    @staticmethod
    def _tong_byte(goc: str) -> int:
        """Tong dung luong mot thu muc. scandir tra san kich thuoc, khoi stat lai tung file."""
        tong = 0
        try:
            with os.scandir(goc) as cac_muc:
                for muc in cac_muc:
                    try:
                        tong += (TrangCaiDat._tong_byte(muc.path) if muc.is_dir(follow_symlinks=False)
                                 else muc.stat(follow_symlinks=False).st_size)
                    except OSError:
                        pass
        except OSError:
            pass
        return tong

    def _cap_nhat_tam(self):
        goc = chh.thu_muc_tam_goc(self._ch)
        tong = so = 0
        if os.path.isdir(goc):
            tong = self._tong_byte(goc)
            try:
                with os.scandir(goc) as cac_muc:
                    so = sum(1 for m in cac_muc if m.is_dir(follow_symlinks=False))
            except OSError:
                pass
        self.nhan_tam.setText(tr("set_temp_usage", goc, so, tong / 2**20))

    def _don_tam(self):
        so = cd.xoa_thu_muc_tam_cu(self._ch)
        self._cap_nhat_tam()
        InfoBar.success(tr("set_title"), tr("set_temp_cleaned", so), parent=self, position=InfoBarPosition.TOP)

    def _mo_tam(self):
        goc = chh.thu_muc_tam_goc(self._ch)
        os.makedirs(goc, exist_ok=True)
        mo_bang_windows(goc)

    def _cap_nhat_ffmpeg(self):
        am_thanh_io.duong_dan_ffmpeg_tu_dat = self._ch.duong_dan_ffmpeg
        try:
            p = am_thanh_io.tim_ffmpeg()
            self.nhan_ffmpeg.setText(tr("set_ffmpeg_using", p))
            self.nhan_ffmpeg.setTextColor("#8a8a8a", "#8a8a8a")
        except RuntimeError as e:
            self.nhan_ffmpeg.setText(str(e))
            self.nhan_ffmpeg.setTextColor(*MAU_LOI)

    def _cap_nhat_thong_tin(self):
        def co(p):
            return "✔" if os.path.exists(p) else "✘"

        self.nhan_phien_ban.setText("\n".join([
            f"Guzz {PHIEN_BAN} · Python {sys.version.split()[0]} · PySide6 {PYSIDE_VERSION}",
            tr("set_about_data", DATA_DIR),
            tr("set_about_chung", DIR_CHUNG),
            tr("set_about_runtime", RUNTIME_DIR, co(os.path.join(RUNTIME_DIR, "python", "python.exe")),
               co(PYTHON_NGUOI_NOI), co(FFMPEG_CUC_BO)),
        ]))

    def _khoi_phuc_mac_dinh(self):
        hop = MessageBox(tr("set_reset_title"), tr("set_reset_body"), self.window())
        hop.yesButton.setText(tr("set_btn_reset"))
        hop.cancelButton.setText(tr("common_cancel"))
        if not hop.exec():
            return
        try:
            du_phong = CONFIG_PATH + datetime.now().strftime(".%Y%m%d_%H%M%S.bak")
            if os.path.exists(CONFIG_PATH):
                shutil.copyfile(CONFIG_PATH, du_phong)
            shutil.copyfile(CONFIG_MAU, CONFIG_PATH)
            dam_bao_du_lieu()
        except OSError as e:
            InfoBar.error(tr("set_title"), str(e), parent=self, position=InfoBarPosition.TOP)
            return
        self.can_khoi_dong_lai.emit()

    # ------------------------------------------------------------ ngon ngu

    def _doi_ngon_ngu(self, _ma):
        self.tieu_de.setText(tr("set_title"))
        for the in self._cac_the:
            the.doi_ngon_ngu()
        for i, (v, _) in enumerate(self.hang_ty_le.cac_muc):
            if v != "auto":
                self.hang_ty_le.combo.setItemText(i, f"{float(v) * 100:.0f}%")
        self.nut_mau_mac_dinh.setText(tr("common_restore_default"))
        self.nut_don_tam.setText(tr("set_btn_clean_temp"))
        self.nut_mo_tam.setText(tr("set_btn_open_temp"))
        self.nut_mo_du_lieu.setText(tr("set_btn_open_data"))
        self.nut_mo_config.setText(tr("set_btn_open_config"))
        self.nut_khoi_dong_lai.setText(tr("set_btn_restart"))
        self.nut_mac_dinh.setText(tr("set_btn_reset"))
        self._xem_truoc_ten()
        self._cap_nhat_tam()
        self._cap_nhat_ffmpeg()
        self._cap_nhat_thong_tin()
