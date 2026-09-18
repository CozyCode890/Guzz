from __future__ import annotations

import dataclasses
import os
import subprocess

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout
from qfluentwidgets import (
    CaptionLabel, CardWidget, DoubleSpinBox, EditableComboBox, FluentIcon, HyperlinkButton,
    IndeterminateProgressRing, InfoBar, InfoBarPosition, LineEdit, MessageBox, PasswordLineEdit,
    PlainTextEdit, PrimaryPushButton, PushButton, SegmentedWidget, SpinBox, StrongBodyLabel, TitleLabel,
)

import cau_hinh as chh
import config_io as cio
import model_ui
import nguoi_noi as nn
import nhan_dien
from i18n import bo_dich, tr
from luong import LuongKiemTraNguoiNoi
from paths import APP_DIR, CONFIG_PATH, SCRIPT_CAI_DAT, tuyet_doi
from su_kien import su_kien
from widgets import (
    MAU_LOI, MAU_TOT, Hang, HangCombo, HangDuongDan, HangSwitch, TheNhom, TrangCuon, bool_txt, chu_goi_y,
    mo_bang_windows,
)

TEN_TRANG = "nguoi_noi"
_CACH = model_ui.CAC_CACH
_MO_TA_CACH = {chh.NN_PYANNOTE: "nn_mode_pyannote_desc", chh.NN_GEMINI: "nn_mode_gemini_desc",
               chh.NN_KET_HOP: "nn_mode_hybrid_desc"}
_MODEL_PYANNOTE = ["pyannote/speaker-diarization-community-1", "pyannote/speaker-diarization-3.1"]


def _so_thuc(tu, den, buoc, so_le=1):
    o = DoubleSpinBox()
    o.setRange(tu, den)
    o.setSingleStep(buoc)
    o.setDecimals(so_le)
    return o


def _so_nguyen(tu, den, buoc=1):
    o = SpinBox()
    o.setRange(tu, den)
    o.setSingleStep(buoc)
    return o


class TrangNguoiNoi(TrangCuon):
    can_mo_trang = Signal(str)

    def __init__(self, parent=None):
        super().__init__("speakersInterface", parent)
        khung, root = self.khung, self.root
        self.luong_kiem_tra: LuongKiemTraNguoiNoi | None = None
        self._ch = chh.CauHinh()
        self._cach = chh.NN_PYANNOTE
        self._cac_the: list[TheNhom] = []

        self.tieu_de = TitleLabel(tr("nn_title"), khung)
        root.addWidget(self.tieu_de)

        # ---- A. Bat + cach nhan dien ----
        the = self._the("nn_section_mode")
        self.hang_bat = the.them(HangSwitch("nn_enable", "nn_enable_hint", the))
        self.chon_cach = SegmentedWidget(the)
        for ten, key in _CACH:
            # itemClicked(bool) phat kem True: tham so dau tien phai nuot no, khong thi de len t.
            self.chon_cach.addItem(ten, tr(key), lambda _=None, t=ten: self._chon_cach(t))
        the.lay.addWidget(self.chon_cach)
        self.mo_ta_cach = chu_goi_y("", the)
        the.lay.addWidget(self.mo_ta_cach)
        # Model chon o trang Google AI Studio quyet dinh cach nao dung duoc; cach khong hop thi khoa.
        hang_model = QHBoxLayout()
        self.nhan_model = CaptionLabel("", the)
        self.nhan_model.setWordWrap(True)
        self.nut_doi_model = PushButton(FluentIcon.ROBOT, tr("nn_btn_change_model"), the)
        self.nut_doi_model.clicked.connect(lambda: self.can_mo_trang.emit("google"))
        hang_model.addWidget(self.nhan_model, 1)
        hang_model.addWidget(self.nut_doi_model)
        the.lay.addLayout(hang_model)
        self.nhan_khoa_cach = CaptionLabel("", the)
        self.nhan_khoa_cach.setWordWrap(True)
        self.nhan_khoa_cach.setTextColor("#8a8a8a", "#8a8a8a")
        the.lay.addWidget(self.nhan_khoa_cach)
        self.nhan_yeu_cau = CaptionLabel("", the)
        self.nhan_yeu_cau.setWordWrap(True)
        the.lay.addWidget(self.nhan_yeu_cau)

        # ---- B. Moi truong pyannote ----
        self.the_moi_truong = the = self._the("nn_section_env", "nn_env_hint")
        self.nhan_moi_truong = CaptionLabel("", the)
        self.nhan_moi_truong.setWordWrap(True)
        the.lay.addWidget(self.nhan_moi_truong)
        hang_nut = QHBoxLayout()
        self.nut_kiem_tra = PushButton(FluentIcon.SEARCH, tr("nn_btn_check"), the)
        self.nut_cai_dat = PushButton(FluentIcon.DOWNLOAD, tr("nn_btn_install"), the)
        self.nut_mo_model = PushButton(FluentIcon.FOLDER, tr("nn_btn_open_models"), the)
        self.vong_cho = IndeterminateProgressRing(the)
        self.vong_cho.setFixedSize(18, 18)
        self.vong_cho.setStrokeWidth(2)
        self.vong_cho.hide()
        self.nut_kiem_tra.clicked.connect(self._kiem_tra)
        self.nut_cai_dat.clicked.connect(self._cai_dat_runtime)
        self.nut_mo_model.clicked.connect(self._mo_thu_muc_model)
        for w in (self.nut_kiem_tra, self.nut_cai_dat, self.nut_mo_model, self.vong_cho):
            hang_nut.addWidget(w)
        hang_nut.addStretch(1)
        the.lay.addLayout(hang_nut)
        self.nhan_kiem_tra = CaptionLabel("", the)
        self.nhan_kiem_tra.setWordWrap(True)
        the.lay.addWidget(self.nhan_kiem_tra)

        the.lay.addSpacing(8)
        self.nhan_token = StrongBodyLabel(tr("nn_token_section"), the)
        the.lay.addWidget(self.nhan_token)
        self.goi_y_token = chu_goi_y("nn_token_hint", the, nhan_dien.duong_dan_file_token())
        the.lay.addWidget(self.goi_y_token)
        hang_token = QHBoxLayout()
        self.o_token = PasswordLineEdit(the)
        self.o_token.setPlaceholderText(tr("nn_token_placeholder"))
        self.nut_luu_token = PrimaryPushButton(FluentIcon.SAVE, tr("nn_btn_save_token"), the)
        self.nut_xoa_token = PushButton(FluentIcon.DELETE, tr("nn_btn_delete_token"), the)
        self.nut_luu_token.clicked.connect(self._luu_token)
        self.nut_xoa_token.clicked.connect(self._xoa_token)
        hang_token.addWidget(self.o_token, 1)
        hang_token.addWidget(self.nut_luu_token)
        hang_token.addWidget(self.nut_xoa_token)
        the.lay.addLayout(hang_token)
        hang_link = QHBoxLayout()
        self.nhan_trang_thai_token = CaptionLabel("", the)
        self.link_dieu_khoan = HyperlinkButton("https://huggingface.co/" + _MODEL_PYANNOTE[0],
                                              tr("nn_link_accept_terms"), the)
        self.link_token = HyperlinkButton("https://huggingface.co/settings/tokens", tr("nn_link_create_token"), the)
        hang_link.addWidget(self.nhan_trang_thai_token, 1)
        hang_link.addWidget(self.link_dieu_khoan)
        hang_link.addWidget(self.link_token)
        the.lay.addLayout(hang_link)

        the.lay.addSpacing(8)
        self.o_model_pyannote = EditableComboBox()
        self.o_model_pyannote.addItems(_MODEL_PYANNOTE)
        self.o_model_pyannote.setMinimumWidth(360)
        self.o_model_pyannote.currentTextChanged.connect(self._doi_model_pyannote)
        self.o_so_nguoi = _so_nguyen(0, 20)
        self.o_it_nhat = _so_nguyen(0, 20)
        self.o_nhieu_nhat = _so_nguyen(0, 20)
        self.o_timeout = _so_nguyen(1, 600, 5)
        self.hang_python = HangDuongDan("nn_python", the, "python.exe (python.exe)", "nn_auto")
        self.hang_thu_muc_model = HangDuongDan("nn_model_dir", the, "thu_muc", "nn_auto")
        the.them(
            self.hang_python,
            Hang("nn_pyannote_model", self.o_model_pyannote, the),
            self.hang_thu_muc_model,
        )
        self.hang_ngoai_tuyen = the.them(HangSwitch("nn_offline", "nn_offline_hint", the))
        self.hang_thiet_bi = the.them(HangCombo("nn_device", [("auto", "nn_device_auto"), ("cuda", "nn_device_cuda"),
                                                              ("cpu", "nn_device_cpu")], the))
        self.hang_so_nguoi = the.them(Hang("nn_num_speakers", self.o_so_nguoi, the))
        self.hang_it_nhat = the.them(Hang("nn_min_speakers", self.o_it_nhat, the))
        self.hang_nhieu_nhat = the.them(Hang("nn_max_speakers", self.o_nhieu_nhat, the))
        self.hang_chay_tren = the.them(HangCombo("nn_run_on", [("da_lam_sach", "nn_run_on_clean"),
                                                               ("goc", "nn_run_on_original")], the))
        the.them(Hang("nn_timeout", self.o_timeout, the))
        self.o_so_nguoi.valueChanged.connect(self._cap_nhat_so_nguoi)
        self.hang_python.da_sua.connect(lambda _: self._cap_nhat_trang_thai())
        self.hang_thu_muc_model.da_sua.connect(lambda _: self._cap_nhat_trang_thai())

        # ---- C. Lam muot ----
        self.the_lam_muot = the = self._the("nn_section_smooth")
        self.hang_lam_muot = the.them(HangSwitch("nn_smooth", "nn_smooth_hint", the))
        self.o_kep_toi_da = _so_thuc(0, 30, 0.5)
        self.o_kep_nghi = _so_thuc(0, 10, 0.1)
        self.o_cua_so = _so_nguyen(0, 600, 5)
        self.o_toi_thieu = _so_nguyen(0, 300)
        self.o_gop_luot = _so_thuc(0, 30, 0.5)
        self.cac_hang_muot = [
            Hang("nn_sandwich_max", self.o_kep_toi_da, the),
            Hang("nn_sandwich_gap", self.o_kep_nghi, the),
            Hang("nn_density_window", self.o_cua_so, the),
            Hang("nn_density_min", self.o_toi_thieu, the),
        ]
        the.them(*self.cac_hang_muot)
        self.hang_gop_luot = the.them(Hang("nn_merge_turns", self.o_gop_luot, the))
        self.hang_lam_muot.switch.checkedChanged.connect(
            lambda v: [h.setEnabled(v) for h in self.cac_hang_muot])

        # ---- D. Ten nguoi noi ----
        self.the_ten = the = self._the("nn_section_names")
        self.hang_dat_ten = the.them(HangSwitch("nn_name_main", "nn_name_main_hint", the))
        self.o_ten_chinh = LineEdit()
        self.o_ten_khac = LineEdit()
        self.o_ten_chung = LineEdit()
        self.hang_ten_chinh = the.them(Hang("nn_main_label", self.o_ten_chinh, the))
        self.hang_ten_khac = the.them(Hang("nn_other_label", self.o_ten_khac, the))
        self.hang_ten_chung = the.them(Hang("nn_generic_label", self.o_ten_chung, the))
        self.xem_truoc_ten = chu_goi_y("", the)
        the.lay.addWidget(self.xem_truoc_ten)
        for o in (self.o_ten_chinh, self.o_ten_khac, self.o_ten_chung):
            o.setMinimumWidth(260)
            o.textChanged.connect(self._cap_nhat_xem_truoc)
        self.hang_dat_ten.switch.checkedChanged.connect(self._cap_nhat_xem_truoc)

        # ---- E. Gui cho Google + dinh dang ----
        self.the_gui = the = self._the("nn_section_output")
        self.hang_cach_gui = the.them(HangCombo("nn_send_map", [("file", "nn_send_map_file"),
                                                                ("van_ban", "nn_send_map_inline")], the, rong=300))
        self.hang_moc = the.them(HangSwitch("nn_timestamps", "nn_timestamps_hint", the))
        self.o_mau = LineEdit()
        self.o_mau.setMinimumWidth(320)
        self.o_mau.textChanged.connect(self._cap_nhat_xem_truoc)
        self.hang_moc.switch.checkedChanged.connect(self._cap_nhat_xem_truoc)
        self.hang_mau = the.them(Hang("nn_paragraph_template", self.o_mau, the))
        self.xem_truoc_mau = chu_goi_y("", the)
        the.lay.addWidget(self.xem_truoc_mau)
        self.o_gop_toi_da = _so_nguyen(0, 600, 10)
        self.o_gop_lang = _so_thuc(0, 60, 0.5)
        self.hang_gop_toi_da = the.them(Hang("nn_para_max", self.o_gop_toi_da, the))
        self.hang_gop_lang = the.them(Hang("nn_para_gap", self.o_gop_lang, the))
        self.hang_xem_lai = the.them(HangSwitch("nn_review_marks", "nn_review_marks_hint", the))
        self.goi_y_rang_buoc = chu_goi_y("nn_transcribe_limits", the)
        the.lay.addWidget(self.goi_y_rang_buoc)

        # ---- F. Prompt ----
        self.the_prompt = the = CardWidget(khung)
        lay = QVBoxLayout(the)
        hang = QHBoxLayout()
        self.nhan_prompt = StrongBodyLabel(tr("nn_prompt_section"), the)
        self.nut_prompt_mac_dinh = PushButton(FluentIcon.RETURN, tr("common_restore_default"), the)
        self.nut_prompt_mac_dinh.clicked.connect(self._prompt_mac_dinh)
        hang.addWidget(self.nhan_prompt, 1)
        hang.addWidget(self.nut_prompt_mac_dinh)
        lay.addLayout(hang)
        self.goi_y_prompt = chu_goi_y("nn_prompt_hint", the)
        lay.addWidget(self.goi_y_prompt)
        self.o_prompt = PlainTextEdit(the)
        self.o_prompt.setMinimumHeight(220)
        lay.addWidget(self.o_prompt)
        root.addWidget(the)

        root.addStretch(1)
        self.nut_luu = PrimaryPushButton(FluentIcon.SAVE, tr("common_save"), khung)
        self.nut_luu.clicked.connect(self._luu)
        root.addWidget(self.nut_luu)

        bo_dich.doi_ngon_ngu.connect(self._doi_ngon_ngu)
        su_kien.cau_hinh_doi.connect(lambda nguon: nguon != TEN_TRANG and self._nap_du_lieu())
        su_kien.han_muc_doi.connect(self._cap_nhat_model)
        self._nap_du_lieu()

    def _the(self, tieu_de_key, goi_y_key=None) -> TheNhom:
        the = TheNhom(tieu_de_key, goi_y_key, self.khung)
        self.root.addWidget(the)
        self._cac_the.append(the)
        return the

    def showEvent(self, e):
        super().showEvent(e)
        self._cap_nhat_trang_thai()

    # ------------------------------------------------------------ nap / luu

    def _nap_du_lieu(self):
        try:
            ch = chh.doc_cau_hinh(CONFIG_PATH)
            python_tho = cio.lay_gia_tri("NGUOI_NOI", "duong_dan_python", CONFIG_PATH) or ""
            model_dir_tho = cio.lay_gia_tri("NGUOI_NOI", "thu_muc_model", CONFIG_PATH) or ""
        except Exception as e:
            InfoBar.error(tr("nn_title"), str(e), parent=self, position=InfoBarPosition.TOP)
            return
        self._ch = ch
        self.hang_bat.switch.setChecked(ch.nn_bat)
        self._cap_nhat_model()
        cach = chh.cach_thay_the(ch.model, ch.nn_cach)
        self._chon_cach(cach)
        self._canh_bao_cach = (tr("nn_mode_forced", model_ui.ten_cach(ch.nn_cach), ch.model, model_ui.ten_cach(cach))
                               if cach != ch.nn_cach else "")
        self._cap_nhat_trang_thai()
        self.hang_python.setText("" if python_tho.lower() == "auto" else python_tho)
        self.hang_thu_muc_model.setText("" if model_dir_tho.lower() == "auto" else model_dir_tho)
        self.o_model_pyannote.setCurrentText(ch.nn_model)
        self.hang_ngoai_tuyen.switch.setChecked(ch.nn_ngoai_tuyen)
        self.hang_thiet_bi.dat(ch.nn_thiet_bi)
        self.o_so_nguoi.setValue(ch.nn_so_nguoi)
        self.o_it_nhat.setValue(ch.nn_it_nhat)
        self.o_nhieu_nhat.setValue(ch.nn_nhieu_nhat)
        self.hang_chay_tren.dat(ch.nn_chay_tren)
        self.o_timeout.setValue(max(1, ch.nn_timeout_giay // 60))
        self.hang_lam_muot.switch.setChecked(ch.nn_lam_muot)
        for h in self.cac_hang_muot:
            h.setEnabled(ch.nn_lam_muot)
        self.o_kep_toi_da.setValue(ch.nn_kep_toi_da_giay)
        self.o_kep_nghi.setValue(ch.nn_kep_nghi_giay)
        self.o_cua_so.setValue(int(ch.nn_mat_do_cua_so_giay))
        self.o_toi_thieu.setValue(int(ch.nn_mat_do_toi_thieu_giay))
        self.o_gop_luot.setValue(ch.nn_gop_luot_giay)
        self.hang_dat_ten.switch.setChecked(ch.nn_dat_ten_nguoi_chinh)
        self.o_ten_chinh.setText(ch.nn_ten_nguoi_chinh)
        self.o_ten_khac.setText(ch.nn_ten_nguoi_khac)
        self.o_ten_chung.setText(ch.nn_ten_chung)
        self.hang_cach_gui.dat(ch.nn_cach_gui)
        self.hang_moc.switch.setChecked(ch.nn_moc_thoi_gian)
        self.o_mau.setText(ch.nn_mau_doan)
        self.o_gop_toi_da.setValue(int(ch.nn_gop_doan_toi_da_giay))
        self.o_gop_lang.setValue(ch.nn_gop_khoang_lang_giay)
        self.hang_xem_lai.switch.setChecked(ch.nn_danh_dau_xem_lai)
        try:
            self.o_prompt.setPlainText(ch.doc_prompt_nguoi_noi())
        except OSError:
            self.o_prompt.setPlainText("")
        self._cap_nhat_so_nguoi()
        self._cap_nhat_xem_truoc()
        self._cap_nhat_trang_thai()

    def _cau_hinh_tren_man_hinh(self) -> chh.CauHinh:
        return dataclasses.replace(
            self._ch,
            nn_bat=self.hang_bat.switch.isChecked(),
            nn_cach=self._cach,
            nn_python=self.hang_python.text() or "auto",
            nn_model=self.o_model_pyannote.currentText().strip() or chh.CauHinh.nn_model,
            nn_thu_muc_model=self.hang_thu_muc_model.text() or "auto",
            nn_ngoai_tuyen=self.hang_ngoai_tuyen.switch.isChecked(),
            nn_thiet_bi=self.hang_thiet_bi.gia_tri(),
            nn_so_nguoi=self.o_so_nguoi.value(),
            nn_it_nhat=self.o_it_nhat.value(),
            nn_nhieu_nhat=self.o_nhieu_nhat.value(),
            nn_chay_tren=self.hang_chay_tren.gia_tri(),
            nn_timeout_giay=self.o_timeout.value() * 60,
            nn_lam_muot=self.hang_lam_muot.switch.isChecked(),
            nn_kep_toi_da_giay=round(self.o_kep_toi_da.value(), 2),
            nn_kep_nghi_giay=round(self.o_kep_nghi.value(), 2),
            nn_mat_do_cua_so_giay=float(self.o_cua_so.value()),
            nn_mat_do_toi_thieu_giay=float(self.o_toi_thieu.value()),
            nn_gop_luot_giay=round(self.o_gop_luot.value(), 2),
            nn_dat_ten_nguoi_chinh=self.hang_dat_ten.switch.isChecked(),
            nn_ten_nguoi_chinh=self.o_ten_chinh.text().strip() or chh.CauHinh.nn_ten_nguoi_chinh,
            nn_ten_nguoi_khac=self.o_ten_khac.text().strip() or chh.CauHinh.nn_ten_nguoi_khac,
            nn_ten_chung=self.o_ten_chung.text().strip() or chh.CauHinh.nn_ten_chung,
            nn_cach_gui=self.hang_cach_gui.gia_tri(),
            nn_moc_thoi_gian=self.hang_moc.switch.isChecked(),
            nn_mau_doan=self.o_mau.text().strip() or chh.CauHinh.nn_mau_doan,
            nn_gop_doan_toi_da_giay=float(self.o_gop_toi_da.value()),
            nn_gop_khoang_lang_giay=round(self.o_gop_lang.value(), 2),
            nn_danh_dau_xem_lai=self.hang_xem_lai.switch.isChecked(),
        )

    def _luu(self):
        ch = self._cau_hinh_tren_man_hinh()
        try:
            chh.kiem_tra(ch)
        except ValueError as e:
            InfoBar.error(tr("nn_title"), str(e), parent=self, position=InfoBarPosition.TOP, duration=8000)
            return
        loi = chh.loi_rang_buoc(dataclasses.replace(ch, nn_bat=True))
        if loi:
            InfoBar.error(tr("nn_title"), loi, parent=self, position=InfoBarPosition.TOP, duration=10000)
            return

        def so(x):
            return f"{x:g}"

        try:
            cio.dat_nhieu_gia_tri({
                ("NGUOI_NOI", "bat"): bool_txt(ch.nn_bat),
                ("NGUOI_NOI", "cach_nhan_dien"): ch.nn_cach,
                ("NGUOI_NOI", "duong_dan_python"): ch.nn_python,
                ("NGUOI_NOI", "model_pyannote"): ch.nn_model,
                ("NGUOI_NOI", "thu_muc_model"): ch.nn_thu_muc_model,
                ("NGUOI_NOI", "chi_dung_model_da_tai"): bool_txt(ch.nn_ngoai_tuyen),
                ("NGUOI_NOI", "thiet_bi"): ch.nn_thiet_bi,
                ("NGUOI_NOI", "so_nguoi"): ch.nn_so_nguoi,
                ("NGUOI_NOI", "so_nguoi_it_nhat"): ch.nn_it_nhat,
                ("NGUOI_NOI", "so_nguoi_nhieu_nhat"): ch.nn_nhieu_nhat,
                ("NGUOI_NOI", "chay_tren"): ch.nn_chay_tren,
                ("NGUOI_NOI", "timeout_phut"): ch.nn_timeout_giay // 60,
                ("NGUOI_NOI", "lam_muot"): bool_txt(ch.nn_lam_muot),
                ("NGUOI_NOI", "kep_toi_da_giay"): so(ch.nn_kep_toi_da_giay),
                ("NGUOI_NOI", "kep_nghi_giay"): so(ch.nn_kep_nghi_giay),
                ("NGUOI_NOI", "mat_do_cua_so_giay"): so(ch.nn_mat_do_cua_so_giay),
                ("NGUOI_NOI", "mat_do_toi_thieu_giay"): so(ch.nn_mat_do_toi_thieu_giay),
                ("NGUOI_NOI", "gop_luot_cach_nhau_giay"): so(ch.nn_gop_luot_giay),
                ("NGUOI_NOI", "dat_ten_nguoi_chinh"): bool_txt(ch.nn_dat_ten_nguoi_chinh),
                ("NGUOI_NOI", "ten_nguoi_chinh"): ch.nn_ten_nguoi_chinh,
                ("NGUOI_NOI", "ten_nguoi_khac"): ch.nn_ten_nguoi_khac,
                ("NGUOI_NOI", "ten_chung"): ch.nn_ten_chung,
                ("NGUOI_NOI", "cach_gui_ban_do"): ch.nn_cach_gui,
                ("NGUOI_NOI", "moc_thoi_gian"): bool_txt(ch.nn_moc_thoi_gian),
                ("NGUOI_NOI", "mau_doan"): ch.nn_mau_doan,
                ("NGUOI_NOI", "gop_doan_toi_da_giay"): so(ch.nn_gop_doan_toi_da_giay),
                ("NGUOI_NOI", "gop_khoang_lang_giay"): so(ch.nn_gop_khoang_lang_giay),
                ("NGUOI_NOI", "danh_dau_xem_lai"): bool_txt(ch.nn_danh_dau_xem_lai),
            }, CONFIG_PATH)
            p = tuyet_doi(ch.nn_file_prompt)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(self.o_prompt.toPlainText().strip() + "\n")
            self._ch = chh.doc_cau_hinh(CONFIG_PATH)
        except Exception as e:
            InfoBar.error(tr("nn_title"), str(e), parent=self, position=InfoBarPosition.TOP)
            return
        su_kien.cau_hinh_doi.emit(TEN_TRANG)
        self._canh_bao_cach = ""
        self._cap_nhat_trang_thai()
        InfoBar.success(tr("nn_title"), tr("common_saved"), parent=self, position=InfoBarPosition.TOP)

    # ------------------------------------------------------------ hien thi theo cach

    def _cap_nhat_model(self):
        """Model dang chon (trang Google AI Studio) va khoa cac cach nhan dien khong hop voi no."""
        ch = self._ch
        chuoi = dataclasses.replace(ch, nn_bat=True, nn_cach=chh.cach_thay_the(ch.model, ch.nn_cach)).chuoi_model()
        khoa = model_ui.mo_ta_khoa(ch.model)
        ten_model = f"{ch.model} — {khoa}" if khoa else ch.model
        self.nhan_model.setText(tr("nn_current_model", ten_model, model_ui.kieu_model(ch.model),
                                   ", ".join(chuoi[1:]) or tr("nn_no_fallback")))
        hop_le = chh.cac_cach_hop_le(ch.model)
        for ten, key in _CACH:
            item = self.chon_cach.widget(ten)
            if item is not None:
                item.setEnabled(ten in hop_le)
                self.chon_cach.setItemText(ten, tr(key) + ("" if ten in hop_le else "  🔒"))
        bi_khoa = [model_ui.ten_cach(ten) for ten, _ in _CACH if ten not in hop_le]
        self.nhan_khoa_cach.setText(tr("nn_modes_locked", ", ".join(bi_khoa), model_ui.goi_y_rang_buoc(ch.model)))

    def _chon_cach(self, cach: str):
        if cach not in _MO_TA_CACH or not chh.model_hop_voi_cach(self._ch.model, cach):
            # Muc bi khoa: tra lai lua chon cu tren thanh chon.
            self.chon_cach.setCurrentItem(self._cach)
            return
        self._cach = cach
        self._canh_bao_cach = ""
        self.chon_cach.setCurrentItem(cach)
        self.mo_ta_cach.setText(tr(_MO_TA_CACH[cach]))
        can_pyannote = cach in (chh.NN_PYANNOTE, chh.NN_KET_HOP)
        la_pyannote = cach == chh.NN_PYANNOTE
        self.the_moi_truong.setVisible(can_pyannote)
        self.the_lam_muot.setVisible(can_pyannote)
        self.hang_gop_luot.setVisible(la_pyannote)
        self.hang_cach_gui.setVisible(la_pyannote)
        self.the_prompt.setVisible(la_pyannote)
        self.hang_gop_toi_da.setVisible(not la_pyannote)
        self.hang_gop_lang.setVisible(not la_pyannote)
        self.hang_xem_lai.setVisible(cach == chh.NN_KET_HOP)
        self.goi_y_rang_buoc.setVisible(not la_pyannote)
        self._cap_nhat_trang_thai()

    def _cap_nhat_so_nguoi(self, *_):
        chinh_xac = self.o_so_nguoi.value() > 0
        self.hang_it_nhat.setEnabled(not chinh_xac)
        self.hang_nhieu_nhat.setEnabled(not chinh_xac)

    def _cap_nhat_xem_truoc(self, *_):
        ch = self._cau_hinh_tren_man_hinh()
        luot = [nn.LuotNoi(0, 50, "A"), nn.LuotNoi(50, 55, "B"), nn.LuotNoi(55, 60, "C")]
        bang = nn.bang_ten(luot, ch, chinh="A")
        self.xem_truoc_ten.setText(tr("nn_names_preview", ", ".join(bang.values())))
        try:
            vi_du = nn.hien_thi_doan(nn.DoanVan(tr("nn_template_sample"), bang["A"], 754.0),
                                     ch.nn_mau_doan, ch.nn_moc_thoi_gian, False)
            self.xem_truoc_mau.setText(tr("nn_template_preview", vi_du))
            self.xem_truoc_mau.setTextColor("#8a8a8a", "#8a8a8a")
        except (KeyError, IndexError, ValueError):
            self.xem_truoc_mau.setText(tr("nn_template_invalid"))
            self.xem_truoc_mau.setTextColor(*MAU_LOI)

    def _doi_model_pyannote(self, model: str):
        self.link_dieu_khoan.setUrl("https://huggingface.co/" + (model.strip() or _MODEL_PYANNOTE[0]))
        self._cap_nhat_trang_thai()

    def _cap_nhat_trang_thai(self):
        # Hien model se dung khi BAT nhan dien, ke ca luc cong tac dang tat.
        ch = dataclasses.replace(self._cau_hinh_tren_man_hinh(), nn_bat=True)
        token, nguon = nhan_dien.nguon_token()
        if not token:
            self.nhan_trang_thai_token.setText(tr("nn_token_status_none"))
        elif nguon == nhan_dien.duong_dan_file_token():
            self.nhan_trang_thai_token.setText(tr("nn_token_status_file"))
        else:
            self.nhan_trang_thai_token.setText(tr("nn_token_status_other", nguon))
        self.nut_xoa_token.setEnabled(nguon == nhan_dien.duong_dan_file_token())

        python = ch.duong_dan_python_nguoi_noi()
        co_python = os.path.isfile(python)
        co_model = nhan_dien.model_da_tai(ch)
        dong = [
            ("✔ " if co_python else "✘ ") + tr("nn_env_python", python),
            ("✔ " if token else "✘ ") + tr("nn_env_token"),
            ("✔ " if co_model else "• ") + tr("nn_env_model", ch.thu_muc_model_hf()),
        ]
        self.nhan_moi_truong.setText("\n".join(dong))
        self.hang_python.o.setPlaceholderText(tr("nn_auto_path", ch.duong_dan_python_nguoi_noi()
                                                  if not self.hang_python.text() else ""))
        self.hang_thu_muc_model.o.setPlaceholderText(tr("nn_auto_path", ch.thu_muc_model_hf()
                                                        if not self.hang_thu_muc_model.text() else ""))

        if getattr(self, "_canh_bao_cach", ""):
            self.nhan_yeu_cau.setText(self._canh_bao_cach)
            self.nhan_yeu_cau.setTextColor(*MAU_LOI)
        elif self._cach == chh.NN_GEMINI:
            self.nhan_yeu_cau.setText(tr("nn_req_gemini", ch.model))
            self.nhan_yeu_cau.setTextColor(*MAU_TOT)
        else:
            san_sang = co_python and (token or co_model)
            self.nhan_yeu_cau.setText(tr("nn_req_ready" if san_sang else "nn_req_missing", ch.model))
            self.nhan_yeu_cau.setTextColor(*(MAU_TOT if san_sang else MAU_LOI))

    # ------------------------------------------------------------ token, moi truong

    def _luu_token(self):
        token = self.o_token.text().strip()
        if not token:
            return
        try:
            nhan_dien.luu_token(token)
        except OSError as e:
            InfoBar.error(tr("nn_title"), str(e), parent=self, position=InfoBarPosition.TOP)
            return
        self.o_token.clear()
        self._cap_nhat_trang_thai()
        InfoBar.success(tr("nn_title"), tr("nn_token_saved"), parent=self, position=InfoBarPosition.TOP)

    def _xoa_token(self):
        nhan_dien.luu_token("")
        self._cap_nhat_trang_thai()

    def _kiem_tra(self):
        if self.luong_kiem_tra and self.luong_kiem_tra.isRunning():
            return
        # Token dang go tren man hinh (chua Luu) van dung de kiem tra.
        token_moi = self.o_token.text().strip()
        if token_moi:
            nhan_dien.luu_token(token_moi)
            self.o_token.clear()
        self.nut_kiem_tra.setEnabled(False)
        self.vong_cho.show()
        self.nhan_kiem_tra.setText(tr("nn_checking"))
        self.nhan_kiem_tra.setTextColor("#8a8a8a", "#8a8a8a")
        self.luong_kiem_tra = LuongKiemTraNguoiNoi(self._cau_hinh_tren_man_hinh(), self)
        self.luong_kiem_tra.dong.connect(lambda d: self.nhan_kiem_tra.setText(d))
        self.luong_kiem_tra.xong.connect(self._kiem_tra_xong)
        self.luong_kiem_tra.start()

    def _kiem_tra_xong(self, ok: bool, thong_tin: dict, thong_bao: list):
        self.nut_kiem_tra.setEnabled(True)
        self.vong_cho.hide()
        self._cap_nhat_trang_thai()
        if ok:
            chi_tiet = tr("nn_check_ok", thong_tin.get("thiet_bi", "?"), thong_tin.get("gpu") or "CPU",
                          thong_tin.get("torch", "?"), thong_tin.get("pyannote", "?"))
            self.nhan_kiem_tra.setText(chi_tiet)
            self.nhan_kiem_tra.setTextColor(*MAU_TOT)
            InfoBar.success(tr("nn_title"), tr("nn_check_ok_short"), parent=self, position=InfoBarPosition.TOP)
        else:
            chi_tiet = "\n".join(thong_bao[-6:]) or tr("nn_check_fail")
            self.nhan_kiem_tra.setText(chi_tiet)
            self.nhan_kiem_tra.setTextColor(*MAU_LOI)
            InfoBar.error(tr("nn_check_fail"), thong_bao[-1] if thong_bao else "", parent=self,
                          position=InfoBarPosition.TOP, duration=10000)

    def _cai_dat_runtime(self):
        hop = MessageBox(tr("nn_install_title"), tr("nn_install_body"), self.window())
        hop.yesButton.setText(tr("nn_install_yes"))
        hop.cancelButton.setText(tr("common_cancel"))
        if not hop.exec():
            return
        if not os.path.isfile(SCRIPT_CAI_DAT):
            InfoBar.error(tr("nn_title"), SCRIPT_CAI_DAT, parent=self, position=InfoBarPosition.TOP)
            return
        # Cua so PowerShell rieng de nguoi dung thay tien do pip; app van dung duoc trong luc do.
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", SCRIPT_CAI_DAT,
             "-ChiNguoiNoi"],
            cwd=APP_DIR, creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        InfoBar.info(tr("nn_title"), tr("nn_install_started"), parent=self, position=InfoBarPosition.TOP,
                     duration=10000)

    def _mo_thu_muc_model(self):
        p = self._cau_hinh_tren_man_hinh().thu_muc_model_hf()
        os.makedirs(p, exist_ok=True)
        mo_bang_windows(p)

    def _prompt_mac_dinh(self):
        try:
            with open(os.path.join(APP_DIR, "prompt_nguoi_noi.txt"), "r", encoding="utf-8") as f:
                self.o_prompt.setPlainText(f.read().strip())
        except OSError as e:
            InfoBar.error(tr("nn_title"), str(e), parent=self, position=InfoBarPosition.TOP)

    # ------------------------------------------------------------ ngon ngu

    def _doi_ngon_ngu(self, _ma):
        self.tieu_de.setText(tr("nn_title"))
        for ten, key in _CACH:
            self.chon_cach.setItemText(ten, tr(key))
        for the in self._cac_the:
            the.doi_ngon_ngu()
        self.nut_kiem_tra.setText(tr("nn_btn_check"))
        self.nut_cai_dat.setText(tr("nn_btn_install"))
        self.nut_mo_model.setText(tr("nn_btn_open_models"))
        self.nut_doi_model.setText(tr("nn_btn_change_model"))
        self._cap_nhat_model()
        self.nhan_token.setText(tr("nn_token_section"))
        self.goi_y_token.setText(tr("nn_token_hint", nhan_dien.duong_dan_file_token()))
        self.o_token.setPlaceholderText(tr("nn_token_placeholder"))
        self.nut_luu_token.setText(tr("nn_btn_save_token"))
        self.nut_xoa_token.setText(tr("nn_btn_delete_token"))
        self.link_dieu_khoan.setText(tr("nn_link_accept_terms"))
        self.link_token.setText(tr("nn_link_create_token"))
        self.goi_y_rang_buoc.setText(tr("nn_transcribe_limits"))
        self.nhan_prompt.setText(tr("nn_prompt_section"))
        self.goi_y_prompt.setText(tr("nn_prompt_hint"))
        self.nut_prompt_mac_dinh.setText(tr("common_restore_default"))
        self.nut_luu.setText(tr("common_save"))
        self._chon_cach(self._cach)
        self._cap_nhat_xem_truoc()
