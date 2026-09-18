"""
Chay ca luong chuyen doi tren audio tong hop (can ffmpeg), Google AI va pyannote gia lap.
"""

import json
import os
import re
import sys
import tempfile
import time
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import am_thanh_io  # noqa: E402
import cau_hinh  # noqa: E402
import chuyen_doi as cd  # noqa: E402
import google_ai as ga  # noqa: E402
import han_muc  # noqa: E402

SR = 16000
CO_TIENG = [(2, 20), (25, 40), (45, 58)]   # giay co "tieng noi" trong file 60 giay


def tao_audio(duong_dan):
    rng = np.random.default_rng(1)
    y = rng.normal(0, 0.0005, 60 * SR).astype(np.float32)
    for a, b in CO_TIENG:
        t = np.arange((b - a) * SR) / SR
        y[a * SR:b * SR] += (0.3 * np.sin(2 * np.pi * 220 * t) * (1 + np.sin(2 * np.pi * 3 * t))).astype(np.float32)
    am_thanh_io.ghi_audio(y, SR, duong_dan, "wav")


def tu(ds):
    """[(chu, spk, bat_dau, ket_thuc)] -> Interaction co word_info."""
    return {"status": "completed", "steps": [{"type": "model_output", "content": [{
        "type": "text", "text": " ".join(w for w, *_ in ds),
        "annotations": [{"type": "word_info", "text": w, "speaker": s,
                         "start_offset": f"{a}s", "end_offset": f"{b}s"} for w, s, a, b in ds]}]}]}


def van_ban(s):
    return {"status": "completed", "steps": [{"type": "model_output", "content": [{"type": "text", "text": s}]}]}


class MayKhachGia:
    def __init__(self, tra_loi):
        self.tra_loi = tra_loi     # ham (so_thu_tu_doan, kwargs) -> Interaction hoac Exception
        self.cac_lan = []
        self.so_token_lan_cuoi = 0

    def go_chu_tho(self, duong_dan, ch, prompt=None, nen_dung=None, so_giay_audio=None, **kw):
        ban_do = None
        if kw.get("file_kem"):
            with open(kw["file_kem"], encoding="utf-8") as f:
                ban_do = f.read()
        self.cac_lan.append({"file": os.path.basename(duong_dan), "prompt": prompt, **kw, "ban_do": ban_do})
        kq = self.tra_loi(len(self.cac_lan), kw)
        if isinstance(kq, Exception):
            raise kq
        return kq


class TestChuyenDoi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            am_thanh_io.tim_ffmpeg()
        except RuntimeError:
            raise unittest.SkipTest("khong co ffmpeg")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.audio = os.path.join(self.tmp.name, "bai giang.wav")
        tao_audio(self.audio)
        self.ch = cau_hinh.CauHinh(
            # Ghim model va thu tu du phong: cac test nay kiem tra hanh vi doi model,
            # khong phai gia tri mac dinh (mac dinh doi 2026-09-18 sang flash + flash-lite dau chuoi).
            model="gemini-3.5-transcribe",
            model_du_phong=("gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash",
                            "gemini-3.5-transcribe"),
            thu_muc_tam=os.path.join(self.tmp.name, "tmp"), khu_on=False, level_window_sec=0,
            min_silence_len=1000, silence_thresh_offset=20, keep_silence=400,
            phut_moi_doan=0.4, giay_tim_cho_cat=3, giay_doan_cuoi_toi_thieu=5, dinh_dang_doan="wav",
            gioi_han_token_moi_phut=0, xuong_dong="lf")

    def tearDown(self):
        self.tmp.cleanup()

    def doc(self, p):
        with open(p, "r", encoding="utf-8") as f:
            return f.read()

    def test_khong_nhan_dien_ghi_cung_thu_muc_crlf_bom(self):
        self.ch.xuong_dong, self.ch.ma_hoa, self.ch.danh_dau_doan = "crlf", "utf-8-sig", True
        kh = MayKhachGia(lambda i, kw: van_ban(f"Đoạn {i}."))
        kq = cd.chuyen_mot_file(self.ch, self.audio, kh)
        self.assertEqual(kq.file_ra, os.path.join(self.tmp.name, "bai giang.txt"))
        self.assertGreaterEqual(kq.so_doan, 2)
        with open(kq.file_ra, "rb") as f:
            tho = f.read()
        self.assertTrue(tho.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"\r\n\r\n", tho)
        self.assertIn("----- Đoạn 2/", tho.decode("utf-8-sig"))
        self.assertTrue(all(l["model"] == "gemini-3.5-transcribe" and l["prompt"] is None for l in kh.cac_lan))
        self.assertFalse(os.path.exists(cd.thu_muc_tam_cho(self.ch, self.audio)))

        # Lan hai: danh so; bo_qua thi khong goi Google.
        kq2 = cd.chuyen_mot_file(self.ch, self.audio, kh)
        self.assertTrue(kq2.file_ra.endswith("bai giang (2).txt"))
        self.ch.khi_trung_ten = "bo_qua"
        so_lan = len(kh.cac_lan)
        self.assertTrue(cd.chuyen_mot_file(self.ch, self.audio, kh).bo_qua)
        self.assertEqual(len(kh.cac_lan), so_lan)

    def test_thu_muc_ra_va_mau_ten(self):
        self.ch.thu_muc_ra, self.ch.mau_ten_file, self.ch.duoi_file_ra = "Transcripts", "{ten}_{model}", ".md"
        kq = cd.chuyen_mot_file(self.ch, self.audio, MayKhachGia(lambda i, kw: van_ban("x")))
        self.assertEqual(kq.file_ra, os.path.join(self.tmp.name, "Transcripts",
                                                  "bai giang_gemini-3.5-transcribe.md"))

    def test_loi_giua_chung_lam_lai_khong_gui_lai_doan_da_xong(self):
        loi = ga.LoiGoogleAI("qua tai", ga.LOI_TAM_THOI)
        kh = MayKhachGia(lambda i, kw: loi if i == 2 else van_ban(f"lan {i}"))
        with self.assertRaises(ga.LoiGoogleAI):
            cd.chuyen_mot_file(self.ch, self.audio, kh)
        kh2 = MayKhachGia(lambda i, kw: van_ban(f"lan sau {i}"))
        kq = cd.chuyen_mot_file(self.ch, self.audio, kh2)
        self.assertEqual(len(kh2.cac_lan), kq.so_doan - 1)
        self.assertTrue(self.doc(kq.file_ra).startswith("lan 1\n\nlan sau 1"))

    def _gia_pyannote(self, luot):
        def chay(ch, wav, json_ra, nen_dung=None, bao_tien_do=None):
            self.assertTrue(os.path.getsize(wav) > 0)
            if bao_tien_do:
                bao_tien_do(0.5, "embeddings")
            with open(json_ra, "w", encoding="utf-8") as f:
                json.dump({"doan": [{"bat_dau": a, "ket_thuc": b, "nguoi_noi": s} for a, b, s in luot]}, f)
        return mock.patch.object(cd.nhan_dien, "chay_nhan_dien", side_effect=chay)

    def test_pyannote_gui_ban_do_va_doi_moc_ve_file_goc(self):
        self.ch.nn_bat, self.ch.nn_cach, self.ch.xoa_thu_muc_tam_khi_xong = True, "pyannote", False
        self.ch.model = "gemini-3.8-flash"
        # Mac dinh lam muot gop moi nguoi hoi noi < 15 giay vao giang vien; ha nguong de giu cau hoi 10 giay.
        self.ch.them_phan_dau, self.ch.nn_mat_do_toi_thieu_giay = True, 5
        # Luot noi tren audio DA LAM SACH: giang vien ca buoi, nguoi hoi o giay 20-30.
        luot = [(0, 20, "SPEAKER_01"), (20, 30, "SPEAKER_00"), (30, 48, "SPEAKER_01")]
        kh = MayKhachGia(lambda i, kw: van_ban("[00:01] Giảng viên: Mở đầu.\n\n[00:03] Người hỏi 1: Câu hỏi?"))
        tien_do = []
        with self._gia_pyannote(luot):
            kq = cd.chuyen_mot_file(self.ch, self.audio, kh, bao=lambda g, r, ts: tien_do.append((g, r)))

        lan1 = kh.cac_lan[0]
        self.assertEqual(lan1["model"], "gemini-3.8-flash")
        self.assertIn("Speakers in this clip: Giảng viên", lan1["prompt"])
        self.assertIn('"[03:15] Giảng viên: ..."', lan1["prompt"])
        self.assertIn("00:00.0 - ", lan1["ban_do"])
        self.assertTrue(any("Người hỏi 1" in l["ban_do"] for l in kh.cac_lan))

        tam = cd.thu_muc_tam_cho(self.ch, self.audio)
        with open(os.path.join(tam, cd.FILE_DANH_SACH_DOAN), encoding="utf-8") as f:
            ds = json.load(f)
        bd = cd.BanDoThoiGian(ds["ban_do_thoi_gian"])
        noi_dung = self.doc(kq.file_ra)
        self.assertIn("Người nói: Giảng viên", noi_dung.splitlines()[2])
        moc_dau = cd.nn.hh_mm_ss(bd.sang_goc(ds["doan"][0]["bat_dau_giay"] + 1))
        self.assertIn(f"[{moc_dau}] Giảng viên: Mở đầu.", noi_dung)
        self.assertEqual(moc_dau, "00:00:02")  # khoang lang dau file bi cat, moc van theo file goc
        self.assertEqual([g for g, _ in tien_do][0], "lam_sach")
        self.assertIn("nguoi_noi", {g for g, _ in tien_do})
        self.assertEqual(tien_do[-1][1], 1.0)
        self.assertEqual(sorted(r for _, r in tien_do), [r for _, r in tien_do])

    def test_pyannote_chen_ban_do_vao_prompt_khi_chon_van_ban(self):
        self.ch.nn_bat, self.ch.nn_cach, self.ch.nn_cach_gui, self.ch.nn_moc_thoi_gian = True, "pyannote", "van_ban", False
        self.ch.model = "gemini-3.8-flash"
        kh = MayKhachGia(lambda i, kw: van_ban("Giảng viên: A"))
        with self._gia_pyannote([(0, 48, "S0")]):
            kq = cd.chuyen_mot_file(self.ch, self.audio, kh)
        self.assertIn("00:00.0", kh.cac_lan[0]["van_ban_kem"])
        self.assertNotIn("square brackets", kh.cac_lan[0]["prompt"])
        self.assertTrue(self.doc(kq.file_ra).startswith("Giảng viên: A\n\nGiảng viên: A"))

    def test_gemini_dat_ten_trong_tung_doan(self):
        self.ch.nn_bat, self.ch.nn_cach = True, "gemini"

        def tra_loi(i, kw):
            self.assertEqual(kw, {"model": "gemini-3.5-transcribe", "tach_nguoi_noi": True, "moc_tung_tu": True})
            # Doan nao cung: spk_2 noi lau (giang vien), spk_1 hoi mot cau ngan truoc.
            return tu([("Hỏi", "spk_1", 0.0, 0.5), ("gì?", "spk_1", 0.5, 1.0),
                       ("Trả", "spk_2", 1.5, 2.0), ("lời", "spk_2", 2.0, 6.0)])

        kq = cd.chuyen_mot_file(self.ch, self.audio, MayKhachGia(tra_loi))
        dong = self.doc(kq.file_ra).split("\n\n")
        self.assertRegex(dong[0], r"^\[00:00:0\d\] Người hỏi 1: Hỏi gì\?$")
        self.assertRegex(dong[1], r"^\[00:00:0\d\] Giảng viên: Trả lời$")
        self.assertEqual(list(kq.phut_theo_nguoi), ["Giảng viên", "Người hỏi 1"])

    def test_ket_hop_gan_ten_theo_pyannote(self):
        self.ch.nn_bat, self.ch.nn_cach, self.ch.nn_lam_muot = True, "ket_hop", False
        self.ch.nn_mau_doan = "{nguoi} ({moc}): {noi_dung}"
        kh = MayKhachGia(lambda i, kw: tu([("một", None, 0.0, 1.0), ("hai", None, 5.0, 6.0)]))
        with self._gia_pyannote([(0, 4, "A"), (4, 100, "B")]):
            kq = cd.chuyen_mot_file(self.ch, self.audio, kh)
        self.assertEqual(kh.cac_lan[0]["moc_tung_tu"], True)
        noi_dung = self.doc(kq.file_ra)
        # Doan 1: "một" (0-1) thuoc A, "hai" (5-6) thuoc B nguoi noi lau nhat -> Giang vien.
        self.assertRegex(noi_dung, r"^Người hỏi 1 \(00:00:0\d\): một\n\nGiảng viên \(00:00:\d\d\): hai")
        self.assertEqual(len(re.findall("Người hỏi 1", noi_dung)), 1)


class TestTuDoiModel(TestChuyenDoi):
    """Loi that ngay 2026-09-17: het han muc ngay, high demand, Input blocked."""

    # Khong chay lai cac test cua lop cha.
    test_khong_nhan_dien_ghi_cung_thu_muc_crlf_bom = test_thu_muc_ra_va_mau_ten = None
    test_loi_giua_chung_lam_lai_khong_gui_lai_doan_da_xong = None
    test_pyannote_gui_ban_do_va_doi_moc_ve_file_goc = test_pyannote_chen_ban_do_vao_prompt_khi_chon_van_ban = None
    test_gemini_dat_ten_trong_tung_doan = test_ket_hop_gan_ten_theo_pyannote = None

    def test_het_han_muc_ngay_khoa_model_va_doi_sang_du_phong(self):
        loi = ga.LoiGoogleAI("HTTP 429: Quota exceeded ... limit: 25", ga.LOI_HAN_MUC, 429)
        loi.theo_ngay = True
        kh = MayKhachGia(lambda i, kw: loi if kw["model"] == "gemini-3.5-transcribe" and i >= 2
                         else van_ban(f"{kw['model']} {i}"))
        kq = cd.chuyen_mot_file(self.ch, self.audio, kh)
        cac_model = [l["model"] for l in kh.cac_lan]
        self.assertEqual(cac_model[:3], ["gemini-3.5-transcribe", "gemini-3.5-transcribe", "gemini-3.5-flash"])
        self.assertTrue(all(m == "gemini-3.5-flash" for m in cac_model[3:]))   # da khoa: khong thu lai
        khoa, den, ly_do, _ = kh.so_theo_doi.trang_thai_khoa("gemini-3.5-transcribe")
        self.assertEqual((khoa, ly_do), (True, han_muc.KHOA_HAN_MUC_NGAY))
        self.assertEqual(den, han_muc.luc_dat_lai_ngay(time.time()))
        self.assertEqual(kq.cac_model["gemini-3.5-transcribe"], 1)
        # Model du phong da nang nhan prompt.txt, model *-transcribe thi khong.
        self.assertIsNone(kh.cac_lan[0]["prompt"])
        self.assertTrue(kh.cac_lan[2]["prompt"])
        self.assertEqual(kh.cac_lan[2]["so_lan_thu"], self.ch.so_lan_thu_truoc_khi_doi)

    def test_ban_go_chu_rong_thi_thu_lai_model_khac(self):
        """
        Loi that 2026-09-18: gemini-3.5-flash nhan 16k token audio roi tra ve ban go chu RONG.
        Truoc day app chi ghi WARNING va bo qua -> mat han 10 phut bai giang, lai con nho ket qua
        rong nen chay lai cung khong cuu duoc. Nay phai thu lai bang model khac.
        """
        kh = MayKhachGia(lambda i, kw: van_ban("") if kw["model"] == "gemini-3.5-transcribe"
                         else van_ban(f"Co chu {i}."))
        kq = cd.chuyen_mot_file(self.ch, self.audio, kh)
        cac_model = [l["model"] for l in kh.cac_lan]
        # Moi doan: goi model chinh (rong) roi goi lai model du phong.
        self.assertEqual(cac_model[0], "gemini-3.5-transcribe")
        self.assertEqual(cac_model[1], "gemini-3.5-flash")
        self.assertEqual(len(kh.cac_lan), 2 * kq.so_doan)
        # Ban go chu khong duoc mat doan nao.
        noi_dung = self.doc(kq.file_ra)
        self.assertIn("Co chu", noi_dung)
        self.assertEqual(kq.cac_model.get("gemini-3.5-transcribe"), None)

    def test_ket_qua_rong_khong_duoc_nho_lai(self):
        """Nho ket qua rong = chay lai van bo qua doan do vinh vien."""
        kh = MayKhachGia(lambda i, kw: van_ban(""))
        self.ch.tu_doi_model = False
        cd.chuyen_mot_file(self.ch, self.audio, kh)
        so_lan_dau = len(kh.cac_lan)
        self.assertGreater(so_lan_dau, 0)
        thu_muc = cd.thu_muc_tam_cho(self.ch, self.audio)
        if os.path.isdir(thu_muc):
            self.assertEqual([t for t in os.listdir(thu_muc) if t.endswith(".json")], [])
        # Chay lai: phai goi Google lai chu khong doc cache rong.
        self.ch.khi_trung_ten = "ghi_de"
        cd.chuyen_mot_file(self.ch, self.audio, kh)
        self.assertEqual(len(kh.cac_lan), 2 * so_lan_dau)

    def test_bo_loc_chan_mot_doan_chi_doi_model_cho_doan_do(self):
        self.ch.model = "gemini-3.8-flash"
        chan = ga.LoiGoogleAI("HTTP 400: Input blocked: This request was blocked by Gemini's filters.",
                              ga.LOI_BI_CHAN, 400)
        kh = MayKhachGia(lambda i, kw: chan if kw["model"] == "gemini-3.8-flash" and i == 1 else van_ban(kw["model"]))
        kq = cd.chuyen_mot_file(self.ch, self.audio, kh)
        self.assertEqual([l["model"] for l in kh.cac_lan][:3],
                         ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.8-flash"])
        self.assertFalse(kh.so_theo_doi.bi_khoa("gemini-3.8-flash"))
        self.assertTrue(self.doc(kq.file_ra).startswith("gemini-3.5-flash\n\ngemini-3.8-flash"))

    def test_qua_tai_khoa_tam_va_giu_model_du_phong(self):
        self.ch.model, self.ch.quay_lai_model_chinh = "gemini-3.8-flash", False
        qua_tai = ga.LoiGoogleAI("HTTP 500: gemini-3.8-flash is currently experiencing high demand",
                                 ga.LOI_QUA_TAI, 500)
        kh = MayKhachGia(lambda i, kw: qua_tai if kw["model"] == "gemini-3.8-flash" else van_ban("ok"))
        cd.chuyen_mot_file(self.ch, self.audio, kh)
        self.assertEqual([l["model"] for l in kh.cac_lan][:2], ["gemini-3.8-flash", "gemini-3.5-flash"])
        self.assertTrue(all(l["model"] == "gemini-3.5-flash" for l in kh.cac_lan[1:]))
        self.assertEqual(kh.so_theo_doi.trang_thai_khoa("gemini-3.8-flash")[2], han_muc.KHOA_QUA_TAI)

    def test_tat_khoa_qua_tai_van_doi_model_cho_doan_dang_gui(self):
        self.ch.model, self.ch.phut_khoa_khi_qua_tai = "gemini-3.8-flash", 0
        qua_tai = ga.LoiGoogleAI("HTTP 500: high demand", ga.LOI_QUA_TAI, 500)
        kh = MayKhachGia(lambda i, kw: qua_tai if kw["model"] == "gemini-3.8-flash" and i == 1 else van_ban("ok"))
        cd.chuyen_mot_file(self.ch, self.audio, kh)
        self.assertEqual([l["model"] for l in kh.cac_lan][:3], ["gemini-3.8-flash", "gemini-3.5-flash",
                                                                "gemini-3.8-flash"])
        self.assertFalse(kh.so_theo_doi.bi_khoa("gemini-3.8-flash"))

    def test_bo_loc_chan_o_moi_model_thi_file_loi_nhung_khong_dung_hang_doi(self):
        self.ch.model, self.ch.model_du_phong = "gemini-3.8-flash", ("gemini-3.5-flash",)
        chan = ga.LoiGoogleAI("HTTP 400: Input blocked", ga.LOI_BI_CHAN, 400)
        kh = MayKhachGia(lambda i, kw: chan)
        with self.assertRaises(ga.LoiGoogleAI) as ctx:
            cd.chuyen_mot_file(self.ch, self.audio, kh)
        self.assertEqual(ctx.exception.loai, ga.LOI_BI_CHAN)
        self.assertFalse(ctx.exception.dung_hang_doi)
        self.assertEqual(len(kh.cac_lan), 2)

    def test_moi_model_deu_khoa_lau_thi_dung_hang_doi(self):
        self.ch.nn_bat, self.ch.nn_cach = True, "gemini"     # chi co mot model *-transcribe
        kh = MayKhachGia(lambda i, kw: van_ban("x"))
        kh.so_theo_doi = han_muc.SoTheoDoi(None)
        kh.so_theo_doi.khoa("gemini-3.5-transcribe", time.time() + 5 * 3600, han_muc.KHOA_HAN_MUC_NGAY, "429")
        with self.assertRaises(ga.LoiGoogleAI) as ctx:
            cd.chuyen_mot_file(self.ch, self.audio, kh)
        self.assertTrue(ctx.exception.dung_hang_doi)
        self.assertIn("gemini-3.5-transcribe", str(ctx.exception))
        self.assertEqual(kh.cac_lan, [])

    def test_khoa_ngan_thi_cho_roi_gui_tiep(self):
        self.ch.nn_bat, self.ch.nn_cach = True, "gemini"
        kh = MayKhachGia(lambda i, kw: van_ban("x"))
        kh.so_theo_doi = han_muc.SoTheoDoi(None)
        kh.so_theo_doi.khoa("gemini-3.5-transcribe", time.time() + 90, han_muc.KHOA_QUA_TAI, "500")
        with mock.patch.object(ga, "ngu", side_effect=lambda giay, nen_dung=None:
                               kh.so_theo_doi.mo_khoa("gemini-3.5-transcribe")) as ngu:
            cd.chuyen_mot_file(self.ch, self.audio, kh)
        self.assertGreaterEqual(ngu.call_args[0][0], 90)
        self.assertTrue(kh.cac_lan)

    def test_cham_han_muc_ngay_thi_khoa_truoc_khi_gui(self):
        self.ch.han_muc_model = {"gemini-3.5-transcribe": (0, 0, 1)}
        kh = MayKhachGia(lambda i, kw: van_ban(kw["model"]))
        kh.so_theo_doi = han_muc.SoTheoDoi(None)
        kh.so_theo_doi.ghi_yeu_cau("gemini-3.5-transcribe")   # MayKhach that tu ghi; may gia thi ghi tay
        cd.chuyen_mot_file(self.ch, self.audio, kh)
        self.assertTrue(all(l["model"] == "gemini-3.5-flash" for l in kh.cac_lan))
        self.assertEqual(kh.so_theo_doi.trang_thai_khoa("gemini-3.5-transcribe")[2], han_muc.KHOA_CHAM_HAN_MUC)

    def test_model_khong_hop_cach_nhan_dien_bao_loi_ngay(self):
        self.ch.nn_bat, self.ch.nn_cach = True, "pyannote"    # model mac dinh la *-transcribe
        with mock.patch.object(cd, "chuan_bi_doan") as chuan_bi:
            with self.assertRaises(cau_hinh.LoiRangBuoc):
                cd.chuyen_mot_file(self.ch, self.audio, MayKhachGia(lambda i, kw: van_ban("x")))
        chuan_bi.assert_not_called()


class MayChuTheoModel:
    """Gia lap Gemini API cho MayKhach THAT: moi model tra loi theo kich ban rieng (danh sach, lay lan luot)."""

    def __init__(self, kich_ban: dict):
        self.kich_ban = {m: list(ds) for m, ds in kich_ban.items()}
        self.cac_model = []

    def __call__(self, req, timeout=None):
        import io
        import urllib.error
        from test_google_ai import PhanHoi, headers
        url = req.full_url
        if url.endswith("/upload/v1beta/files"):
            return PhanHoi({}, hdr=headers(X_Goog_Upload_URL="https://upload.example/abc"))
        if url == "https://upload.example/abc":
            return PhanHoi({"file": {"name": "files/f1", "uri": "https://g/files/f1", "mimeType": "audio/flac",
                                     "state": "ACTIVE"}})
        if url.endswith("/interactions"):
            model = json.loads(req.data)["model"]
            self.cac_model.append(model)
            ds = self.kich_ban[model]
            kq = ds.pop(0) if len(ds) > 1 else ds[0]
            if isinstance(kq, tuple):
                ma, thong_bao = kq
                raise urllib.error.HTTPError(url, ma, "loi", headers(), io.BytesIO(json.dumps(
                    {"error": {"code": ma, "message": thong_bao}}).encode()))
            return PhanHoi(van_ban(f"{model}: {kq}"))
        return PhanHoi({})


class TestTaiHienNhatKy(TestChuyenDoi):
    """Chuoi loi that trong data\\logs\\guzz.log ngay 2026-09-17, chay qua MayKhach that (chi gia HTTP)."""

    test_khong_nhan_dien_ghi_cung_thu_muc_crlf_bom = test_thu_muc_ra_va_mau_ten = None
    test_loi_giua_chung_lam_lai_khong_gui_lai_doan_da_xong = None
    test_pyannote_gui_ban_do_va_doi_moc_ve_file_goc = test_pyannote_chen_ban_do_vao_prompt_khi_chon_van_ban = None
    test_gemini_dat_ten_trong_tung_doan = test_ket_hop_gan_ten_theo_pyannote = None

    HET_25_YEU_CAU = (429, "You exceeded your current quota, please check your plan and billing details.\n"
                           "* Quota exceeded for metric: generativelanguage.googleapis.com/"
                           "generate_content_free_tier_requests, limit: 25, model: gemini-3.5-transcribe\n"
                           "Please retry in 27.888016836s.")
    HIGH_DEMAND = (500, "gemini-3.8-flash is currently experiencing high demand, spikes in demand are usually "
                        "temporary. Please try again later.")
    INPUT_BLOCKED = (400, "Input blocked: This request was blocked by Gemini's filters. They can occasionally "
                          "trigger by mistake on safe coding, security, or biology-related queries.")

    def setUp(self):
        super().setUp()
        ga._DIEU_TIET_THEO_MODEL.clear()
        self.ch.phut_moi_doan = 0.25          # du doan de thay ca luc doi model lan luc giu model
        self.so = han_muc.SoTheoDoi(None)

    def chay(self, kich_ban):
        may_chu = MayChuTheoModel(kich_ban)
        kh = ga.MayKhach("K", mo_url=may_chu, so_theo_doi=self.so)
        with mock.patch.object(ga, "ngu"):
            kq = cd.chuyen_mot_file(self.ch, self.audio, kh)
        return kq, may_chu.cac_model

    def test_het_han_muc_ngay_roi_high_demand_thi_sang_flash_lite(self):
        self.ch.model_du_phong = ("gemini-3.8-flash", "gemini-3.5-flash-lite")
        kq, cac_model = self.chay({
            "gemini-3.5-transcribe": ["ok", self.HET_25_YEU_CAU],
            "gemini-3.8-flash": [self.HIGH_DEMAND],
            "gemini-3.5-flash-lite": ["ok"],
        })
        self.assertGreaterEqual(kq.so_doan, 3)
        # Doan 1 transcribe; doan 2: 429 han muc NGAY -> khong thu lai; 3.8-flash qua tai thu 2 lan -> flash-lite.
        self.assertEqual(cac_model[:5], ["gemini-3.5-transcribe", "gemini-3.5-transcribe", "gemini-3.8-flash",
                                         "gemini-3.8-flash", "gemini-3.5-flash-lite"])
        # Cac doan sau khong goi lai model da khoa.
        self.assertEqual(set(cac_model[5:]), {"gemini-3.5-flash-lite"})
        self.assertEqual(self.so.trang_thai_khoa("gemini-3.5-transcribe")[2], han_muc.KHOA_HAN_MUC_NGAY)
        self.assertEqual(self.so.trang_thai_khoa("gemini-3.8-flash")[2], han_muc.KHOA_QUA_TAI)
        self.assertEqual(self.so.hoc_duoc("gemini-3.5-transcribe"), {"rpd": 25})
        self.assertEqual(kq.cac_model, {"gemini-3.5-transcribe": 1, "gemini-3.5-flash-lite": kq.so_doan - 1})
        loai_su_kien = [s["loai"] for s in self.so.anh_chup()["su_kien"]]
        self.assertIn(han_muc.SK_DOI_MODEL, loai_su_kien)

    def test_input_blocked_khong_dung_file(self):
        self.ch.model, self.ch.model_du_phong = "gemini-3.8-flash", ("gemini-3.5-flash-lite",)
        self.ch.nn_bat, self.ch.nn_cach = False, "pyannote"
        kq, cac_model = self.chay({
            "gemini-3.8-flash": ["ok", self.INPUT_BLOCKED, "ok"],
            "gemini-3.5-flash-lite": ["ok"],
        })
        self.assertEqual(cac_model[:4], ["gemini-3.8-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite",
                                         "gemini-3.8-flash"])
        self.assertFalse(self.so.bi_khoa("gemini-3.8-flash"))
        self.assertIn("gemini-3.5-flash-lite: ok", self.doc(kq.file_ra))
        self.assertEqual(self.so.anh_chup()["model"]["gemini-3.8-flash"]["dem_loi"], {"bi_chan": 1})


if __name__ == "__main__":
    unittest.main()
