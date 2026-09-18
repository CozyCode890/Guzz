import os
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cau_hinh as chh  # noqa: E402
import han_muc as hm  # noqa: E402

UTC = timezone.utc


def epoch(*a) -> float:
    return datetime(*a, tzinfo=UTC).timestamp()


class DongHo:
    def __init__(self, t: float):
        self.t = t

    def __call__(self):
        return self.t


class TestGioPacific(unittest.TestCase):
    def test_mua_he(self):
        # 16:00 UTC = 09:00 PDT = 23:00 gio Viet Nam: van la ngay 17 o My.
        t = epoch(2026, 9, 17, 16, 0)
        self.assertEqual(hm.ngay_pacific(t), "2026-09-17")
        # Google tinh lai luc 0h PDT ngay 18 = 07:00 UTC = 14:00 gio Viet Nam.
        self.assertEqual(hm.luc_dat_lai_ngay(t), epoch(2026, 9, 18, 7, 0))
        self.assertEqual(hm.ngay_pacific(epoch(2026, 9, 17, 6, 30)), "2026-09-16")

    def test_mua_dong_va_hai_lan_doi_gio(self):
        self.assertEqual(hm.luc_dat_lai_ngay(epoch(2026, 1, 15, 12)), epoch(2026, 1, 16, 8))
        self.assertEqual(hm.lech_pacific(datetime(2026, 3, 8, 9, 59)), timedelta(hours=-8))
        self.assertEqual(hm.lech_pacific(datetime(2026, 3, 8, 10, 0)), timedelta(hours=-7))
        self.assertEqual(hm.lech_pacific(datetime(2026, 11, 1, 8, 59)), timedelta(hours=-7))
        self.assertEqual(hm.lech_pacific(datetime(2026, 11, 1, 9, 0)), timedelta(hours=-8))
        self.assertEqual(hm.luc_dat_lai_ngay(epoch(2026, 3, 7, 20)), epoch(2026, 3, 8, 8))
        self.assertEqual(hm.luc_dat_lai_ngay(epoch(2026, 3, 8, 20)), epoch(2026, 3, 9, 7))

    def test_dem_nguoc(self):
        self.assertEqual(hm.dem_nguoc(3 * 3600 + 5 * 60 + 9.4), "3:05:09")
        self.assertEqual(hm.dem_nguoc(-5), "0:00:00")


class TestSoTheoDoi(unittest.TestCase):
    def setUp(self):
        self.dh = DongHo(epoch(2026, 9, 17, 16, 0))
        self.so = hm.SoTheoDoi(None, dong_ho=self.dh)

    def test_khoa_het_han_thi_tu_mo(self):
        self.so.khoa("m", self.dh() + 600, hm.KHOA_QUA_TAI, "HTTP 500: high demand")
        self.assertEqual(self.so.trang_thai_khoa("m")[:3], (True, self.dh() + 600, hm.KHOA_QUA_TAI))
        dau = self.so.dau_hieu()
        self.dh.t += 601
        self.assertFalse(self.so.bi_khoa("m"))
        self.assertNotEqual(self.so.dau_hieu(), dau)
        self.assertEqual([s["loai"] for s in self.so.anh_chup()["su_kien"]], [hm.SK_KHOA, hm.SK_HET_KHOA])

    def test_khoa_ngay_khong_bi_rut_ngan_khoa_vinh_vien_phai_mo_tay(self):
        mo_lai = hm.luc_dat_lai_ngay(self.dh())
        self.so.khoa("m", mo_lai, hm.KHOA_HAN_MUC_NGAY)
        self.so.khoa("m", self.dh() + 600, hm.KHOA_QUA_TAI)
        self.assertEqual(self.so.trang_thai_khoa("m")[1:3], (mo_lai, hm.KHOA_HAN_MUC_NGAY))
        self.so.khoa("x", None, hm.KHOA_KHONG_TON_TAI)
        self.dh.t += 10 ** 7
        self.assertTrue(self.so.bi_khoa("x"))
        self.so.mo_khoa("x")
        self.assertFalse(self.so.bi_khoa("x"))

    def test_sang_ngay_moi_dat_lai_bo_dem_va_luu_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "su_dung.json")
            so = hm.SoTheoDoi(p, dong_ho=self.dh)
            so.ghi_yeu_cau("m", 15000)
            so.ghi_yeu_cau("m", 15000)
            so.hoc_han_muc("m", "rpd", 25)
            so.khoa("m", hm.luc_dat_lai_ngay(self.dh()), hm.KHOA_HAN_MUC_NGAY, "429")

            mo_lai = hm.SoTheoDoi(p, dong_ho=self.dh)   # nhu mo lai app
            self.assertEqual(mo_lai.yeu_cau_hom_nay("m"), 2)
            self.assertEqual(mo_lai.hoc_duoc("m"), {"rpd": 25})
            self.assertTrue(mo_lai.bi_khoa("m"))

            self.dh.t = hm.luc_dat_lai_ngay(self.dh()) + 1
            self.assertEqual(mo_lai.yeu_cau_hom_nay("m"), 0)
            self.assertFalse(mo_lai.bi_khoa("m"))
            self.assertEqual(mo_lai.anh_chup()["model"]["m"]["token_tong"], 30000)

    def test_gioi_han_khai_bao_hoc_duoc_va_mac_dinh(self):
        ch = chh.CauHinh(gioi_han_token_moi_phut=10000, han_muc_model={"a": (0, 5, 0)})
        self.so.hoc_han_muc("a", "rpd", 25)
        self.so.hoc_han_muc("b", "tpm", 250000)
        self.assertEqual(self.so.gioi_han(ch, "a"), hm.HanMuc(0, 5, 25))
        self.assertEqual(self.so.gioi_han(ch, "b"), hm.HanMuc(250000, 0, 0))
        self.assertEqual(self.so.gioi_han(ch, "c"), hm.HanMuc(10000, 0, 0))

    def test_dang_cho(self):
        self.so.dat_dang_cho("m", "tpm", self.dh() + 39, "10000")
        self.assertEqual(self.so.anh_chup()["dang_cho"]["ly_do"], "tpm")
        self.so.xoa_dang_cho()
        self.assertIsNone(self.so.anh_chup()["dang_cho"])


class TestDungChungVoiAppKia(unittest.TestCase):
    """
    su_dung.json dung chung cho Guzz va GoogleAITranscribe: hai tien trinh cung ghi
    mot file, moi lan sua deu gianh khoa file va doc lai truoc, nen khong ben nao
    de len so dem cua ben kia.
    """

    def setUp(self):
        thu_muc = tempfile.TemporaryDirectory()
        self.addCleanup(thu_muc.cleanup)
        self.thu_muc = thu_muc.name
        self.p = os.path.join(self.thu_muc, "su_dung.json")
        self.dh = DongHo(epoch(2026, 9, 18, 20, 0))

    def test_ghi_xen_ke_khong_mat_so_dem(self):
        a = hm.SoTheoDoi(self.p, dong_ho=self.dh)       # app nay
        b = hm.SoTheoDoi(self.p, dong_ho=self.dh)       # app kia, dang mo cung luc
        a.ghi_yeu_cau("m", 100)
        b.ghi_yeu_cau("m", 50)
        a.ghi_yeu_cau("m", 100)
        tren_dia = hm.doc_file(self.p, "2026-09-18")["model"]["m"]
        self.assertEqual(tren_dia["yeu_cau_hom_nay"], 3)
        self.assertEqual(tren_dia["token_hom_nay"], 250)
        self.assertEqual(b.yeu_cau_hom_nay("m"), 3)     # b doc lai, thay ca phan cua a

    def test_khoa_ben_nay_ben_kia_thay_ngay(self):
        a = hm.SoTheoDoi(self.p, dong_ho=self.dh)
        b = hm.SoTheoDoi(self.p, dong_ho=self.dh)
        a.khoa("m", self.dh() + 600, hm.KHOA_QUA_TAI, "503")
        self.assertTrue(b.bi_khoa("m"))
        self.assertEqual(len(b.anh_chup()["su_kien"]), 1)
        b.mo_khoa("m")
        self.assertFalse(a.bi_khoa("m"))

    def test_khoa_file_khong_cho_hai_ben_ghi_cung_luc(self):
        with hm.khoa_file(self.p) as duoc:
            self.assertTrue(duoc)
            with hm.khoa_file(self.p, giay_cho=0.05) as duoc_nua:
                self.assertFalse(duoc_nua)  # ben thu hai cho het gio roi ghi luon
        with hm.khoa_file(self.p, giay_cho=0.05) as sau_khi_nha:
            self.assertTrue(sau_khi_nha)


class TestGopFileCu(unittest.TestCase):
    """Chuyen su_dung.json cu cua tung app vao file dung chung."""

    def setUp(self):
        thu_muc = tempfile.TemporaryDirectory()
        self.addCleanup(thu_muc.cleanup)
        self.thu_muc = thu_muc.name
        self.t = epoch(2026, 9, 18, 20, 0)
        self.dh = DongHo(self.t)

    def _so(self, ten: str) -> "hm.SoTheoDoi":
        return hm.SoTheoDoi(os.path.join(self.thu_muc, ten), dong_ho=self.dh)

    def test_gop_cong_so_dem_giu_khoa_va_tron_lich_su(self):
        a, b = self._so("a.json"), self._so("b.json")
        a.ghi_yeu_cau("m", 100)
        a.khoa("m", self.t + 600, hm.KHOA_QUA_TAI, "503")
        b.ghi_yeu_cau("m", 40)
        b.ghi_yeu_cau("x", 10)
        b.hoc_han_muc("x", "rpd", 25)

        kq = hm.gop(a.anh_chup(), b.anh_chup())
        self.assertEqual(sorted(kq["model"]), ["m", "x"])
        self.assertEqual(kq["model"]["m"]["yeu_cau_hom_nay"], 2)
        self.assertEqual(kq["model"]["m"]["token_hom_nay"], 140)
        self.assertEqual(kq["model"]["m"]["ly_do_khoa"], hm.KHOA_QUA_TAI)   # ben nao khoa thi giu
        self.assertEqual(kq["model"]["x"]["hoc_duoc"], {"rpd": 25})
        self.assertEqual([sk["loai"] for sk in kq["su_kien"]], [hm.SK_KHOA, hm.SK_HOC_HAN_MUC])

    def test_gop_bo_so_trong_ngay_cua_ben_da_sang_ngay_khac(self):
        a, b = self._so("a.json"), self._so("b.json")
        a.ghi_yeu_cau("m", 100)
        self.dh.t = hm.luc_dat_lai_ngay(self.t) + 60     # b lam viec o ngay hom sau
        b.ghi_yeu_cau("m", 40)

        kq = hm.gop(a.anh_chup(), b.anh_chup())
        self.assertEqual(kq["ngay"], hm.ngay_pacific(self.dh()))
        self.assertEqual(kq["model"]["m"]["yeu_cau_hom_nay"], 1)    # chi con phan cua b
        self.assertEqual(kq["model"]["m"]["token_hom_nay"], 40)
        self.assertEqual(kq["model"]["m"]["yeu_cau_tong"], 2)       # tong thi van cong het
        self.assertEqual(kq["model"]["m"]["token_tong"], 140)

    def test_gop_file_cu_roi_doi_ten_de_lan_sau_khong_gop_lai(self):
        cu = os.path.join(self.thu_muc, "cu", "su_dung.json")
        chung = os.path.join(self.thu_muc, "chung", "su_dung.json")
        self._so(os.path.join("cu", "su_dung.json")).ghi_yeu_cau("m", 100)
        with mock.patch("duong_dan_chung.cac_file_su_dung_cu", side_effect=lambda: [cu]
                        if os.path.isfile(cu) else []):
            self.assertEqual(hm.gop_file_cu(chung), [cu])
            self.assertFalse(os.path.exists(cu))
            self.assertTrue(os.path.exists(cu + hm.DUOI_DA_GOP))
            self.assertEqual(hm.SoTheoDoi(chung, dong_ho=self.dh).yeu_cau_hom_nay("m"), 1)
            self.assertEqual(hm.gop_file_cu(chung), [])         # khong con gi de gop


if __name__ == "__main__":
    unittest.main()
