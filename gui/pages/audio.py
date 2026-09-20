from __future__ import annotations

from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout
from qfluentwidgets import (
    TitleLabel, StrongBodyLabel, CardWidget, SegmentedWidget, SwitchButton,
    SpinBox, DoubleSpinBox, ComboBox, PrimaryPushButton, FluentIcon,
    InfoBar, InfoBarPosition,
)

import cau_hinh as chh
from paths import CONFIG_PATH
from su_kien import su_kien
from i18n import tr, bo_dich
import config_io as cio
import presets
from widgets import Hang, HangSwitch, TrangCuon, bool_txt, chu_goi_y, dich_cong_tac

TEN_TRANG = "am_thanh"

# So rung tieng cho chon trong o "Rung tieng se dung". Video nhieu hon the nay
# thi sua thang rung_am_thanh trong config.txt.
SO_RUNG_CHON = 8


class TrangAmThanh(TrangCuon):
    def __init__(self, parent=None):
        super().__init__("audioInterface", parent)
        khung, root = self.khung, self.root
        self._dang_nap = False
        self._cho_nap = False

        self.tieu_de = TitleLabel(tr("audio_title"), khung)
        root.addWidget(self.tieu_de)

        # ---- Lam sach ----
        the_sach = CardWidget(khung)
        lay_sach = QVBoxLayout(the_sach)
        self.nhan_sach = StrongBodyLabel(tr("audio_clean_section"), the_sach)
        lay_sach.addWidget(self.nhan_sach)
        self.hang_khu_on = HangSwitch("audio_denoise", parent=the_sach)
        self.hang_cat_lang = HangSwitch("audio_trim", "audio_trim_hint", the_sach)
        lay_sach.addWidget(self.hang_khu_on)
        lay_sach.addWidget(self.hang_cat_lang)

        self.pivot = SegmentedWidget(the_sach)
        for ten, key in (("gan_giang_vien", "audio_preset_near_lecturer"),
                         ("gan_loa", "audio_preset_near_speaker"),
                         ("giang_vien_di_lai", "audio_preset_moving"),
                         ("tuy_chinh", "audio_preset_custom")):
            # itemClicked(bool) phat kem True: tham so dau tien phai nuot no, khong thi de len t.
            self.pivot.addItem(ten, tr(key), lambda _=None, t=ten: self._chon_preset(t))
        lay_sach.addWidget(self.pivot)
        self.goi_y_preset = chu_goi_y("audio_preset_hint", the_sach)
        lay_sach.addWidget(self.goi_y_preset)
        root.addWidget(the_sach)

        hang_nang_cao = QHBoxLayout()
        self.nhan_nang_cao = StrongBodyLabel(tr("audio_advanced"), khung)
        self.bat_nang_cao = SwitchButton(khung)
        dich_cong_tac(self.bat_nang_cao)
        self.bat_nang_cao.checkedChanged.connect(lambda hien: self.khung_nang_cao.setVisible(hien))
        hang_nang_cao.addWidget(self.nhan_nang_cao)
        hang_nang_cao.addWidget(self.bat_nang_cao)
        hang_nang_cao.addStretch(1)
        root.addLayout(hang_nang_cao)

        self.khung_nang_cao = QFrame(khung)
        lay_nc = QVBoxLayout(self.khung_nang_cao)
        lay_nc.setContentsMargins(0, 0, 0, 0)

        def so_thuc(tu, den, buoc):
            o = DoubleSpinBox()
            o.setRange(tu, den)
            o.setSingleStep(buoc)
            return o

        def so_nguyen(tu, den, buoc=1):
            o = SpinBox()
            o.setRange(tu, den)
            o.setSingleStep(buoc)
            return o

        # key trong config.txt -> (nhan, o nhap)
        self.o = {
            "target_dbfs": ("audio_target_dbfs", so_thuc(-40, 0, 0.5)),
            "silence_thresh_offset": ("audio_silence_offset", so_nguyen(1, 60)),
            "min_silence_len": ("audio_min_silence", so_nguyen(100, 5000, 50)),
            "keep_silence": ("audio_keep_silence", so_nguyen(0, 2000, 50)),
            "noise_sample_sec": ("audio_noise_sample", so_thuc(0.2, 10.0, 0.1)),
            "bandpass_thap": ("audio_bandpass_low", so_nguyen(20, 2000)),
            "bandpass_cao": ("audio_bandpass_high", so_nguyen(2000, 16000)),
            "ty_le_giam_on": ("audio_prop_decrease", so_thuc(0.0, 1.0, 0.01)),
            "can_bang_am_luong_giay": ("audio_level_window", so_thuc(0.0, 30.0, 0.5)),
            "tan_so_lay_mau": ("audio_resample", so_nguyen(8000, 48000, 1000)),
        }
        self.cac_hang = []
        for key, (nhan, o_nhap) in self.o.items():
            h = Hang(nhan, o_nhap, self.khung_nang_cao)
            lay_nc.addWidget(h)
            self.cac_hang.append(h)
            if key in presets.CAC_TRUONG:
                o_nhap.valueChanged.connect(self._danh_dau_tuy_chinh)
        self.khung_nang_cao.setVisible(False)
        root.addWidget(self.khung_nang_cao)

        # ---- Cat doan ----
        the_doan = CardWidget(khung)
        lay_doan = QVBoxLayout(the_doan)
        self.nhan_doan = StrongBodyLabel(tr("audio_chunk_section"), the_doan)
        lay_doan.addWidget(self.nhan_doan)
        self.o_phut = so_nguyen(1, 60)
        self.o_tim = so_nguyen(0, 120)
        self.o_cuoi = so_nguyen(0, 600, 10)
        self.o_dinh_dang = ComboBox()
        self.o_dinh_dang.addItems(list(chh.CAC_DINH_DANG_DOAN))
        self.hang_doan = [
            Hang("audio_chunk_minutes", self.o_phut, the_doan),
            Hang("audio_chunk_search", self.o_tim, the_doan),
            Hang("audio_chunk_last_min", self.o_cuoi, the_doan),
            Hang("audio_chunk_format", self.o_dinh_dang, the_doan),
        ]
        for h in self.hang_doan:
            lay_doan.addWidget(h)
        self.goi_y_doan = chu_goi_y("audio_chunk_hint", the_doan)
        lay_doan.addWidget(self.goi_y_doan)
        root.addWidget(the_doan)

        # ---- Video ----
        the_video = CardWidget(khung)
        lay_video = QVBoxLayout(the_video)
        self.nhan_video = StrongBodyLabel(tr("video_section"), the_video)
        lay_video.addWidget(self.nhan_video)
        self.goi_y_video = chu_goi_y("video_section_hint", the_video)
        lay_video.addWidget(self.goi_y_video)

        self.hang_nhan_video = HangSwitch("video_accept", "video_accept_hint", the_video)
        self.o_rung = ComboBox()
        self.o_rung.setMinimumWidth(240)
        self.o_dinh_dang_tach = ComboBox()
        self.o_dinh_dang_tach.addItems(list(chh.CAC_DINH_DANG_DOAN))
        self.hang_rung = Hang("video_track", self.o_rung, the_video)
        self.goi_y_rung = chu_goi_y("video_track_hint", the_video)
        self.hang_tach_truoc = HangSwitch("video_extract_first", "video_extract_first_hint", the_video)
        self.hang_dinh_dang_tach = Hang("video_extract_format", self.o_dinh_dang_tach, the_video)
        self.hang_luu_tach = HangSwitch("video_save_extracted", "video_save_extracted_hint", the_video)
        self.hang_bo_qua_cam = HangSwitch("video_skip_silent", "video_skip_silent_hint", the_video)
        self.hang_video = [self.hang_nhan_video, self.hang_rung, self.hang_tach_truoc,
                           self.hang_dinh_dang_tach, self.hang_luu_tach, self.hang_bo_qua_cam]
        lay_video.addWidget(self.hang_nhan_video)
        lay_video.addWidget(self.hang_rung)
        lay_video.addWidget(self.goi_y_rung)
        for h in (self.hang_tach_truoc, self.hang_dinh_dang_tach, self.hang_luu_tach, self.hang_bo_qua_cam):
            lay_video.addWidget(h)
        # Tat nhan file video thi cac o con lai khong con y nghia.
        self.hang_nhan_video.switch.checkedChanged.connect(self._bat_tat_video)
        root.addWidget(the_video)

        root.addStretch(1)
        self.nut_luu = PrimaryPushButton(FluentIcon.SAVE, tr("common_save"), khung)
        self.nut_luu.clicked.connect(self._luu)
        root.addWidget(self.nut_luu)

        bo_dich.doi_ngon_ngu.connect(self._doi_ngon_ngu)
        su_kien.cau_hinh_doi.connect(self._cau_hinh_doi)
        self._dien_combo_rung()
        self._nap_du_lieu()

    def _cau_hinh_doi(self, nguon: str):
        """Trang dang an thi de danh, mo ra moi nap lai (xem showEvent)."""
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

    # ------------------------------------------------------------ video

    def _dien_combo_rung(self):
        """Tu dong + rang tieng thu 1..SO_RUNG_CHON. Rang duoc danh so tu 0 trong config,
        nhung hien ra tu 1 cho de hieu."""
        gia_tri = self._gia_tri_rung()
        self.o_rung.blockSignals(True)
        self.o_rung.clear()
        self.o_rung.addItem(tr("video_track_auto"), userData=chh.RUNG_TU_DONG)
        for i in range(SO_RUNG_CHON):
            self.o_rung.addItem(tr("video_track_n", i + 1), userData=str(i))
        self._dat_rung(gia_tri)
        self.o_rung.blockSignals(False)

    def _gia_tri_rung(self) -> str:
        return self.o_rung.currentData() or chh.RUNG_TU_DONG

    def _dat_rung(self, gia_tri: str):
        for i in range(self.o_rung.count()):
            if self.o_rung.itemData(i) == gia_tri:
                self.o_rung.setCurrentIndex(i)
                return
        self.o_rung.setCurrentIndex(0)

    def _bat_tat_video(self, bat: bool):
        for h in self.hang_video[1:]:
            h.setEnabled(bat)
        self.goi_y_rung.setEnabled(bat)

    def _gia_tri_preset_hien_tai(self) -> dict:
        return {k: self.o[k][1].value() for k in presets.CAC_TRUONG}

    def _danh_dau_tuy_chinh(self, *_):
        if not self._dang_nap:
            self.pivot.setCurrentItem(presets.nhan_dien_preset(self._gia_tri_preset_hien_tai()))

    def _chon_preset(self, ten: str):
        self.pivot.setCurrentItem(ten)
        if ten == "tuy_chinh":
            return
        self._dang_nap = True
        for k, v in presets.CAC_PRESET[ten].items():
            self.o[k][1].setValue(v)
        self._dang_nap = False

    def _nap_du_lieu(self):
        try:
            ch = chh.doc_cau_hinh(CONFIG_PATH)
        except Exception as e:
            InfoBar.error(tr("audio_title"), str(e), parent=self, position=InfoBarPosition.TOP)
            return

        self._dang_nap = True
        self.hang_khu_on.switch.setChecked(ch.khu_on)
        self.hang_cat_lang.switch.setChecked(ch.cat_khoang_lang)
        gia_tri = {
            "target_dbfs": ch.target_dbfs,
            "silence_thresh_offset": ch.silence_thresh_offset,
            "min_silence_len": ch.min_silence_len,
            "keep_silence": ch.keep_silence,
            "noise_sample_sec": ch.noise_sample_sec,
            "bandpass_thap": ch.bandpass_low,
            "bandpass_cao": ch.bandpass_high,
            "ty_le_giam_on": ch.prop_decrease,
            "can_bang_am_luong_giay": ch.level_window_sec,
            "tan_so_lay_mau": ch.tan_so_lay_mau,
        }
        for k, v in gia_tri.items():
            self.o[k][1].setValue(v)
        self.o_phut.setValue(max(1, round(ch.phut_moi_doan)))
        self.o_tim.setValue(int(ch.giay_tim_cho_cat))
        self.o_cuoi.setValue(int(ch.giay_doan_cuoi_toi_thieu))
        self.o_dinh_dang.setCurrentText(ch.dinh_dang_doan)

        self.hang_nhan_video.switch.setChecked(ch.nhan_file_video)
        self._dat_rung(ch.video_rung_am_thanh)
        self.hang_tach_truoc.switch.setChecked(ch.video_tach_truoc)
        self.o_dinh_dang_tach.setCurrentText(ch.video_dinh_dang_tach)
        self.hang_luu_tach.switch.setChecked(ch.video_luu_am_thanh_tach)
        self.hang_bo_qua_cam.switch.setChecked(ch.video_bo_qua_khong_tieng)
        self._bat_tat_video(ch.nhan_file_video)
        self._dang_nap = False

        self.pivot.setCurrentItem(presets.nhan_dien_preset(self._gia_tri_preset_hien_tai()))

    def _luu(self):
        thay_doi = {
            ("XU_LY_AM_THANH", "khu_on"): str(self.hang_khu_on.switch.isChecked()).lower(),
            ("XU_LY_AM_THANH", "cat_khoang_lang"): str(self.hang_cat_lang.switch.isChecked()).lower(),
            ("CAT_DOAN", "phut_moi_doan"): self.o_phut.value(),
            ("CAT_DOAN", "giay_tim_cho_cat"): self.o_tim.value(),
            ("CAT_DOAN", "giay_doan_cuoi_toi_thieu"): self.o_cuoi.value(),
            ("CAT_DOAN", "dinh_dang_doan"): self.o_dinh_dang.currentText(),
            ("XU_LY_VIDEO", "nhan_file_video"): bool_txt(self.hang_nhan_video.switch.isChecked()),
            ("XU_LY_VIDEO", "rung_am_thanh"): self._gia_tri_rung(),
            ("XU_LY_VIDEO", "tach_am_thanh_truoc"): bool_txt(self.hang_tach_truoc.switch.isChecked()),
            ("XU_LY_VIDEO", "dinh_dang_tach"): self.o_dinh_dang_tach.currentText(),
            ("XU_LY_VIDEO", "luu_am_thanh_tach"): bool_txt(self.hang_luu_tach.switch.isChecked()),
            ("XU_LY_VIDEO", "bo_qua_video_khong_tieng"):
                bool_txt(self.hang_bo_qua_cam.switch.isChecked()),
        }
        for k, (_, o_nhap) in self.o.items():
            v = o_nhap.value()
            thay_doi[("XU_LY_AM_THANH", k)] = round(v, 3) if isinstance(v, float) else v
        try:
            cio.dat_nhieu_gia_tri(thay_doi, CONFIG_PATH)
            chh.doc_cau_hinh(CONFIG_PATH)
        except Exception as e:
            InfoBar.error(tr("audio_title"), str(e), parent=self, position=InfoBarPosition.TOP)
            return
        su_kien.cau_hinh_doi.emit(TEN_TRANG)
        InfoBar.success(tr("audio_title"), tr("common_saved"), parent=self,
                        position=InfoBarPosition.TOP)

    def _doi_ngon_ngu(self, _ma):
        self.tieu_de.setText(tr("audio_title"))
        self.nhan_sach.setText(tr("audio_clean_section"))
        for ten, key in (("gan_giang_vien", "audio_preset_near_lecturer"),
                         ("gan_loa", "audio_preset_near_speaker"),
                         ("giang_vien_di_lai", "audio_preset_moving"),
                         ("tuy_chinh", "audio_preset_custom")):
            self.pivot.setItemText(ten, tr(key))
        self.goi_y_preset.setText(tr("audio_preset_hint"))
        self.nhan_nang_cao.setText(tr("audio_advanced"))
        dich_cong_tac(self.bat_nang_cao)
        self.nhan_doan.setText(tr("audio_chunk_section"))
        self.goi_y_doan.setText(tr("audio_chunk_hint"))
        self.nhan_video.setText(tr("video_section"))
        self.goi_y_video.setText(tr("video_section_hint"))
        self.goi_y_rung.setText(tr("video_track_hint"))
        self._dien_combo_rung()
        self.nut_luu.setText(tr("common_save"))
        for h in (self.hang_khu_on, self.hang_cat_lang, *self.cac_hang, *self.hang_doan,
                  *self.hang_video):
            h.doi_ngon_ngu()
