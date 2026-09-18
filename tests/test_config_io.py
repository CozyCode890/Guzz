import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gui"))

import config_io as cio  # noqa: E402

MAU = """# dau file
[GOOGLE_AI]
# ghi chu
model = gemini-3.5-transcribe  # model mac dinh
ngon_ngu =
tu_vung = C#, F#

[KET_QUA]
danh_dau_doan = false
"""


class TestConfigIO(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = os.path.join(self.tmp.name, "config.txt")
        with open(self.p, "w", encoding="utf-8") as f:
            f.write(MAU)

    def tearDown(self):
        self.tmp.cleanup()

    def doc(self):
        with open(self.p, encoding="utf-8") as f:
            return f.read()

    def test_dau_thang_trong_gia_tri_khong_phai_ghi_chu(self):
        self.assertEqual(cio.lay_gia_tri("GOOGLE_AI", "tu_vung", self.p), "C#, F#")
        self.assertEqual(cio.lay_gia_tri("GOOGLE_AI", "model", self.p), "gemini-3.5-transcribe")

    def test_gia_tri_rong_ghi_lai_khong_vo_dong(self):
        cio.dat_gia_tri("GOOGLE_AI", "ngon_ngu", "vi-VN", self.p)
        self.assertIn("\nngon_ngu = vi-VN\ntu_vung = C#, F#\n", self.doc())

    def test_giu_ghi_chu_cuoi_dong_va_them_key_thieu(self):
        cio.dat_nhieu_gia_tri({
            ("GOOGLE_AI", "model"): "gemini-3.8-flash",
            ("KET_QUA", "danh_dau_doan"): "true",
            ("KET_QUA", "key_moi"): 5,
            ("MUC_MOI", "x"): "y",
        }, self.p)
        t = self.doc()
        self.assertIn("model = gemini-3.8-flash  # model mac dinh\n", t)
        self.assertIn("danh_dau_doan = true\nkey_moi = 5\n", t)
        self.assertTrue(t.endswith("\n[MUC_MOI]\nx = y\n"))
        self.assertIn("# ghi chu\n", t)

    def test_cung_ten_key_khac_section(self):
        with open(self.p, "a", encoding="utf-8") as f:
            f.write("\n[GUI]\nngon_ngu = vi\n")
        cio.dat_gia_tri("GUI", "ngon_ngu", "en", self.p)
        self.assertEqual(cio.lay_gia_tri("GOOGLE_AI", "ngon_ngu", self.p), "")
        self.assertEqual(cio.lay_gia_tri("GUI", "ngon_ngu", self.p), "en")


if __name__ == "__main__":
    unittest.main()
