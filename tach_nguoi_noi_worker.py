#!/usr/bin/env python3
"""
tach_nguoi_noi_worker.py
Tach nguoi noi (speaker diarization) cho mot file wav bang pyannote.audio.
Lay tu C:\\LecturerCleaner\\tach_nguoi_noi_worker.py, them bao tien do tung buoc.

File nay chay bang Python cua runtime RIENG (runtime\\nguoi_noi, co torch +
pyannote), KHONG chay bang Python cua app. App goi no qua subprocess.

Ket qua la file json:
    {
      "model": "...", "thiet_bi": "cuda", "thoi_luong_giay": 7412.3,
      "so_nguoi": 3,
      "doan": [{"bat_dau": 0.52, "ket_thuc": 14.1, "nguoi_noi": "SPEAKER_00"}, ...]
    }
"doan" khong chong lan nhau (moi thoi diem chi mot nguoi).

Token Hugging Face lay tu bien moi truong HF_TOKEN (app doc tu file rieng va dat
vao), noi luu model tu HF_HOME, che do khong mang tu HF_HUB_OFFLINE. Khong nhan
token qua tham so dong lenh de tranh lo trong nhat ky.

Stderr: moi dong thong bao cho nguoi doc bat dau bang "GUZZ|", dong tien do co
dang "GUZZ|TIEN_DO|<buoc>|<xong>|<tong>". Phan con lai la canh bao cua torch.

Cach dung:
    python tach_nguoi_noi_worker.py --kiem-tra
    python tach_nguoi_noi_worker.py bai_giang.wav --ra bai_giang.speakers.json --max 6

Ma thoat:
    0 = xong
    1 = loi khi xu ly file
    2 = moi truong chua san sang (thieu thu vien, chua co token / chua dong y
        dieu khoan model, khong co CUDA khi ep --thiet-bi cuda)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Windows thuong khong cho tao symlink, cache van chay duoc; bo canh bao cho gon log.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

MODEL_MAC_DINH = "pyannote/speaker-diarization-community-1"

MA_LOI_XU_LY = 1
MA_LOI_MOI_TRUONG = 2

TIEN_TO = "GUZZ|"


def bao(msg: str):
    print(TIEN_TO + msg, file=sys.stderr, flush=True)


class HookTienDo:
    """Hook cua pyannote: goi hook(buoc, artifact, file=..., total=..., completed=...)."""

    def __init__(self):
        self._lan_cuoi = 0.0

    def __call__(self, buoc, _artifact=None, file=None, total=None, completed=None):
        if total is None or completed is None:
            print(f"{TIEN_TO}TIEN_DO|{buoc}|1|1", file=sys.stderr, flush=True)
            return
        bay_gio = time.monotonic()
        if completed < total and bay_gio - self._lan_cuoi < 0.5:
            return
        self._lan_cuoi = bay_gio
        print(f"{TIEN_TO}TIEN_DO|{buoc}|{completed}|{total}", file=sys.stderr, flush=True)


def nap_pipeline(model: str, thiet_bi: str):
    try:
        import torch
        from pyannote.audio import Pipeline
    except Exception as e:  # ImportError, loi DLL cua torchcodec...
        bao(f"Khong nap duoc torch/pyannote.audio: {e}")
        bao("Chay lai cai_dat.ps1 -NguoiNoi.")
        sys.exit(MA_LOI_MOI_TRUONG)

    if thiet_bi == "auto":
        thiet_bi = "cuda" if torch.cuda.is_available() else "cpu"
    elif thiet_bi == "cuda" and not torch.cuda.is_available():
        bao("Da chon thiet bi cuda nhung torch khong thay GPU CUDA.")
        sys.exit(MA_LOI_MOI_TRUONG)

    try:
        pipeline = Pipeline.from_pretrained(model, token=os.environ.get("HF_TOKEN") or None)
    except Exception as e:
        bao(f"Khong tai duoc model {model}: {e}")
        bao("Kiem tra: da nhap token Hugging Face chua, va da bam dong y dieu khoan tai "
            f"https://huggingface.co/{model} chua.")
        sys.exit(MA_LOI_MOI_TRUONG)
    if pipeline is None:
        bao(f"Khong tai duoc model {model} (thuong do chua co token Hugging Face "
            "hoac chua dong y dieu khoan model).")
        sys.exit(MA_LOI_MOI_TRUONG)

    pipeline.to(torch.device(thiet_bi))
    return pipeline, thiet_bi


def doc_audio(duong_dan: str):
    """
    Doc wav vao bo nho roi dua waveform cho pyannote, de khong phu thuoc
    torchcodec/FFmpeg khi giai ma file tren Windows.
    """
    import soundfile as sf
    import torch

    du_lieu, tan_so = sf.read(duong_dan, dtype="float32", always_2d=True)  # (thoi_gian, kenh)
    if du_lieu.shape[1] > 1:
        du_lieu = du_lieu.mean(axis=1, keepdims=True)
    waveform = torch.from_numpy(du_lieu.T.copy())  # (kenh, thoi_gian)
    return {"waveform": waveform, "sample_rate": tan_so}, du_lieu.shape[0] / tan_so


def tach(pipeline, audio: dict, so_nguoi: int, it_nhat: int, nhieu_nhat: int):
    tham_so = {}
    if so_nguoi > 0:
        tham_so["num_speakers"] = so_nguoi
    else:
        if it_nhat > 0:
            tham_so["min_speakers"] = it_nhat
        if nhieu_nhat > 0:
            tham_so["max_speakers"] = nhieu_nhat

    kq = pipeline(audio, hook=HookTienDo(), **tham_so)

    # pyannote 4: DiarizeOutput co ban "exclusive" (khong chong lan).
    # Ban cu tra thang Annotation.
    ann = getattr(kq, "exclusive_speaker_diarization", None)
    if ann is None:
        ann = getattr(kq, "speaker_diarization", kq)

    doan = [
        {"bat_dau": round(turn.start, 3), "ket_thuc": round(turn.end, 3), "nguoi_noi": str(nguoi)}
        for turn, _, nguoi in ann.itertracks(yield_label=True)
    ]
    doan.sort(key=lambda d: d["bat_dau"])
    return doan


def vram_dinh_mb(thiet_bi: str):
    if thiet_bi != "cuda":
        return None
    import torch
    return round(torch.cuda.max_memory_allocated() / 2**20)


def ghi_json(duong_dan: str, du_lieu: dict):
    tam = duong_dan + ".tmp"
    with open(tam, "w", encoding="utf-8") as f:
        json.dump(du_lieu, f, ensure_ascii=False, indent=1)
    os.replace(tam, duong_dan)


def thong_tin_moi_truong(thiet_bi: str) -> dict:
    import torch
    thong_tin = {
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "cuda": torch.cuda.is_available(),
        "thiet_bi": thiet_bi,
    }
    if torch.cuda.is_available():
        thong_tin["gpu"] = torch.cuda.get_device_name(0)
    try:
        import pyannote.audio
        thong_tin["pyannote"] = pyannote.audio.__version__
    except Exception:
        pass
    return thong_tin


def main():
    ap = argparse.ArgumentParser(description="Tach nguoi noi cho file wav bang pyannote.audio")
    ap.add_argument("wav", nargs="?", help="File wav can tach")
    ap.add_argument("--ra", help="File json ket qua (mac dinh: <wav>.speakers.json)")
    ap.add_argument("--model", default=MODEL_MAC_DINH)
    ap.add_argument("--thiet-bi", default="auto", choices=["auto", "cuda", "cpu"])
    ap.add_argument("--so-nguoi", type=int, default=0, help="Biet chinh xac so nguoi (0 = tu doan)")
    ap.add_argument("--min", dest="it_nhat", type=int, default=0)
    ap.add_argument("--max", dest="nhieu_nhat", type=int, default=0)
    ap.add_argument("--kiem-tra", action="store_true",
                    help="Chi nap model de kiem tra moi truong roi thoat")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if not args.kiem_tra and not args.wav:
        ap.error("can duong dan wav (hoac dung --kiem-tra)")

    luc_dau = time.monotonic()
    bao("Dang nap model...")
    pipeline, thiet_bi = nap_pipeline(args.model, args.thiet_bi)
    bao(f"Da nap model {args.model} tren {thiet_bi} ({time.monotonic() - luc_dau:.0f}s)")

    if args.kiem_tra:
        print(json.dumps({"ok": True, **thong_tin_moi_truong(thiet_bi)}, ensure_ascii=False))
        return

    if not os.path.isfile(args.wav):
        bao(f"Khong thay file: {args.wav}")
        sys.exit(MA_LOI_XU_LY)

    duong_dan_ra = args.ra or os.path.splitext(args.wav)[0] + ".speakers.json"

    try:
        audio, thoi_luong = doc_audio(args.wav)
        bao(f"Dang tach nguoi noi: {os.path.basename(args.wav)} ({thoi_luong / 60:.1f} phut)")
        luc_tach = time.monotonic()
        doan = tach(pipeline, audio, args.so_nguoi, args.it_nhat, args.nhieu_nhat)
    except Exception as e:
        bao(f"Loi khi tach nguoi noi: {type(e).__name__}: {e}")
        sys.exit(MA_LOI_XU_LY)

    so_nguoi = len({d["nguoi_noi"] for d in doan})
    ghi_json(duong_dan_ra, {
        "model": args.model,
        "thiet_bi": thiet_bi,
        "file_wav": os.path.abspath(args.wav),
        "thoi_luong_giay": round(thoi_luong, 2),
        "giay_xu_ly": round(time.monotonic() - luc_tach, 1),
        "so_nguoi": so_nguoi,
        "vram_dinh_mb": vram_dinh_mb(thiet_bi),
        "doan": doan,
    })
    bao(f"Xong trong {time.monotonic() - luc_tach:.0f}s: {len(doan)} luot noi, {so_nguoi} nguoi noi")
    print(duong_dan_ra)


if __name__ == "__main__":
    main()
