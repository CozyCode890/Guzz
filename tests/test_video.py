"""
Xu ly file video: doc rung tieng, tach tieng ra file, va chay ca luong chuyen doi
tren mot file video that (can ffmpeg; Google AI duoc gia lap).
"""

import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import am_thanh_io  # noqa: E402
import cau_hinh  # noqa: E402
import chuyen_doi as cd  # noqa: E402
import video_io  # noqa: E402
from test_chuyen_doi import SR, MayKhachGia, tao_audio, van_ban  # noqa: E402

GIAY = 6


def tao_song(duong_dan, tan_so, giay=GIAY):
    """File wav mot tan so duy nhat, de nhan ra dang nghe rung nao."""
    t = np.arange(giay * SR) / SR
    am_thanh_io.ghi_audio((0.3 * np.sin(2 * np.pi * tan_so * t)).astype(np.float32), SR, duong_dan, "wav")


def tao_video(duong_dan, *cac_wav):
    """Video hinh den + mot rung tieng cho moi file wav truyen vao (khong wav nao = video cam)."""
    lenh = [am_thanh_io.tim_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-f", "lavfi", "-i", "color=c=black:s=64x64:r=5"]
    for w in cac_wav:
        lenh += ["-i", w]
    lenh += ["-map", "0:v"] + [x for i in range(len(cac_wav)) for x in ("-map", f"{i + 1}:a")]
    lenh += ["-c:v", "mpeg4", "-c:a", "aac", "-shortest" if cac_wav else "-t", "" if cac_wav else str(GIAY)]
    lenh = [x for x in lenh if x] + [duong_dan]
    kq = subprocess.run(lenh, capture_output=True)
    if kq.returncode != 0:
        raise RuntimeError(kq.stderr.decode("utf-8", "replace")[-800:])


def tan_so_troi(duong_dan, rung=None) -> float:
    """Tan so manh nhat trong file, de biet da lay dung rung tieng nao chua."""
    y = am_thanh_io.doc_audio(duong_dan, SR, rung=rung)
    pho = np.abs(np.fft.rfft(y[SR:SR * 3]))
    return float(np.fft.rfftfreq(len(y[SR:SR * 3]), 1 / SR)[int(np.argmax(pho))])


class TestChonRung(unittest.TestCase):
    """chon_rung() khong goi ffmpeg: chi la phep chon tren danh sach rung."""

    def setUp(self):
        self.rung = [video_io.RungAmThanh(i, i + 1) for i in range(3)]

    def test_auto_va_gia_tri_rong_lay_rung_dau(self):
        for yeu_cau in (None, "", "  ", "auto", "AUTO"):
            self.assertEqual(video_io.chon_rung(self.rung, yeu_cau), 0, yeu_cau)

    def test_so_hop_le_lay_dung_rung_do(self):
        self.assertEqual(video_io.chon_rung(self.rung, "2"), 2)
        self.assertEqual(video_io.chon_rung(self.rung, 1), 1)

    def test_so_ngoai_khoang_hoac_rac_thi_lui_ve_rung_dau(self):
        for yeu_cau in ("9", "-1", "hai"):
            self.assertEqual(video_io.chon_rung(self.rung, yeu_cau), 0, yeu_cau)

    def test_khong_co_rung_nao_tra_ve_none(self):
        self.assertIsNone(video_io.chon_rung([], "auto"))
        self.assertIsNone(video_io.chon_rung([], "0"))


class TestDocVaTachRung(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = cls.tmp.name
        cls.wav_thap, cls.wav_cao = os.path.join(d, "thap.wav"), os.path.join(d, "cao.wav")
        tao_song(cls.wav_thap, 300)
        tao_song(cls.wav_cao, 1500)
        cls.hai_rung = os.path.join(d, "hai rung.mp4")
        cls.cam = os.path.join(d, "khong tieng.mp4")
        tao_video(cls.hai_rung, cls.wav_thap, cls.wav_cao)
        tao_video(cls.cam)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_liet_ke_duoc_ca_hai_rung(self):
        rung = video_io.cac_rung_am_thanh(self.hai_rung)
        self.assertEqual([r.chi_so for r in rung], [0, 1])
        self.assertEqual([r.codec for r in rung], ["aac", "aac"])
        # Rung tieng dung sau rung hinh trong file, nen chi so stream bat dau tu 1.
        self.assertEqual([r.chi_so_stream for r in rung], [1, 2])
        self.assertIn("#0", rung[0].mo_ta())

    def test_video_khong_co_tieng_tra_ve_danh_sach_rong(self):
        self.assertEqual(video_io.cac_rung_am_thanh(self.cam), [])

    def test_file_audio_thuong_van_dem_duoc_rung(self):
        self.assertEqual(len(video_io.cac_rung_am_thanh(self.wav_thap)), 1)

    def test_file_hong_bao_loi_chu_khong_coi_la_khong_co_tieng(self):
        """Bo qua am tham mot file hong thi nguoi dung khong biet vi sao thieu ban go chu."""
        hong = os.path.join(self.tmp.name, "hong.mp4")
        with open(hong, "wb") as f:
            f.write(b"khong phai video" * 50)
        with self.assertRaises(RuntimeError):
            video_io.cac_rung_am_thanh(hong)

    def test_doc_audio_theo_rung_lay_dung_tieng(self):
        self.assertAlmostEqual(tan_so_troi(self.hai_rung, rung=0), 300, delta=15)
        self.assertAlmostEqual(tan_so_troi(self.hai_rung, rung=1), 1500, delta=15)
        # Khong chi dinh rung: ffmpeg lay rung mac dinh (rung dau).
        self.assertAlmostEqual(tan_so_troi(self.hai_rung), 300, delta=15)

    def test_tach_am_thanh_ghi_ra_dung_rung_va_khong_con_file_part(self):
        ra = os.path.join(self.tmp.name, "tach.flac")
        video_io.tach_am_thanh(self.hai_rung, ra, rung=1)
        self.assertTrue(os.path.getsize(ra) > 0)
        self.assertFalse(os.path.exists(ra + ".part"))
        self.assertAlmostEqual(tan_so_troi(ra), 1500, delta=15)
        self.assertEqual(video_io.cac_rung_am_thanh(ra)[0].codec, "flac")

    def test_tach_rung_khong_ton_tai_thi_bao_loi_va_don_file_part(self):
        ra = os.path.join(self.tmp.name, "hong.flac")
        with self.assertRaises(RuntimeError):
            video_io.tach_am_thanh(self.hai_rung, ra, rung=7)
        self.assertFalse(os.path.exists(ra))
        self.assertFalse(os.path.exists(ra + ".part"))


class TestCauHinhVideo(unittest.TestCase):
    def test_cac_duoi_nhan_gop_audio_va_video_khong_trung(self):
        ch = cau_hinh.CauHinh(duoi_file_nhan=(".mp3", ".mp4"), duoi_file_video=(".mp4", ".mkv"))
        self.assertEqual(ch.cac_duoi_nhan(), (".mp3", ".mp4", ".mkv"))

    def test_tat_nhan_video_thi_chi_con_duoi_audio(self):
        ch = cau_hinh.CauHinh(duoi_file_nhan=(".mp3",), nhan_file_video=False)
        self.assertEqual(ch.cac_duoi_nhan(), (".mp3",))
        # duoi_file_video van giu nguyen: la_file_video() chi noi ve dinh dang.
        self.assertTrue(ch.la_file_video("a.mp4"))

    def test_la_file_video_khong_phan_biet_hoa_thuong(self):
        ch = cau_hinh.CauHinh()
        self.assertTrue(ch.la_file_video(r"C:\a\B.MP4"))
        self.assertFalse(ch.la_file_video(r"C:\a\B.m4a"))

    def test_luu_am_thanh_tach_thi_van_phai_tach_du_tat_tach_truoc(self):
        ch = cau_hinh.CauHinh(video_tach_truoc=False, video_luu_am_thanh_tach=True)
        self.assertTrue(ch.can_tach_am_thanh_video())
        self.assertFalse(cau_hinh.CauHinh(video_tach_truoc=False).can_tach_am_thanh_video())

    def test_rung_am_thanh_sai_thi_kiem_tra_bao_loi(self):
        for gia_tri in ("rung 1", "-1", "auto2"):
            with self.assertRaises(ValueError, msg=gia_tri):
                cau_hinh.kiem_tra(cau_hinh.CauHinh(video_rung_am_thanh=gia_tri))
        cau_hinh.kiem_tra(cau_hinh.CauHinh(video_rung_am_thanh="3"))

    def test_dinh_dang_tach_sai_thi_kiem_tra_bao_loi(self):
        with self.assertRaises(ValueError):
            cau_hinh.kiem_tra(cau_hinh.CauHinh(video_dinh_dang_tach="m4a"))


class TestChuyenMotFileVideo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        wav_chinh, wav_phu = os.path.join(d, "chinh.wav"), os.path.join(d, "phu.wav")
        tao_audio(wav_chinh)                 # tin hieu "co tieng noi" 60 giay
        tao_song(wav_phu, 1500, giay=60)     # cung do dai: "-shortest" cat theo rung ngan nhat
        self.video = os.path.join(d, "bai giang.mp4")
        tao_video(self.video, wav_chinh, wav_phu)
        self.ch = cau_hinh.CauHinh(
            model="gemini-3.5-transcribe", tu_doi_model=False,
            thu_muc_tam=os.path.join(d, "tmp"), khu_on=False, level_window_sec=0,
            min_silence_len=1000, silence_thresh_offset=20, keep_silence=400,
            phut_moi_doan=0.4, giay_tim_cho_cat=3, giay_doan_cuoi_toi_thieu=5, dinh_dang_doan="wav",
            gioi_han_token_moi_phut=0, xuong_dong="lf", xoa_thu_muc_tam_khi_xong=False)

    def tearDown(self):
        self.tmp.cleanup()

    def chay(self, **doi):
        for k, v in doi.items():
            setattr(self.ch, k, v)
        kh = MayKhachGia(lambda i, kw: van_ban(f"Đoạn {i}."))
        return cd.chuyen_mot_file(self.ch, self.video, kh), kh

    def test_video_ra_ban_go_chu_va_tach_tieng_ra_thu_muc_tam(self):
        kq, kh = self.chay()
        self.assertEqual(kq.file_ra, os.path.join(self.tmp.name, "bai giang.txt"))
        self.assertGreaterEqual(kq.so_doan, 2)
        self.assertEqual(len(kh.cac_lan), kq.so_doan)
        tach = os.path.join(cd.thu_muc_tam_cho(self.ch, self.video), "am_thanh_video.flac")
        self.assertTrue(os.path.getsize(tach) > 0)
        self.assertAlmostEqual(tan_so_troi(tach), 220, delta=25)   # rung 0, khong phai rung 1500 Hz

    def test_chon_rung_khac_thi_tach_dung_rung_do(self):
        self.chay(video_rung_am_thanh="1")
        tach = os.path.join(cd.thu_muc_tam_cho(self.ch, self.video), "am_thanh_video.flac")
        self.assertAlmostEqual(tan_so_troi(tach), 1500, delta=15)

    def test_doi_rung_thi_khong_dung_lai_cac_doan_da_cat_cua_rung_cu(self):
        kq, _ = self.chay()
        self.ch.khi_trung_ten = "ghi_de"
        kq2, kh2 = self.chay(video_rung_am_thanh="1")
        # Ma bam doi theo rung -> phai cat doan va goi Google lai tu dau.
        self.assertEqual(len(kh2.cac_lan), kq2.so_doan)
        self.assertNotEqual(cd.ma_am_thanh(self.ch, self.video, (0, True, "flac")),
                            cd.ma_am_thanh(self.ch, self.video, (1, True, "flac")))
        self.assertGreater(kq.so_doan, 0)

    def test_khong_tach_truoc_van_doc_thang_tu_video(self):
        kq, kh = self.chay(video_tach_truoc=False)
        self.assertGreaterEqual(kq.so_doan, 2)
        self.assertEqual(len(kh.cac_lan), kq.so_doan)
        self.assertFalse(os.path.exists(
            os.path.join(cd.thu_muc_tam_cho(self.ch, self.video), "am_thanh_video.flac")))

    def test_luu_am_thanh_tach_chep_ra_canh_ban_go_chu(self):
        kq, _ = self.chay(video_luu_am_thanh_tach=True, video_tach_truoc=False)
        ra = os.path.splitext(kq.file_ra)[0] + ".am_thanh.flac"
        self.assertTrue(os.path.getsize(ra) > 0)

    def test_ma_bam_cua_file_audio_khong_doi_vi_them_phan_video(self):
        """File audio cu da co doan trong tmp thi doi app moi van dung lai duoc."""
        wav = os.path.join(self.tmp.name, "chinh.wav")
        self.assertEqual(cd.ma_am_thanh(self.ch, wav), cd.ma_am_thanh(self.ch, wav, None))


class TestVideoKhongCoTieng(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.video = os.path.join(self.tmp.name, "hinh khong tieng.mp4")
        tao_video(self.video)
        self.ch = cau_hinh.CauHinh(model="gemini-3.5-transcribe",
                                   thu_muc_tam=os.path.join(self.tmp.name, "tmp"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_mac_dinh_thi_bo_qua_va_khong_goi_google(self):
        kh = MayKhachGia(lambda i, kw: van_ban("x"))
        kq = cd.chuyen_mot_file(self.ch, self.video, kh)
        self.assertTrue(kq.bo_qua)
        self.assertIsNone(kq.file_ra)
        self.assertEqual(kh.cac_lan, [])

    def test_file_hong_van_bao_loi_du_dang_bat_bo_qua(self):
        hong = os.path.join(self.tmp.name, "hong.mp4")
        with open(hong, "wb") as f:
            f.write(b"khong phai video" * 50)
        with self.assertRaises(RuntimeError) as e:
            cd.chuyen_mot_file(self.ch, hong, MayKhachGia(lambda i, kw: van_ban("x")))
        self.assertNotIsInstance(e.exception, cd.KhongCoTieng)

    def test_tat_bo_qua_thi_bao_loi(self):
        self.ch.video_bo_qua_khong_tieng = False
        with self.assertRaises(cd.KhongCoTieng):
            cd.chuyen_mot_file(self.ch, self.video, MayKhachGia(lambda i, kw: van_ban("x")))


if __name__ == "__main__":
    unittest.main(verbosity=1)
