"""
am_thanh_io.py
Doc / ghi audio bang cach goi thang ffmpeg (lay tu GoogleAITranscribe).

Khac GoogleAITranscribe: tim ffmpeg trong runtime\\ffmpeg cua app truoc, roi moi
toi duong dan tu khai bao va PATH, de ban cai dat khong phu thuoc may nguoi dung
da cai ffmpeg hay chua.

VI SAO KHONG DUNG pydub NHU LecturerCleaner:
  - pydub goi ffmpeg ma khong co co CREATE_NO_WINDOW. App GUI chay bang
    pythonw.exe (khong co console), nen moi lan goi Windows lai bat len mot cua
    so console den roi tat.
  - pydub ha tan so lay mau bang audioop, module da bi go khoi Python 3.13.
  - Doc qua pydub phai giu ca ban raw_data lan AudioSegment trong RAM.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import wave

import numpy as np

from duong_dan import FFMPEG_CUC_BO

OUTPUT_SAMPLE_WIDTH = 2          # luon ghi PCM 16-bit
_BIEN_DO_TOI_DA = 32768.0        # bien do toi da cua mau 16-bit

# App GUI chay bang pythonw (khong co console); khong co co nay moi lan goi
# ffmpeg.exe se bat len mot cua so console den.
CO_KHONG_CUA_SO = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_MA_HOA = {
    "flac": ["-c:a", "flac", "-f", "flac"],
    "mp3": ["-c:a", "libmp3lame", "-b:a", "64k", "-f", "mp3"],
}

# GUI dat gia tri nay theo [HE_THONG] duong_dan_ffmpeg ("" hoac "auto" = tu tim).
duong_dan_ffmpeg_tu_dat = ""


def tim_ffmpeg() -> str:
    tu_dat = os.path.expandvars((duong_dan_ffmpeg_tu_dat or "").strip())
    if tu_dat and tu_dat.lower() != "auto":
        if os.path.isfile(tu_dat):
            return tu_dat
        raise RuntimeError(f"Khong thay ffmpeg tai duong dan da khai bao: {tu_dat}")
    if os.path.isfile(FFMPEG_CUC_BO):
        return FFMPEG_CUC_BO
    p = shutil.which("ffmpeg")
    if not p:
        raise RuntimeError(
            "Khong tim thay ffmpeg. Chay cai_dat.ps1 de chep ffmpeg vao runtime\\ffmpeg, "
            "hoac khai bao duong dan ffmpeg.exe trong trang Cai dat."
        )
    return p


def doc_audio(duong_dan: str, sr: int = 16000) -> np.ndarray:
    """Giai ma mot file audio bat ky thanh mang float32 mono [-1, 1] o tan so sr."""
    lenh = [
        tim_ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", duong_dan, "-vn", "-ac", "1", "-ar", str(int(sr)),
        "-f", "s16le", "-acodec", "pcm_s16le", "pipe:1",
    ]
    kq = subprocess.run(lenh, capture_output=True, creationflags=CO_KHONG_CUA_SO)
    if kq.returncode != 0:
        loi = kq.stderr.decode("utf-8", "replace").strip()[-600:]
        raise RuntimeError(f"ffmpeg khong doc duoc {os.path.basename(duong_dan)}: {loi}")
    so_byte = len(kq.stdout) - len(kq.stdout) % OUTPUT_SAMPLE_WIDTH
    if so_byte == 0:
        raise RuntimeError(f"File {os.path.basename(duong_dan)} khong co du lieu am thanh.")
    mau = np.frombuffer(kq.stdout, dtype=np.int16, count=so_byte // OUTPUT_SAMPLE_WIDTH)
    return mau.astype(np.float32) / _BIEN_DO_TOI_DA


_THOI_LUONG = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2}(?:\.\d+)?)")


def do_thoi_luong(duong_dan: str) -> float | None:
    """
    Thoi luong (giay) doc tu phan dau file, khong giai ma ca file. None neu ffmpeg
    khong doc duoc. Khong can ffprobe: "ffmpeg -i" in dong "Duration:" ra stderr.
    """
    try:
        kq = subprocess.run([tim_ffmpeg(), "-hide_banner", "-nostdin", "-i", duong_dan],
                            capture_output=True, creationflags=CO_KHONG_CUA_SO, timeout=30)
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        return None
    m = _THOI_LUONG.search(kq.stderr.decode("utf-8", "replace"))
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def chuyen_ma(vao: str, ra: str, sr: int = 16000):
    """Doi thang mot file sang mono sr Hz (dinh dang theo duoi file ra), khong nap vao RAM."""
    tam = ra + ".part"
    dinh_dang = os.path.splitext(ra)[1].lstrip(".").lower()
    lenh = [tim_ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-i", vao, "-vn", "-ac", "1", "-ar", str(int(sr)), "-f", dinh_dang, tam]
    kq = subprocess.run(lenh, capture_output=True, creationflags=CO_KHONG_CUA_SO)
    if kq.returncode != 0:
        try:
            os.remove(tam)
        except OSError:
            pass
        loi = kq.stderr.decode("utf-8", "replace").strip()[-600:]
        raise RuntimeError(f"ffmpeg khong doi duoc {os.path.basename(vao)}: {loi}")
    os.replace(tam, ra)


def _sang_pcm16(y: np.ndarray) -> bytes:
    y = np.clip(y, -1.0, 1.0)
    return (y * (_BIEN_DO_TOI_DA - 1)).astype(np.int16).tobytes()


def ghi_audio(y: np.ndarray, sr: int, duong_dan: str, dinh_dang: str | None = None):
    """
    Ghi mang float32 [-1, 1] ra file mono. dinh_dang: wav | flac | mp3
    (mac dinh lay theo duoi file). Ghi ra file .part roi moi doi ten, nen tat
    may giua chung khong de lai file hong mang ten that.
    """
    dinh_dang = (dinh_dang or os.path.splitext(duong_dan)[1].lstrip(".")).lower()
    tam = duong_dan + ".part"

    if dinh_dang == "wav":
        with wave.open(tam, "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(OUTPUT_SAMPLE_WIDTH)
            f.setframerate(int(sr))
            f.writeframes(_sang_pcm16(y))
    elif dinh_dang in _MA_HOA:
        lenh = [
            tim_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "s16le", "-ar", str(int(sr)), "-ac", "1", "-i", "pipe:0",
            *_MA_HOA[dinh_dang], tam,
        ]
        kq = subprocess.run(lenh, input=_sang_pcm16(y), capture_output=True,
                            creationflags=CO_KHONG_CUA_SO)
        if kq.returncode != 0:
            try:
                os.remove(tam)
            except OSError:
                pass
            loi = kq.stderr.decode("utf-8", "replace").strip()[-600:]
            raise RuntimeError(f"ffmpeg khong ghi duoc {os.path.basename(duong_dan)}: {loi}")
    else:
        raise ValueError(f"Khong ho tro dinh dang '{dinh_dang}'")

    os.replace(tam, duong_dan)
