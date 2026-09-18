import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cau_hinh  # noqa: E402
import nguoi_noi as nn  # noqa: E402
from xu_ly_am_thanh import BanDoThoiGian  # noqa: E402

L = nn.LuotNoi


def ch(**them):
    c = cau_hinh.CauHinh()
    for k, v in them.items():
        setattr(c, k, v)
    return c


class TestBanDoThoiGian(unittest.TestCase):
    def setUp(self):
        # Giu [10, 20] va [30, 50] cua file goc 60 giay -> audio da cat dai 30 giay.
        self.bd = BanDoThoiGian([(10, 20), (30, 50)], 60)

    def test_sang_goc(self):
        self.assertEqual(self.bd.thoi_luong_sach, 30)
        self.assertEqual(self.bd.sang_goc(0), 10)
        self.assertEqual(self.bd.sang_goc(9.5), 19.5)
        self.assertEqual(self.bd.sang_goc(10), 30)
        self.assertEqual(self.bd.sang_goc(25), 45)
        self.assertEqual(self.bd.sang_goc(99), 50)

    def test_sang_sach_khoang_bi_cat_lay_dau_doan_sau(self):
        self.assertEqual(self.bd.sang_sach(5), 0)
        self.assertEqual(self.bd.sang_sach(15), 5)
        self.assertEqual(self.bd.sang_sach(25), 10)
        self.assertEqual(self.bd.sang_sach(40), 20)
        self.assertEqual(self.bd.sang_sach(59), 30)

    def test_khong_cat(self):
        bd = BanDoThoiGian.khong_cat(100)
        self.assertEqual(bd.sang_goc(42), 42)
        self.assertEqual(bd.sang_sach(42), 42)


class TestLuotNoi(unittest.TestCase):
    def test_quy_tac_kep_tra_manh_ngan_ve_giang_vien(self):
        ds = [L(0, 30, "A"), L(30.5, 31.5, "B"), L(32, 60, "A")]
        so = nn.lam_muot(ds, list(ds), toi_thieu=0)
        self.assertEqual(so, 1)
        self.assertEqual([l.nguoi_noi for l in ds], ["A", "A", "A"])
        self.assertEqual(len(nn.gop_luot(ds, 1.0)), 1)

    def test_quy_tac_mat_do_giu_hoi_dap_that(self):
        luot = [L(0, 100, "A"), L(100, 104, "B"), L(104, 110, "A")]
        # Nguoi hoi noi 4 giay trong +-60 giay: tra ve giang vien.
        ds = [L(l.bat_dau, l.ket_thuc, l.nguoi_noi) for l in luot]
        nn.lam_muot(ds, luot, kep_toi_da=0)
        self.assertEqual(ds[1].nguoi_noi, "A")
        # Hoi dap qua lai 20 giay thi giu nguyen.
        luot = [L(0, 100, "A"), L(100, 110, "B"), L(110, 115, "A"), L(115, 125, "B")]
        ds = [L(l.bat_dau, l.ket_thuc, l.nguoi_noi) for l in luot]
        nn.lam_muot(ds, luot, kep_toi_da=0)
        self.assertEqual([l.nguoi_noi for l in ds], ["A", "B", "A", "B"])

    def test_bang_ten(self):
        ds = [L(0, 5, "S1"), L(5, 60, "S0"), L(60, 65, "S2")]
        self.assertEqual(nn.bang_ten(ds, ch()), {"S0": "Giảng viên", "S1": "Người hỏi 1", "S2": "Người hỏi 2"})
        self.assertEqual(nn.bang_ten(ds, ch(nn_dat_ten_nguoi_chinh=False, nn_ten_chung="Speaker")),
                         {"S1": "Speaker 1", "S0": "Speaker 2", "S2": "Speaker 3"})

    def test_cat_theo_doan_va_ban_do(self):
        ds = [L(590, 605, "S0"), L(605, 606, "S1"), L(1300, 1310, "S0")]
        doan = nn.cat_theo_doan(ds, 600, 1200)
        self.assertEqual(doan, [L(0, 5, "S0"), L(5, 6, "S1")])
        van_ban = nn.ban_do_van_ban(doan, {"S0": "Giảng viên", "S1": "Người hỏi 1"})
        self.assertIn("00:00.0 - 00:05.0  Giảng viên\n00:05.0 - 00:06.0  Người hỏi 1\n", van_ban)
        self.assertEqual(nn.ten_trong_doan(doan, {"S0": "Giảng viên", "S1": "Người hỏi 1"}),
                         ["Giảng viên", "Người hỏi 1"])
        self.assertIn("no speech", nn.ban_do_van_ban([], {}))


class TestDocBanGoChuPrompt(unittest.TestCase):
    def test_moc_ten_dam_va_dong_khong_ten(self):
        van_ban = ("[00:05] Giảng viên: Hôm nay học SVM.\n\n"
                   "**Người hỏi 1:** Thưa thầy, ví dụ: kernel là gì?\n"
                   "Ví dụ: một dòng không có tên\n"
                   "[01:02:03]\nGiảng viên:\n\nKernel là hàm.")
        bd = BanDoThoiGian([(100, 5000)])
        kq = nn.doc_doan_van_prompt(van_ban, ["Giảng viên", "Người hỏi 1"], 600, bd.sang_goc)
        self.assertEqual([(d.nguoi_noi, d.moc, d.noi_dung) for d in kq], [
            ("Giảng viên", 705, "Hôm nay học SVM."),
            ("Người hỏi 1", None, "Thưa thầy, ví dụ: kernel là gì?"),
            ("Người hỏi 1", None, "Ví dụ: một dòng không có tên"),
            ("Giảng viên", 100 + 600 + 3723, "Kernel là hàm."),
        ])

    def test_hien_thi_mau(self):
        d = nn.DoanVan("abc", "Giảng viên", 3725.4, xem_lai=True)
        self.assertEqual(nn.hien_thi_doan(d, "[{moc}] {nguoi}: {noi_dung}", True, True),
                         "[01:02:05] Giảng viên: [?] abc")
        self.assertEqual(nn.hien_thi_doan(d, "[{moc}] {nguoi}: {noi_dung}", False, False),
                         "Giảng viên: abc")
        self.assertEqual(nn.hien_thi_doan(d, "{nguoi} ({moc}): {noi_dung}", False, False),
                         "Giảng viên: abc")
        self.assertEqual(nn.hien_thi_doan(nn.DoanVan("x"), "{nguoi}: {noi_dung}", True, True), "x")


class TestGhepTu(unittest.TestCase):
    def test_gan_lam_muot_gop(self):
        tu = [{"tu": w, "nguoi_noi": None, "bat_dau": i * 0.5, "ket_thuc": i * 0.5 + 0.4}
              for i, w in enumerate("Hôm nay , chúng ta học ( SVM ) .".split())]
        cau = nn.tu_sang_cau(tu, bu_moc=100)
        luot = [L(100, 102.2, "S0"), L(102.2, 102.9, "S1"), L(102.9, 200, "S0")]
        nn.gan_nguoi_noi(cau, luot)
        self.assertEqual(cau[5].nguoi_noi, "S1")
        nn.lam_muot(cau, luot, toi_thieu=0)
        self.assertTrue(all(c.nguoi_noi == "S0" for c in cau))
        nn.doi_ten(cau, nn.bang_ten(cau, ch(), chinh="S0"))
        gop = nn.gop_cau(cau)
        self.assertEqual(len(gop), 1)
        self.assertEqual(gop[0].noi_dung, "Hôm nay, chúng ta học (SVM).")
        self.assertEqual(gop[0].nguoi_noi, "Giảng viên")
        self.assertEqual(gop[0].bat_dau, 100)

    def test_gop_ngat_khi_nghi_lau(self):
        cau = [nn.Cau(0, 1, "a", "X"), nn.Cau(1.2, 2, "b", "X"), nn.Cau(6, 7, "c", "X"), nn.Cau(7, 8, "d", "Y")]
        self.assertEqual([c.noi_dung for c in nn.gop_cau(cau, 60, 3)], ["a b", "c", "d"])


if __name__ == "__main__":
    unittest.main()
