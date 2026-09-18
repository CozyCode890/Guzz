import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cau_hinh as chh  # noqa: E402
from duong_dan import CONFIG_MAU  # noqa: E402


class TestCauHinh(unittest.TestCase):
    def test_doc_duoc_config_mau(self):
        ch = chh.doc_cau_hinh(CONFIG_MAU)
        self.assertEqual(ch.thu_muc_ra, "")
        self.assertEqual(ch.nn_ten_nguoi_chinh, "Giảng viên")
        self.assertEqual(ch.nn_mau_doan, "[{moc}] {nguoi}: {noi_dung}")
        self.assertEqual(ch.che_do_am_thanh, "giang_vien_di_lai")
        self.assertEqual(ch.nn_timeout_giay, 3600)
        self.assertTrue(ch.tu_doi_model)
        self.assertEqual(ch.model, "gemini-3.5-flash-lite")
        self.assertEqual(ch.model_du_phong[0], "gemini-3.5-flash-lite")
        # Han muc that doc tu https://ai.dev/rate-limit ngay 2026-09-18.
        self.assertEqual(ch.han_muc_model, {
            "gemini-3.5-transcribe": (10000, 3, 25),
            "gemini-3.5-flash": (250000, 5, 20),
            "gemini-3.8-flash": (250000, 5, 20),
            "gemini-3.5-flash-lite": (250000, 15, 500),
        })
        self.assertIsNone(chh.loi_rang_buoc(ch))

    def test_rang_buoc_model_va_cach_nhan_dien(self):
        self.assertEqual(chh.cac_cach_hop_le("gemini-3.5-transcribe"), ("gemini", "ket_hop"))
        self.assertEqual(chh.cac_cach_hop_le("gemini-3.8-flash"), ("pyannote",))
        ch = chh.CauHinh(model="gemini-3.5-transcribe")
        self.assertIsNone(chh.loi_rang_buoc(ch))   # tat nhan dien: model nao cung duoc
        ch.nn_bat = True                            # cach mac dinh: pyannote + prompt
        self.assertIn("pyannote", chh.loi_rang_buoc(ch))
        ch.nn_cach = "ket_hop"
        self.assertIsNone(chh.loi_rang_buoc(ch))
        self.assertTrue(ch.can_pyannote())
        # Model khong phai *-transcribe thi khoa tach giong tren Google.
        ch.model = "gemini-3.8-flash"
        self.assertIn("*-transcribe", chh.loi_rang_buoc(ch))
        self.assertEqual(chh.cach_thay_the("gemini-3.8-flash", "ket_hop"), "pyannote")
        self.assertEqual(chh.cach_thay_the("gemini-3.8-flash", "gemini"), "pyannote")
        self.assertEqual(chh.cach_thay_the("gemini-3.5-transcribe", "pyannote"), "ket_hop")
        self.assertEqual(chh.cach_thay_the("gemini-3.5-transcribe", "gemini"), "gemini")
        ch.nn_cach = "gemini"
        self.assertFalse(ch.can_pyannote())

    def test_chuoi_model_chi_lay_model_hop_cach(self):
        ch = chh.CauHinh(model="gemini-3.8-flash",
                         model_du_phong=("gemini-3.5-transcribe", "gemini-3.8-flash", "gemini-3.5-flash"))
        self.assertEqual(ch.chuoi_model(), ["gemini-3.8-flash", "gemini-3.5-transcribe", "gemini-3.5-flash"])
        ch.nn_bat = True
        self.assertEqual(ch.chuoi_model(), ["gemini-3.8-flash", "gemini-3.5-flash"])
        ch.tu_doi_model = False
        self.assertEqual(ch.chuoi_model(), ["gemini-3.8-flash"])

    def test_doc_doi_model_va_han_muc(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "config.txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write("[DOI_MODEL]\nbat = false\nmodel_du_phong = a, b\nso_lan_thu_truoc_khi_doi = 0\n"
                        "[HAN_MUC]\ngemini-3.8-flash = 250000, 10\ngemini-x = 0, 0, 20\n")
            ch = chh.doc_cau_hinh(p)
            self.assertFalse(ch.tu_doi_model)
            self.assertEqual(ch.model_du_phong, ("a", "b"))
            self.assertEqual(ch.so_lan_thu_truoc_khi_doi, 1)
            self.assertEqual(ch.han_muc_model, {"gemini-3.8-flash": (250000, 10, 0), "gemini-x": (0, 0, 20)})
            self.assertEqual(ch.han_muc_cua("khac"), (10000, 0, 0))
            with open(p, "w", encoding="utf-8") as f:
                f.write("[HAN_MUC]\ngemini-x = nhieu\n")
            with self.assertRaises(ValueError):
                chh.doc_cau_hinh(p)

    def test_ten_file_va_thu_muc(self):
        ch = chh.CauHinh(mau_ten_file="{ngay_ghi}_{ten}")
        ten = ch.ten_file_ra(r"C:\a\Recording (3).m4a", luc_ghi=datetime(2026, 9, 10, 8, 11))
        self.assertEqual(ten, "2026-09-10_0811_Recording (3).txt")
        self.assertEqual(ch.thu_muc_ket_qua(r"C:\a\b.m4a"), r"C:\a")
        ch.thu_muc_ra = "Out"
        self.assertEqual(ch.thu_muc_ket_qua(r"C:\a\b.m4a"), r"C:\a\Out")
        ch.thu_muc_ra = r"D:\T"
        self.assertEqual(ch.thu_muc_ket_qua(r"C:\a\b.m4a"), r"D:\T")
        ch.mau_ten_file = "{ten}: {gio}?"
        self.assertTrue(ch.ten_file_ra(r"C:\a\b.m4a").startswith("b- "))

    def test_bao_loi_som(self):
        for them, chu in ((dict(mau_ten_file="{sai}"), "mau_ten_file"),
                          (dict(nn_mau_doan="{x}"), "mau_doan"),
                          (dict(nn_bat=True, nn_cach="gemini", phut_moi_doan=45), "30"),
                          (dict(nn_it_nhat=5, nn_nhieu_nhat=2), "so_nguoi"),
                          # Loi that 2026-09-17: nut SegmentedWidget phat True, GUI ghi "True" vao config.
                          (dict(nn_cach=True), "cach_nhan_dien")):
            with self.assertRaises(ValueError) as ctx:
                chh.kiem_tra(chh.CauHinh(**them))
            self.assertIn(chu, str(ctx.exception))

    def test_tuy_chon_giao_dien_sai_khong_lam_hong(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "config.txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write("[GIAO_DIEN]\nchu_de = tim\nco_chu_nhat_ky = 99\n[NGUOI_NOI]\nmau_doan = {nguoi}: {noi_dung}\n")
            ch = chh.doc_cau_hinh(p)
            self.assertEqual((ch.chu_de, ch.co_chu_nhat_ky), ("auto", 32))
            self.assertEqual(ch.nn_mau_doan, "{nguoi}: {noi_dung}")
            with open(p, "w", encoding="utf-8") as f:
                f.write("[KET_QUA]\nkhi_trung_ten = xoa\n")
            with self.assertRaises(ValueError):
                chh.doc_cau_hinh(p)


if __name__ == "__main__":
    unittest.main()
