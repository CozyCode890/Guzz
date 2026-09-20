from __future__ import annotations

import dataclasses
import os

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout
from qfluentwidgets import (
    TitleLabel, StrongBodyLabel, CaptionLabel, CardWidget, ComboBox, EditableComboBox,
    LineEdit, PasswordLineEdit, PlainTextEdit, SpinBox, PrimaryPushButton, PushButton,
    FluentIcon, InfoBar, InfoBarPosition, IndeterminateProgressRing, HyperlinkButton,
)

import cau_hinh as chh
import google_ai as ga
import model_ui
from paths import APP_DIR, CONFIG_PATH, tuyet_doi
from i18n import tr, bo_dich
import config_io as cio
from luong import LuongKiemTraKetNoi
from su_kien import su_kien
from widgets import MAU_LOI, Hang, HangSwitch, TheNhom, TrangCuon, bool_txt, chu_goi_y

TEN_TRANG = "google"
MODEL_GOI_Y = model_ui.MODEL_GOI_Y


def _so_nguyen(tu, den, buoc=1, rong=None):
    o = SpinBox()
    o.setRange(tu, den)
    o.setSingleStep(buoc)
    if rong:
        o.setMinimumWidth(rong)
    return o


class TrangGoogleAI(TrangCuon):
    def __init__(self, parent=None):
        super().__init__("googleInterface", parent)
        khung, root = self.khung, self.root
        self.luong_kiem_tra = None
        self._ch = chh.CauHinh()
        self._model_tu_key: list[str] = []
        self._cho_lam_moi = False
        self._cho_nap = False

        self.tieu_de = TitleLabel(tr("google_title"), khung)
        root.addWidget(self.tieu_de)

        # ---- API key ----
        the_key = CardWidget(khung)
        lay_key = QVBoxLayout(the_key)
        self.nhan_key = StrongBodyLabel(tr("google_key_section"), the_key)
        lay_key.addWidget(self.nhan_key)
        self.goi_y_key = chu_goi_y("google_key_hint", the_key, ga.duong_dan_file_api_key())
        lay_key.addWidget(self.goi_y_key)

        hang_key = QHBoxLayout()
        self.o_key = PasswordLineEdit(the_key)
        self.o_key.setPlaceholderText(tr("google_key_placeholder"))
        self.nut_luu_key = PrimaryPushButton(FluentIcon.SAVE, tr("google_btn_save_key"), the_key)
        self.nut_xoa_key = PushButton(FluentIcon.DELETE, tr("google_btn_delete_key"), the_key)
        self.nut_kiem_tra = PushButton(FluentIcon.CONNECT, tr("google_btn_check"), the_key)
        self.nut_luu_key.clicked.connect(self._luu_key)
        self.nut_xoa_key.clicked.connect(self._xoa_key)
        self.nut_kiem_tra.clicked.connect(self._kiem_tra)
        hang_key.addWidget(self.o_key, 1)
        hang_key.addWidget(self.nut_luu_key)
        hang_key.addWidget(self.nut_xoa_key)
        hang_key.addWidget(self.nut_kiem_tra)
        lay_key.addLayout(hang_key)

        hang_trang_thai = QHBoxLayout()
        self.vong_cho = IndeterminateProgressRing(the_key)
        self.vong_cho.setFixedSize(16, 16)
        self.vong_cho.setStrokeWidth(2)
        self.vong_cho.setVisible(False)
        self.nhan_trang_thai_key = CaptionLabel("", the_key)
        self.nhan_trang_thai_key.setWordWrap(True)
        self.link_key = HyperlinkButton("https://aistudio.google.com/apikey", tr("google_link_get_key"), the_key)
        hang_trang_thai.addWidget(self.vong_cho)
        hang_trang_thai.addWidget(self.nhan_trang_thai_key, 1)
        hang_trang_thai.addWidget(self.link_key)
        lay_key.addLayout(hang_trang_thai)
        root.addWidget(the_key)

        # ---- Model ----
        the_model = CardWidget(khung)
        lay_model = QVBoxLayout(the_model)
        self.nhan_model = StrongBodyLabel(tr("google_model_section"), the_model)
        lay_model.addWidget(self.nhan_model)
        self.o_model = EditableComboBox()
        self.o_model.setMinimumWidth(320)
        self.o_model.currentTextChanged.connect(self._cap_nhat_theo_model)
        self.o_che_do = ComboBox()
        self.o_che_do.addItems([tr("google_mode_smart"), tr("google_mode_verbatim")])
        self.o_ngon_ngu = LineEdit()
        self.o_ngon_ngu.setPlaceholderText("vi-VN, en-US")
        self.o_tu_vung = LineEdit()
        self.o_tu_vung.setPlaceholderText("Data Mining, decision tree, overfitting")
        self.hang_model = Hang("google_model", self.o_model, the_model)
        self.hang_che_do = Hang("google_mode", self.o_che_do, the_model)
        self.hang_ngon_ngu = Hang("google_language", self.o_ngon_ngu, the_model, gian=True)
        self.hang_tu_vung = Hang("google_vocabulary", self.o_tu_vung, the_model, gian=True)
        lay_model.addWidget(self.hang_model)
        self.nhan_khoa_model = CaptionLabel("", the_model)
        self.nhan_khoa_model.setWordWrap(True)
        self.nhan_khoa_model.setTextColor(*MAU_LOI)
        lay_model.addWidget(self.nhan_khoa_model)
        for h in (self.hang_che_do, self.hang_ngon_ngu, self.hang_tu_vung):
            lay_model.addWidget(h)
        self.goi_y_model = chu_goi_y("google_model_hint", the_model)
        lay_model.addWidget(self.goi_y_model)
        self.goi_y_rang_buoc = CaptionLabel("", the_model)
        self.goi_y_rang_buoc.setWordWrap(True)
        lay_model.addWidget(self.goi_y_rang_buoc)
        root.addWidget(the_model)

        # ---- Tu doi model ----
        self.the_doi = the = TheNhom("google_fallback_section", "google_fallback_hint", khung)
        root.addWidget(the)
        self.hang_tu_doi = the.them(HangSwitch("google_fallback_enable", parent=the))
        self.o_du_phong = LineEdit()
        self.o_du_phong.setPlaceholderText(", ".join(chh.MODEL_DU_PHONG_MAC_DINH))
        # Cho go xong hang moi dung lai chuoi model: moi lan dung lai la mot luot hoi
        # trang thai khoa cua tung model, go tung chu ma tinh lai thi phi.
        self._dong_ho_chuoi = QTimer(self)
        self._dong_ho_chuoi.setSingleShot(True)
        self._dong_ho_chuoi.setInterval(300)
        self._dong_ho_chuoi.timeout.connect(self._cap_nhat_chuoi)
        self.o_du_phong.textChanged.connect(lambda _: self._dong_ho_chuoi.start())
        self.hang_du_phong = the.them(Hang("google_fallback_models", self.o_du_phong, the, gian=True))
        self.nhan_chuoi = chu_goi_y("", the)
        the.lay.addWidget(self.nhan_chuoi)
        self.o_so_lan_doi = _so_nguyen(1, 10)
        self.o_phut_khoa = _so_nguyen(0, 1440, 5)
        self.o_doi_khi_cho = _so_nguyen(0, 3600, 10)
        self.o_cho_toi_da = _so_nguyen(0, 1440, 5)
        self.hang_so_lan_doi = the.them(Hang("google_fallback_retries", self.o_so_lan_doi, the))
        self.hang_phut_khoa = the.them(Hang("google_fallback_overload_lock", self.o_phut_khoa, the))
        self.hang_quay_lai = the.them(HangSwitch("google_fallback_return", "google_fallback_return_hint", the))
        self.hang_doi_khi_cho = the.them(Hang("google_fallback_wait_switch", self.o_doi_khi_cho, the))
        self.hang_cho_toi_da = the.them(Hang("google_fallback_max_wait", self.o_cho_toi_da, the))
        self.hang_khoa_truoc = the.them(HangSwitch("google_fallback_proactive", parent=the))
        self.hang_tu_doi.switch.checkedChanged.connect(self._bat_tat_doi_model)

        # ---- Prompt ----
        self.the_prompt = CardWidget(khung)
        lay_prompt = QVBoxLayout(self.the_prompt)
        hang_prompt = QHBoxLayout()
        self.nhan_prompt = StrongBodyLabel(tr("google_prompt_section"), self.the_prompt)
        self.nut_prompt_mac_dinh = PushButton(FluentIcon.RETURN, tr("common_restore_default"), self.the_prompt)
        self.nut_prompt_mac_dinh.clicked.connect(self._prompt_mac_dinh)
        hang_prompt.addWidget(self.nhan_prompt, 1)
        hang_prompt.addWidget(self.nut_prompt_mac_dinh)
        lay_prompt.addLayout(hang_prompt)
        self.o_prompt = PlainTextEdit(self.the_prompt)
        self.o_prompt.setMinimumHeight(170)
        lay_prompt.addWidget(self.o_prompt)
        root.addWidget(self.the_prompt)

        # ---- Gui yeu cau ----
        the_gui = CardWidget(khung)
        lay_gui = QVBoxLayout(the_gui)
        self.nhan_gui = StrongBodyLabel(tr("google_request_section"), the_gui)
        lay_gui.addWidget(self.nhan_gui)
        self.hang_luu_server = HangSwitch("google_store", parent=the_gui)
        self.hang_xoa_file = HangSwitch("google_delete_remote", parent=the_gui)
        self.o_timeout = _so_nguyen(60, 3600, 60)
        self.o_so_lan = _so_nguyen(1, 10)
        self.o_token_phut = _so_nguyen(0, 100_000_000, 1000, 160)
        self.hang_so = [
            Hang("google_timeout", self.o_timeout, the_gui),
            Hang("google_retries", self.o_so_lan, the_gui),
            Hang("google_token_limit", self.o_token_phut, the_gui),
        ]
        for h in (self.hang_luu_server, self.hang_xoa_file, *self.hang_so):
            lay_gui.addWidget(h)
        self.goi_y_token = chu_goi_y("google_token_limit_hint", the_gui)
        lay_gui.addWidget(self.goi_y_token)
        root.addWidget(the_gui)

        root.addStretch(1)
        self.nut_luu = PrimaryPushButton(FluentIcon.SAVE, tr("common_save"), khung)
        self.nut_luu.clicked.connect(self._luu)
        root.addWidget(self.nut_luu)

        bo_dich.doi_ngon_ngu.connect(self._doi_ngon_ngu)
        su_kien.cau_hinh_doi.connect(self._cau_hinh_doi)
        su_kien.han_muc_doi.connect(self._han_muc_doi)
        self._nap_du_lieu()

    def _cau_hinh_doi(self, nguon: str):
        if nguon == TEN_TRANG:
            return
        if self.isVisible():
            self._nap_du_lieu()
        else:
            self._cho_nap = True

    def _han_muc_doi(self):
        """Doi trang thai khoa model: dang an thi de danh, mo trang ra moi lam moi."""
        if self.isVisible():
            self._lam_moi_khoa()
        else:
            self._cho_lam_moi = True

    def showEvent(self, e):
        super().showEvent(e)
        # Nap lai ca trang thi da gom ca viec lam moi trang thai khoa.
        if self._cho_nap:
            self._cho_nap = self._cho_lam_moi = False
            self._nap_du_lieu()
        elif self._cho_lam_moi:
            self._cho_lam_moi = False
            self._lam_moi_khoa()

    # ------------------------------------------------------------ du lieu

    def _nap_du_lieu(self):
        self._cap_nhat_trang_thai_key()
        try:
            ch = chh.doc_cau_hinh(CONFIG_PATH)
        except Exception as e:
            InfoBar.error(tr("google_title"), str(e), parent=self, position=InfoBarPosition.TOP)
            return
        self._ch = ch
        self._dien_model(ch.model)
        self.o_che_do.setCurrentIndex(chh.CAC_CHE_DO_GO_CHU.index(ch.che_do_go_chu))
        self.o_ngon_ngu.setText(", ".join(ch.ngon_ngu))
        self.o_tu_vung.setText(", ".join(ch.tu_vung))
        try:
            self.o_prompt.setPlainText(ch.doc_prompt())
        except OSError:
            self.o_prompt.setPlainText("")
        self.hang_luu_server.switch.setChecked(ch.luu_tren_server)
        self.hang_xoa_file.switch.setChecked(ch.xoa_file_tren_server)
        self.o_timeout.setValue(ch.timeout_giay)
        self.o_so_lan.setValue(ch.so_lan_thu_moi_doan)
        self.o_token_phut.setValue(ch.gioi_han_token_moi_phut)
        self.hang_tu_doi.switch.setChecked(ch.tu_doi_model)
        self.o_du_phong.setText(", ".join(ch.model_du_phong))
        self.o_so_lan_doi.setValue(ch.so_lan_thu_truoc_khi_doi)
        self.o_phut_khoa.setValue(int(round(ch.phut_khoa_khi_qua_tai)))
        self.hang_quay_lai.switch.setChecked(ch.quay_lai_model_chinh)
        self.o_doi_khi_cho.setValue(ch.doi_khi_cho_qua_giay)
        self.o_cho_toi_da.setValue(int(round(ch.cho_toi_da_khi_het_model_phut)))
        self.hang_khoa_truoc.switch.setChecked(ch.khoa_truoc_khi_cham_han_muc)
        self._bat_tat_doi_model(ch.tu_doi_model)
        self._cap_nhat_theo_model(ch.model)

    def _dien_model(self, chon: str):
        model_ui.dien_combo_model(self.o_model, model_ui.cac_model_biet(self._ch, self._model_tu_key), chon,
                                  sua_duoc=True)

    def _cau_hinh_tren_man_hinh(self) -> chh.CauHinh:
        return dataclasses.replace(
            self._ch,
            model=self.o_model.currentText().strip() or self._ch.model,
            tu_doi_model=self.hang_tu_doi.switch.isChecked(),
            model_du_phong=chh._danh_sach(self.o_du_phong.text()),
        )

    def _lam_moi_khoa(self):
        # Dang go ten model thi khong dien lai combo (con tro se nhay), chi cap nhat dong ghi chu.
        if not self.o_model.hasFocus():
            self._dien_model(self.o_model.currentText().strip())
        self._cap_nhat_theo_model(self.o_model.currentText())

    def _cap_nhat_theo_model(self, model: str):
        model = (model or "").strip()
        self.hang_che_do.setEnabled(chh.la_model_go_chu(model))
        khoa = model_ui.mo_ta_khoa(model) if model else None
        self.nhan_khoa_model.setText(tr("google_model_locked_note", khoa) if khoa else "")
        self.nhan_khoa_model.setVisible(bool(khoa))
        self.goi_y_rang_buoc.setText(model_ui.goi_y_rang_buoc(model))
        self._cap_nhat_chuoi()

    def _cap_nhat_chuoi(self):
        ch = self._cau_hinh_tren_man_hinh()
        chuoi = ch.chuoi_model()
        phan = []
        for m in chuoi:
            khoa = model_ui.mo_ta_khoa(m)
            phan.append(f"{m} ({khoa})" if khoa else m)
        chu = tr("google_fallback_chain", "  →  ".join(phan))
        bo_qua = [m for m in ch.model_du_phong if m not in chuoi and m != ch.model]
        if ch.tu_doi_model and bo_qua:
            chu += "\n" + tr("google_fallback_skipped", ", ".join(bo_qua))
        self.nhan_chuoi.setText(chu)

    def _bat_tat_doi_model(self, bat: bool):
        for h in (self.hang_du_phong, self.hang_so_lan_doi, self.hang_phut_khoa, self.hang_quay_lai,
                  self.hang_doi_khi_cho):
            h.setEnabled(bat)
        self._cap_nhat_chuoi()

    def _cap_nhat_trang_thai_key(self):
        key, nguon = ga.nguon_api_key()
        if not key:
            self.nhan_trang_thai_key.setText(tr("google_key_status_none"))
        elif nguon == ga.duong_dan_file_api_key():
            self.nhan_trang_thai_key.setText(tr("google_key_status_file", ga.che_api_key(key)))
        elif nguon == ga.duong_dan_key_google_ai_transcribe():
            self.nhan_trang_thai_key.setText(tr("google_key_status_gait", ga.che_api_key(key)))
        else:
            self.nhan_trang_thai_key.setText(tr("google_key_status_env", ga.che_api_key(key), nguon))
        self.nut_xoa_key.setEnabled(nguon == ga.duong_dan_file_api_key())

    def _luu_key(self):
        key = self.o_key.text().strip()
        if not key:
            return
        try:
            ga.luu_api_key(key)
        except OSError as e:
            InfoBar.error(tr("google_title"), str(e), parent=self, position=InfoBarPosition.TOP)
            return
        self.o_key.clear()
        self._cap_nhat_trang_thai_key()
        InfoBar.success(tr("google_title"), tr("google_key_saved"), parent=self,
                        position=InfoBarPosition.TOP)

    def _xoa_key(self):
        ga.luu_api_key("")
        self._cap_nhat_trang_thai_key()
        InfoBar.success(tr("google_title"), tr("google_key_deleted"), parent=self,
                        position=InfoBarPosition.TOP)

    def _kiem_tra(self):
        if self.luong_kiem_tra and self.luong_kiem_tra.isRunning():
            return
        # Uu tien key dang go tren man hinh, chua can bam Luu.
        key = self.o_key.text().strip() or ga.lay_api_key()
        if not key:
            self.nhan_trang_thai_key.setText(tr("google_key_status_none"))
            return
        self.nut_kiem_tra.setEnabled(False)
        self.vong_cho.setVisible(True)
        self.nhan_trang_thai_key.setText(tr("google_checking"))
        self.luong_kiem_tra = LuongKiemTraKetNoi(key, self)
        self.luong_kiem_tra.xong.connect(self._kiem_tra_xong)
        self.luong_kiem_tra.start()

    def _kiem_tra_xong(self, ok: bool, loi: str, model: list):
        self.nut_kiem_tra.setEnabled(True)
        self.vong_cho.setVisible(False)
        if not ok:
            self.nhan_trang_thai_key.setText(f"{tr('google_check_fail')}: {loi}")
            InfoBar.error(tr("google_check_fail"), loi, parent=self,
                          position=InfoBarPosition.TOP, duration=8000)
            return

        dang_chon = self.o_model.currentText().strip()
        self._model_tu_key = sorted(m for m in model if m.startswith("gemini"))
        self._dien_model(dang_chon)

        if dang_chon and dang_chon not in model:
            thong_bao = tr("google_check_model_missing", dang_chon)
            InfoBar.warning(tr("google_title"), thong_bao, parent=self,
                            position=InfoBarPosition.TOP, duration=8000)
        else:
            thong_bao = tr("google_check_ok", len(model))
            InfoBar.success(tr("google_title"), thong_bao, parent=self, position=InfoBarPosition.TOP)
        self.nhan_trang_thai_key.setText(thong_bao)

    def _prompt_mac_dinh(self):
        try:
            with open(os.path.join(APP_DIR, "prompt.txt"), "r", encoding="utf-8") as f:
                self.o_prompt.setPlainText(f.read().strip())
        except OSError as e:
            InfoBar.error(tr("google_title"), str(e), parent=self, position=InfoBarPosition.TOP)

    def _luu(self):
        model = self.o_model.currentText().strip()
        if not model:
            return
        khoa = model_ui.mo_ta_khoa(model)
        if khoa and model != self._ch.model:
            InfoBar.error(tr("google_title"), tr("google_model_locked", model, khoa), parent=self,
                          position=InfoBarPosition.TOP, duration=8000)
            return
        gia_tri = {
            ("GOOGLE_AI", "model"): model,
            ("GOOGLE_AI", "che_do_go_chu"): chh.CAC_CHE_DO_GO_CHU[self.o_che_do.currentIndex()],
            ("GOOGLE_AI", "ngon_ngu"): self.o_ngon_ngu.text().strip(),
            ("GOOGLE_AI", "tu_vung"): self.o_tu_vung.text().strip(),
            ("GOOGLE_AI", "luu_tren_server"): bool_txt(self.hang_luu_server.switch.isChecked()),
            ("GOOGLE_AI", "xoa_file_tren_server"): bool_txt(self.hang_xoa_file.switch.isChecked()),
            ("GOOGLE_AI", "timeout_giay"): self.o_timeout.value(),
            ("GOOGLE_AI", "so_lan_thu_moi_doan"): self.o_so_lan.value(),
            ("GOOGLE_AI", "gioi_han_token_moi_phut"): self.o_token_phut.value(),
            ("DOI_MODEL", "bat"): bool_txt(self.hang_tu_doi.switch.isChecked()),
            ("DOI_MODEL", "model_du_phong"): ", ".join(chh._danh_sach(self.o_du_phong.text())),
            ("DOI_MODEL", "so_lan_thu_truoc_khi_doi"): self.o_so_lan_doi.value(),
            ("DOI_MODEL", "phut_khoa_khi_qua_tai"): self.o_phut_khoa.value(),
            ("DOI_MODEL", "quay_lai_model_chinh"): bool_txt(self.hang_quay_lai.switch.isChecked()),
            ("DOI_MODEL", "doi_khi_cho_qua_giay"): self.o_doi_khi_cho.value(),
            ("DOI_MODEL", "cho_toi_da_khi_het_model_phut"): self.o_cho_toi_da.value(),
            ("DOI_MODEL", "khoa_truoc_khi_cham_han_muc"): bool_txt(self.hang_khoa_truoc.switch.isChecked()),
        }
        # Model khong di duoc voi cach nhan dien dang bat thi doi cach, khong de config o trang thai hong.
        cach_cu = self._ch.nn_cach
        cach_moi = chh.cach_thay_the(model, cach_cu)
        if cach_moi != cach_cu:
            gia_tri[("NGUOI_NOI", "cach_nhan_dien")] = cach_moi
        try:
            cio.dat_nhieu_gia_tri(gia_tri, CONFIG_PATH)
            ch = chh.doc_cau_hinh(CONFIG_PATH)
            p = tuyet_doi(ch.file_prompt)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(self.o_prompt.toPlainText().strip() + "\n")
        except Exception as e:
            InfoBar.error(tr("google_title"), str(e), parent=self, position=InfoBarPosition.TOP)
            return
        self._ch = ch
        su_kien.cau_hinh_doi.emit(TEN_TRANG)
        self._cap_nhat_theo_model(model)
        if cach_moi != cach_cu and ch.nn_bat:
            InfoBar.warning(tr("google_title"), tr("rb_auto_switched", model, model_ui.ten_cach(cach_cu),
                                                   model_ui.ten_cach(cach_moi)),
                            parent=self, position=InfoBarPosition.TOP, duration=10000)
        else:
            InfoBar.success(tr("google_title"), tr("common_saved"), parent=self, position=InfoBarPosition.TOP)

    def _doi_ngon_ngu(self, _ma):
        self.tieu_de.setText(tr("google_title"))
        self.nhan_key.setText(tr("google_key_section"))
        self.goi_y_key.setText(tr("google_key_hint", ga.duong_dan_file_api_key()))
        self.o_key.setPlaceholderText(tr("google_key_placeholder"))
        self.nut_luu_key.setText(tr("google_btn_save_key"))
        self.nut_xoa_key.setText(tr("google_btn_delete_key"))
        self.nut_kiem_tra.setText(tr("google_btn_check"))
        self.link_key.setText(tr("google_link_get_key"))
        self._cap_nhat_trang_thai_key()
        self.nhan_model.setText(tr("google_model_section"))
        chi_so = self.o_che_do.currentIndex()
        self.o_che_do.clear()
        self.o_che_do.addItems([tr("google_mode_smart"), tr("google_mode_verbatim")])
        self.o_che_do.setCurrentIndex(max(0, chi_so))
        self.goi_y_model.setText(tr("google_model_hint"))
        self.the_doi.doi_ngon_ngu()
        self.nhan_prompt.setText(tr("google_prompt_section"))
        self.nut_prompt_mac_dinh.setText(tr("common_restore_default"))
        self.nhan_gui.setText(tr("google_request_section"))
        self.goi_y_token.setText(tr("google_token_limit_hint"))
        self.nut_luu.setText(tr("common_save"))
        self._lam_moi_khoa()
        for h in (self.hang_model, self.hang_che_do, self.hang_ngon_ngu, self.hang_tu_vung,
                  self.hang_luu_server, self.hang_xoa_file, *self.hang_so):
            h.doi_ngon_ngu()
