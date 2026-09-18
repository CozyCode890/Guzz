import email.message
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cau_hinh  # noqa: E402
import google_ai as ga  # noqa: E402


def tao_cau_hinh(**them):
    # Tat dieu tiet o cac test khong noi ve no, khoi phai cho that.
    ch = cau_hinh.CauHinh(model="gemini-3.5-transcribe", gioi_han_token_moi_phut=0,
                          han_muc_model={})
    for k, v in them.items():
        setattr(ch, k, v)
    return ch


def headers(**kv):
    h = email.message.Message()
    for k, v in kv.items():
        h[k.replace("_", "-")] = v
    return h


class PhanHoi:
    def __init__(self, than=b"{}", status=200, hdr=None):
        self.status = status
        self.headers = hdr or headers()
        self._than = than if isinstance(than, bytes) else json.dumps(than).encode()

    def read(self):
        return self._than

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def loi_http(ma, than, hdr=None):
    b = json.dumps(than).encode() if not isinstance(than, bytes) else than
    return urllib.error.HTTPError("https://x", ma, "loi", hdr or headers(), io.BytesIO(b))


class MayChuGia:
    """Gia lap Gemini API: ghi lai moi yeu cau, tra loi theo kich ban."""

    def __init__(self, ket_qua_interaction):
        self.yeu_cau = []
        self.ket_qua_interaction = list(ket_qua_interaction)

    def __call__(self, req, timeout=None):
        self.yeu_cau.append(req)
        url, method = req.full_url, req.get_method()
        if url.endswith("/upload/v1beta/files"):
            return PhanHoi({}, hdr=headers(X_Goog_Upload_URL="https://upload.example/abc"))
        if url == "https://upload.example/abc":
            return PhanHoi({"file": {"name": "files/f1", "uri": "https://g/files/f1",
                                     "mimeType": "audio/flac", "state": "ACTIVE"}})
        if url.endswith("/interactions"):
            kq = self.ket_qua_interaction.pop(0)
            if isinstance(kq, Exception):
                raise kq
            return PhanHoi(kq)
        if method == "DELETE":
            return PhanHoi({})
        raise AssertionError(f"Yeu cau khong mong doi: {method} {url}")

    def cac_url(self):
        return [(r.get_method(), r.full_url) for r in self.yeu_cau]


KQ_XONG = {"id": "int_1", "status": "completed", "steps": [
    {"type": "user_input", "content": [{"type": "text", "text": "KHONG LAY"}]},
    {"type": "model_output", "content": [{"type": "text", "text": "Xin chào "},
                                         {"type": "text", "text": "các bạn."}]},
]}


class TestYeuCau(unittest.TestCase):
    def test_model_transcribe_gui_transcription_config_khong_prompt(self):
        ch = tao_cau_hinh(model="gemini-3.5-transcribe", che_do_go_chu="verbatim",
                          ngon_ngu=("vi-VN",), tu_vung=("Data Mining",))
        yc = ga.tao_yeu_cau(ch, "uri://a", "audio/flac", prompt="bi bo qua")
        self.assertEqual(yc["input"], [{"type": "audio", "uri": "uri://a", "mime_type": "audio/flac"}])
        self.assertEqual(yc["generation_config"]["transcription_config"], {
            "mode": {"type": "verbatim"}, "language_codes": ["vi-VN"],
            "custom_vocabulary": ["Data Mining"]})
        self.assertIs(yc["store"], False)

    def test_model_da_nang_gui_prompt_truoc_audio(self):
        ch = tao_cau_hinh(model="gemini-3.8-flash", luu_tren_server=True)
        yc = ga.tao_yeu_cau(ch, "uri://a", "audio/flac", prompt="Go chu giup.")
        self.assertEqual(yc["input"][0], {"type": "text", "text": "Go chu giup."})
        self.assertEqual(yc["input"][1]["type"], "audio")
        self.assertNotIn("generation_config", yc)
        self.assertNotIn("store", yc)

    def test_trich_van_ban_chi_lay_model_output(self):
        self.assertEqual(ga.doc_ket_qua(KQ_XONG), "Xin chào các bạn.")

    def test_status_failed_la_loi_khac(self):
        with self.assertRaises(ga.LoiGoogleAI) as ctx:
            ga.doc_ket_qua({"status": "failed", "errors": [{"message": "hong"}]})
        self.assertEqual(ctx.exception.loai, ga.LOI_KHAC)
        self.assertIn("hong", str(ctx.exception))


class TestPhanLoaiLoi(unittest.TestCase):
    def setUp(self):
        # Moi model mot DieuTiet dung chung ca tien trinh: moi test bat dau sach.
        ga._DIEU_TIET_THEO_MODEL.clear()

    def test_429_la_het_han_muc_kem_retry_delay(self):
        e = ga.loi_tu_http(429, json.dumps({"error": {
            "code": 429, "status": "RESOURCE_EXHAUSTED", "message": "quota",
            "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "37s"}],
        }}).encode())
        self.assertEqual(e.loai, ga.LOI_HAN_MUC)
        self.assertTrue(e.thu_lai_duoc)
        self.assertEqual(e.cho_giay, 37)
        self.assertIn("RESOURCE_EXHAUSTED", str(e))

    def test_429_thoi_gian_cho_nam_trong_message(self):
        # Dung nguyen van loi that lay tu nhat ky ngay 2026-09-17.
        e = ga.loi_tu_http(429, json.dumps({"error": {
            "code": 429, "status": "RESOURCE_EXHAUSTED",
            "message": "You exceeded your current quota, please check your plan and billing details.\n"
                       "* Quota exceeded for metric: generativelanguage.googleapis.com/"
                       "generate_content_free_tier_input_token_count, limit: 10000, "
                       "model: gemini-3.5-transcribe\nPlease retry in 55.981490556s."}}).encode())
        self.assertEqual(e.loai, ga.LOI_HAN_MUC)
        self.assertAlmostEqual(e.cho_giay, 55.981490556)
        self.assertEqual(e.vi_pham, [ga.ViPhamHanMuc(
            "generativelanguage.googleapis.com/generate_content_free_tier_input_token_count", 10000,
            "gemini-3.5-transcribe")])
        self.assertTrue(e.vi_pham[0].la_token)

    def test_thu_lai_cho_dung_thoi_gian_google_yeu_cau(self):
        audio = os.path.join(tempfile.mkdtemp(), "a.flac")
        with open(audio, "wb") as f:
            f.write(b"x")
        may_chu = MayChuGia([loi_http(429, {"error": {"message": "Please retry in 55.9s."}}), KQ_XONG])
        with mock.patch.object(ga, "ngu") as ngu:
            ga.MayKhach("K", mo_url=may_chu).go_chu(audio, tao_cau_hinh())
        self.assertAlmostEqual(ngu.call_args[0][0], 57.9)

    def test_429_han_muc_ngay_khong_thu_lai_va_ghi_nho(self):
        """Loi that 2026-09-17: limit 25 yeu cau, app gui moi phut mot doan -> han muc NGAY."""
        import han_muc
        audio = os.path.join(tempfile.mkdtemp(), "a.flac")
        with open(audio, "wb") as f:
            f.write(b"x")
        thong_bao = ("You exceeded your current quota, please check your plan and billing details.\n"
                     "* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, "
                     "limit: 25, model: gemini-3.5-transcribe\nPlease retry in 27.888016836s.")
        may_chu = MayChuGia([loi_http(429, {"error": {"code": 429, "message": thong_bao}})])
        so = han_muc.SoTheoDoi(None)
        kh = ga.MayKhach("K", mo_url=may_chu, so_theo_doi=so)
        with mock.patch.object(ga, "ngu") as ngu:
            with self.assertRaises(ga.LoiGoogleAI) as ctx:
                kh.go_chu(audio, tao_cau_hinh(so_lan_thu_moi_doan=4), model="gemini-3.5-transcribe")
        self.assertEqual(ctx.exception.loai, ga.LOI_HAN_MUC)
        self.assertTrue(ctx.exception.theo_ngay)
        self.assertFalse(ctx.exception.thu_lai_duoc)
        ngu.assert_not_called()
        self.assertEqual(so.hoc_duoc("gemini-3.5-transcribe"), {"rpd": 25})
        self.assertEqual(so.anh_chup()["model"]["gemini-3.5-transcribe"]["dem_loi"], {"han_muc_ngay": 1})

    def test_con_model_du_phong_thi_thu_it_lan_hon(self):
        audio = os.path.join(tempfile.mkdtemp(), "a.flac")
        with open(audio, "wb") as f:
            f.write(b"x")
        may_chu = MayChuGia([loi_http(500, {"error": {"message": "high demand"}})] * 2 + [KQ_XONG])
        with mock.patch.object(ga, "ngu"):
            with self.assertRaises(ga.LoiGoogleAI) as ctx:
                ga.MayKhach("K", mo_url=may_chu).go_chu(audio, tao_cau_hinh(so_lan_thu_moi_doan=4), so_lan_thu=2)
        self.assertEqual(ctx.exception.loai, ga.LOI_QUA_TAI)
        self.assertEqual(len(may_chu.ket_qua_interaction), 1)

    def test_key_sai_la_loi_cau_hinh(self):
        e = ga.loi_tu_http(400, json.dumps({"error": {
            "status": "INVALID_ARGUMENT", "message": "API key not valid.",
            "details": [{"reason": "API_KEY_INVALID"}]}}).encode())
        self.assertEqual(e.loai, ga.LOI_CAU_HINH)
        self.assertIn("API_KEY_INVALID", str(e))

    def test_503_than_khong_phai_json(self):
        e = ga.loi_tu_http(503, b"<html>Service Unavailable</html>")
        self.assertEqual(e.loai, ga.LOI_QUA_TAI)

    def test_500_high_demand_la_qua_tai(self):
        # Nguyen van loi that cua gemini-3.8-flash ngay 2026-09-17.
        e = ga.loi_tu_http(500, json.dumps({"error": {"code": 500, "message": (
            "gemini-3.8-flash is currently experiencing high demand, spikes in demand are usually temporary. "
            "Please try again later.")}}).encode())
        self.assertEqual(e.loai, ga.LOI_QUA_TAI)
        self.assertTrue(e.thu_lai_duoc)
        self.assertIn(e.loai, ga.CAC_LOI_DOI_MODEL)
        self.assertFalse(e.dung_hang_doi)

    def test_input_blocked_khong_dung_hang_doi(self):
        # Loi that ngay 2026-09-17: truoc day bi coi la loi cau hinh va dung ca hang doi.
        e = ga.loi_tu_http(400, json.dumps({"error": {"code": 400, "message": (
            "Input blocked: This request was blocked by Gemini's filters. They can occasionally trigger by "
            "mistake on safe coding, security, or biology-related queries. Please try rephrasing your prompt.")}})
            .encode())
        self.assertEqual(e.loai, ga.LOI_BI_CHAN)
        self.assertFalse(e.thu_lai_duoc)
        self.assertFalse(e.dung_hang_doi)

    def test_quota_failure_trong_details(self):
        e = ga.loi_tu_http(429, json.dumps({"error": {"status": "RESOURCE_EXHAUSTED", "message": "quota", "details": [
            {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{
                "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
                "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
                "quotaDimensions": {"model": "gemini-3.8-flash", "location": "global"}, "quotaValue": "20"}]}]}})
            .encode())
        self.assertEqual(e.vi_pham[0].theo, "ngay")
        self.assertEqual((e.vi_pham[0].gioi_han, e.vi_pham[0].model), (20, "gemini-3.8-flash"))
        self.assertFalse(e.vi_pham[0].la_token)

    def test_model_khong_ton_tai(self):
        e = ga.loi_tu_http(404, json.dumps({"error": {"message": "models/gemini-9 is not found for API version v1beta"}})
                           .encode())
        self.assertEqual(e.loai, ga.LOI_MODEL)


class TestGoChu(unittest.TestCase):
    def setUp(self):
        ga._DIEU_TIET_THEO_MODEL.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.audio = os.path.join(self.tmp.name, "doan_001.flac")
        with open(self.audio, "wb") as f:
            f.write(b"fLaC" + b"\0" * 100)

    def tearDown(self):
        self.tmp.cleanup()

    def test_tai_len_go_chu_roi_xoa(self):
        may_chu = MayChuGia([KQ_XONG])
        kh = ga.MayKhach("KEY123", mo_url=may_chu)
        van_ban = kh.go_chu(self.audio, tao_cau_hinh())
        self.assertEqual(van_ban, "Xin chào các bạn.")
        self.assertEqual([m for m, _ in may_chu.cac_url()], ["POST", "POST", "POST", "DELETE"])
        bat_dau = may_chu.yeu_cau[0]
        self.assertEqual(bat_dau.get_header("X-goog-upload-command"), "start")
        self.assertEqual(bat_dau.get_header("X-goog-upload-header-content-length"), "104")
        self.assertEqual(bat_dau.get_header("X-goog-api-key"), "KEY123")
        tai = may_chu.yeu_cau[1]
        self.assertEqual(tai.get_header("X-goog-upload-command"), "upload, finalize")
        self.assertEqual(len(tai.data), 104)
        body = json.loads(may_chu.yeu_cau[2].data)
        self.assertEqual(body["input"][0]["uri"], "https://g/files/f1")
        self.assertTrue(may_chu.cac_url()[3][1].endswith("/v1beta/files/f1"))

    def test_loi_tam_thoi_thu_lai_roi_thanh_cong(self):
        may_chu = MayChuGia([loi_http(503, {"error": {"message": "overloaded"}}), KQ_XONG])
        kh = ga.MayKhach("K", mo_url=may_chu)
        with mock.patch.object(ga, "ngu") as ngu:
            van_ban = kh.go_chu(self.audio, tao_cau_hinh(so_lan_thu_moi_doan=3))
        self.assertEqual(van_ban, "Xin chào các bạn.")
        ngu.assert_called_once()
        # Moi lan thu deu xoa file da tai len.
        self.assertEqual(sum(1 for m, _ in may_chu.cac_url() if m == "DELETE"), 2)

    def test_het_so_lan_thu_thi_nem_loi_han_muc(self):
        may_chu = MayChuGia([loi_http(429, {"error": {"message": "q"}})] * 2)
        kh = ga.MayKhach("K", mo_url=may_chu)
        with mock.patch.object(ga, "ngu"):
            with self.assertRaises(ga.LoiGoogleAI) as ctx:
                kh.go_chu(self.audio, tao_cau_hinh(so_lan_thu_moi_doan=2))
        self.assertEqual(ctx.exception.loai, ga.LOI_HAN_MUC)
        self.assertFalse(ctx.exception.theo_ngay)

    def test_model_khong_ton_tai_khong_thu_lai(self):
        may_chu = MayChuGia([loi_http(404, {"error": {"message": "model not found"}})])
        kh = ga.MayKhach("K", mo_url=may_chu)
        with mock.patch.object(ga, "ngu") as ngu:
            with self.assertRaises(ga.LoiGoogleAI) as ctx:
                kh.go_chu(self.audio, tao_cau_hinh(so_lan_thu_moi_doan=4))
        self.assertEqual(ctx.exception.loai, ga.LOI_MODEL)
        ngu.assert_not_called()

    def test_key_sai_dung_hang_doi(self):
        e = ga.loi_tu_http(403, json.dumps({"error": {"message": "Permission denied"}}).encode())
        self.assertEqual(e.loai, ga.LOI_CAU_HINH)
        self.assertTrue(e.dung_hang_doi)

    def test_mat_mang_la_tam_thoi(self):
        def mat_mang(req, timeout=None):
            raise urllib.error.URLError("getaddrinfo failed")
        with self.assertRaises(ga.LoiGoogleAI) as ctx:
            ga.MayKhach("K", mo_url=mat_mang).liet_ke_model()
        self.assertEqual(ctx.exception.loai, ga.LOI_TAM_THOI)

    def test_nut_dung_cat_ngang_luc_cho(self):
        with self.assertRaises(ga.DaDung):
            ga.ngu(30, nen_dung=lambda: True)


class DongHoGia:
    def __init__(self):
        self.bay_gio = 1000.0

    def __call__(self):
        return self.bay_gio


def kq_co_token(so):
    return dict(KQ_XONG, usage={"total_input_tokens": so, "total_tokens": so + 900})


class TestDieuTiet(unittest.TestCase):
    def test_uoc_luong_theo_doan_truoc_va_cho_du_han_muc(self):
        dh = DongHoGia()
        dt = ga.DieuTiet(dong_ho=dh)
        self.assertEqual(dt.thoi_gian_can_cho(10000, dt.uoc_luong(600, 10000)), 0)
        dt.ghi(dh(), 4000, so_giay_audio=600)
        dh.bay_gio += 20
        du_kien = dt.uoc_luong(600, 10000)
        self.assertEqual(du_kien, 4400)
        self.assertEqual(dt.thoi_gian_can_cho(10000, du_kien), 0)  # 4000 + 4400 <= 10000
        dt.ghi(dh(), 4000, so_giay_audio=600)
        dh.bay_gio += 20
        # 8000 + 4400 > 10000: cho lan gui dau tien ra khoi cua so 60 giay.
        self.assertAlmostEqual(dt.thoi_gian_can_cho(10000, 4400), 21.0)
        dh.bay_gio += 21
        self.assertEqual(dt.thoi_gian_can_cho(10000, 4400), 0)

    def test_khong_biet_so_token_thi_cach_nhau_mot_phut(self):
        dh = DongHoGia()
        dt = ga.DieuTiet(dong_ho=dh)
        dt.ghi(dh(), 10000, thuc_te=False)
        self.assertIsNone(dt.token_moi_giay_audio)
        dh.bay_gio += 15
        self.assertAlmostEqual(dt.thoi_gian_can_cho(10000, dt.uoc_luong(600, 10000)), 46.0)

    def test_doan_lon_hon_han_muc_chi_can_cua_so_trong(self):
        dh = DongHoGia()
        dt = ga.DieuTiet(dong_ho=dh)
        self.assertEqual(dt.thoi_gian_can_cho(10000, 25000), 0)
        dt.ghi(dh(), 2000, so_giay_audio=60)
        dh.bay_gio += 30
        self.assertAlmostEqual(dt.thoi_gian_can_cho(10000, 25000), 31.0)

    def test_gioi_han_0_la_khong_cho(self):
        dt = ga.DieuTiet(dong_ho=DongHoGia())
        dt.ghi(0, 10 ** 9)
        self.assertEqual(dt.thoi_gian_can_cho(0, 10 ** 9), 0)

    def test_ba_doan_lien_tiep_khong_dinh_429(self):
        """Tai hien lan chay that 2026-09-17: doan 3 phai tu cho, khong duoc gui ngay."""
        dh = DongHoGia()
        dt = ga.DieuTiet(dong_ho=dh)
        audio = os.path.join(tempfile.mkdtemp(), "a.flac")
        with open(audio, "wb") as f:
            f.write(b"x")
        may_chu = MayChuGia([kq_co_token(4000), kq_co_token(4000), kq_co_token(4000)])
        kh = ga.MayKhach("K", mo_url=may_chu, dieu_tiet=dt)
        ch = tao_cau_hinh(gioi_han_token_moi_phut=10000)
        cac_lan_cho = []

        def ngu_gia(giay, nen_dung=None):
            cac_lan_cho.append(round(giay))
            dh.bay_gio += giay

        with mock.patch.object(ga, "ngu", side_effect=ngu_gia):
            for _ in range(3):
                kh.go_chu(audio, ch, so_giay_audio=600)
                self.assertEqual(kh.so_token_lan_cuoi, 4000)
                dh.bay_gio += 15  # moi doan Google xu ly mat ~15 giay
        # Doan 1, 2 gui ngay (tong 8000); doan 3 (uoc 4400) cho doan 1 ra khoi cua so.
        self.assertEqual(cac_lan_cho, [31])

    def test_han_muc_yeu_cau_moi_phut(self):
        dh = DongHoGia()
        dt = ga.DieuTiet(dong_ho=dh)
        self.assertEqual(dt.thoi_gian_can_cho_yeu_cau(2), 0)
        dt.ghi(dh(), 0)
        dh.bay_gio += 10
        dt.ghi(dh(), 0)
        dh.bay_gio += 10
        self.assertAlmostEqual(dt.thoi_gian_can_cho_yeu_cau(2), 41.0)   # lan dau (t=0) ra khoi cua so luc 61
        self.assertEqual(dt.thoi_gian_can_cho_yeu_cau(3), 0)
        self.assertEqual(dt.so_yeu_cau(), 2)

    def test_bi_429_thi_coi_ca_phut_da_day(self):
        dh = DongHoGia()
        dt = ga.DieuTiet(dong_ho=dh)
        audio = os.path.join(tempfile.mkdtemp(), "a.flac")
        with open(audio, "wb") as f:
            f.write(b"x")
        may_chu = MayChuGia([loi_http(429, {"error": {"message": "quota"}})])
        kh = ga.MayKhach("K", mo_url=may_chu, dieu_tiet=dt)
        with self.assertRaises(ga.LoiGoogleAI):
            kh.go_chu(audio, tao_cau_hinh(gioi_han_token_moi_phut=10000, so_lan_thu_moi_doan=1))
        self.assertEqual(dt.da_dung(), 10000)


KQ_CO_TU = {"id": "int_2", "status": "completed", "steps": [
    {"type": "model_output", "content": [{
        "type": "text", "text": "Hello world",
        "annotations": [
            {"type": "word_info", "text": "Hello", "speaker": "spk_1",
             "start_offset": "0.100s", "end_offset": "0.450s"},
            {"type": "word_info", "text": "world", "speaker": "spk_2",
             "start_offset": "0.500s", "end_offset": "0.850s"},
            {"type": "other", "text": "bo qua"},
        ]}]},
]}


class TestNguoiNoiVaFileKem(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.audio = os.path.join(self.tmp.name, "doan_001.flac")
        self.ban_do = os.path.join(self.tmp.name, "doan_001.nguoi_noi.txt")
        with open(self.audio, "wb") as f:
            f.write(b"fLaC" + b"\0" * 10)
        with open(self.ban_do, "w", encoding="utf-8") as f:
            f.write("00:00.0 - 00:05.0  Giảng viên\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_transcribe_tach_nguoi_noi_ep_verbatim_va_bo_tu_vung(self):
        ch = tao_cau_hinh(che_do_go_chu="smart", ngon_ngu=("vi-VN",), tu_vung=("SVM",))
        yc = ga.tao_yeu_cau(ch, "uri://a", "audio/flac", model="gemini-3.5-transcribe",
                            tach_nguoi_noi=True, moc_tung_tu=True)
        self.assertEqual(yc["generation_config"]["transcription_config"], {
            "mode": {"type": "verbatim", "diarization_mode": "speaker",
                     "timestamp_granularities": ["word"]},
            "language_codes": ["vi-VN"]})

    def test_transcribe_chi_moc_tung_tu(self):
        ch = tao_cau_hinh(che_do_go_chu="verbatim")
        yc = ga.tao_yeu_cau(ch, "uri://a", "audio/flac", model="gemini-3.5-transcribe", moc_tung_tu=True)
        self.assertEqual(yc["generation_config"]["transcription_config"]["mode"],
                         {"type": "verbatim", "timestamp_granularities": ["word"]})

    def test_model_da_nang_gui_prompt_audio_roi_tai_lieu(self):
        ch = tao_cau_hinh(model="gemini-3.5-transcribe")
        yc = ga.tao_yeu_cau(ch, "uri://a", "audio/flac", "P", model="gemini-3.8-flash",
                            tai_lieu=("uri://b", "text/plain"))
        self.assertEqual(yc["model"], "gemini-3.8-flash")
        self.assertEqual([p["type"] for p in yc["input"]], ["text", "audio", "document"])
        self.assertEqual(yc["input"][2], {"type": "document", "uri": "uri://b", "mime_type": "text/plain"})

    def test_ban_do_chen_vao_prompt(self):
        yc = ga.tao_yeu_cau(tao_cau_hinh(), "uri://a", "audio/flac", "P", model="gemini-3.8-flash",
                            van_ban_kem="00:00.0 - 00:05.0  A")
        self.assertTrue(yc["input"][0]["text"].endswith("SPEAKER MAP:\n00:00.0 - 00:05.0  A"))
        self.assertEqual(len(yc["input"]), 2)

    def test_trich_tu(self):
        self.assertEqual(ga.trich_tu(KQ_CO_TU), [
            {"tu": "Hello", "nguoi_noi": "spk_1", "bat_dau": 0.1, "ket_thuc": 0.45},
            {"tu": "world", "nguoi_noi": "spk_2", "bat_dau": 0.5, "ket_thuc": 0.85},
        ])
        self.assertEqual(ga._giay({"seconds": "2", "nanos": 500000000}), 2.5)

    def test_tai_len_ca_hai_file_roi_xoa_ca_hai(self):
        ten = iter(["files/au", "files/bd"])
        yeu_cau = []

        def may_chu(req, timeout=None):
            yeu_cau.append(req)
            url = req.full_url
            if url.endswith("/upload/v1beta/files"):
                return PhanHoi({}, hdr=headers(X_Goog_Upload_URL="https://upload.example/x"))
            if url == "https://upload.example/x":
                n = next(ten)
                return PhanHoi({"file": {"name": n, "uri": "https://g/" + n, "state": "ACTIVE",
                                         "mimeType": "text/plain" if n.endswith("bd") else "audio/flac"}})
            if url.endswith("/interactions"):
                return PhanHoi(KQ_XONG)
            return PhanHoi({})

        kh = ga.MayKhach("K", mo_url=may_chu)
        van_ban = kh.go_chu(self.audio, tao_cau_hinh(), "P", model="gemini-3.8-flash", file_kem=self.ban_do)
        self.assertEqual(van_ban, "Xin chào các bạn.")
        tai_ban_do = yeu_cau[2]
        self.assertEqual(tai_ban_do.get_header("X-goog-upload-header-content-type"), "text/plain")
        body = json.loads(next(r for r in yeu_cau if r.full_url.endswith("/interactions")).data)
        self.assertEqual(body["input"][2]["uri"], "https://g/files/bd")
        self.assertEqual(sorted(r.full_url.rsplit("/", 1)[1] for r in yeu_cau if r.get_method() == "DELETE"),
                         ["au", "bd"])


class TestApiKey(unittest.TestCase):
    def test_file_uu_tien_hon_bien_moi_truong(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": d, "GEMINI_API_KEY": "tu_env"}):
                self.assertEqual(ga.nguon_api_key(), ("tu_env", "GEMINI_API_KEY"))
                ga.luu_api_key("  tu_file  ")
                self.assertEqual(ga.lay_api_key(), "tu_file")
                ga.luu_api_key("")
                self.assertEqual(ga.lay_api_key(), "tu_env")

    def test_dung_lai_key_cua_google_ai_transcribe(self):
        with tempfile.TemporaryDirectory() as d:
            env = {k: v for k, v in os.environ.items() if k not in ga.BIEN_MOI_TRUONG}
            env["LOCALAPPDATA"] = d
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(ga.nguon_api_key(), (None, None))
                os.makedirs(os.path.join(d, "GoogleAITranscribe"))
                with open(ga.duong_dan_key_google_ai_transcribe(), "w", encoding="utf-8") as f:
                    f.write("key_gait\n")
                self.assertEqual(ga.nguon_api_key(), ("key_gait", ga.duong_dan_key_google_ai_transcribe()))
                ga.luu_api_key("key_guzz")
                self.assertEqual(ga.lay_api_key(), "key_guzz")


if __name__ == "__main__":
    unittest.main()
