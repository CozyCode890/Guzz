"""
presets.py
Ba bo tham so xu ly am thanh dung san, khop voi Nhom 3 (GUI): ngoi gan
giang vien (mic bat truc tiep giong noi), ngoi gan loa (giong bi thu lai
qua loa, thuong co tieng re/vo am), va giang vien di lai (dung giua lop roi
chay ra chay vao laptop, am luong len xuong theo khoang cach). Day la diem
khoi dau hop ly, nen nghe thu roi chinh lai o phan Tuy chinh trong app.

noise_sample_sec = do dai cua so (giay) de uoc luong san tieng on. Ngoi gan
loa thi tieng re kha deu, de cua so dai hon cho san tieng on on dinh, do bi
hut mat phu am cua giang vien.

can_bang_am_luong_giay = cua so (giay) cho buoc can bang am luong theo thoi
gian, 0 = tat. Chi preset giang vien di lai bat buoc nay. Preset do con:
  - ha ty_le_giam_on: doan giang vien dung xa von da nho va nhieu vang phong,
    giam on manh qua se an mat giong;
  - tang silence_thresh_offset va min_silence_len: cat it hon, vi luc giang
    vien vua di vua noi nho hoac dung lai go may thi van la bai giang;
  - noise_sample_sec ngan hon: san tieng on doi theo cho giang vien dung.
"""

CAC_TRUONG = (
    "target_dbfs",
    "silence_thresh_offset",
    "min_silence_len",
    "keep_silence",
    "noise_sample_sec",
    "bandpass_thap",
    "bandpass_cao",
    "ty_le_giam_on",
    "can_bang_am_luong_giay",
)

GAN_GIANG_VIEN = {
    "target_dbfs": -16.0,
    "silence_thresh_offset": 16,
    "min_silence_len": 700,
    "keep_silence": 300,
    "noise_sample_sec": 2.0,
    "bandpass_thap": 80,
    "bandpass_cao": 8000,
    "ty_le_giam_on": 0.85,
    "can_bang_am_luong_giay": 0.0,
}

GAN_LOA = {
    "target_dbfs": -18.0,
    "silence_thresh_offset": 14,
    "min_silence_len": 700,
    "keep_silence": 250,
    "noise_sample_sec": 3.0,
    "bandpass_thap": 80,
    "bandpass_cao": 6000,
    "ty_le_giam_on": 0.92,
    "can_bang_am_luong_giay": 0.0,
}

GIANG_VIEN_DI_LAI = {
    "target_dbfs": -16.0,
    "silence_thresh_offset": 20,
    "min_silence_len": 1000,
    "keep_silence": 400,
    "noise_sample_sec": 1.5,
    "bandpass_thap": 80,
    "bandpass_cao": 7000,
    "ty_le_giam_on": 0.8,
    "can_bang_am_luong_giay": 3.0,
}

CAC_PRESET = {
    "gan_giang_vien": GAN_GIANG_VIEN,
    "gan_loa": GAN_LOA,
    "giang_vien_di_lai": GIANG_VIEN_DI_LAI,
}


def nhan_dien_preset(gia_tri_hien_tai: dict) -> str:
    for ten, preset in CAC_PRESET.items():
        if all(gia_tri_hien_tai.get(k) == v for k, v in preset.items()):
            return ten
    return "tuy_chinh"
