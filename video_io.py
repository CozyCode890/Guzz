"""
video_io.py
Doc thong tin rung (stream) am thanh trong file video va rut mot rung ra file
audio rieng, van bang cach goi thang ffmpeg nhu am_thanh_io.

VI SAO TACH RA MOT FILE:
  - Video bai giang thuong nang hang GB. Doc thang tu video thi ffmpeg phai giai
    ma lai ca luong hinh moi lan (lam sach mot lan, pyannote tren audio goc mot
    lan nua). Rut audio ra file tam roi dung lai file do nhanh hon han.
  - Video quay bang may anh / phan mem hop thoai hay co nhieu rung tieng (mic
    cai ao, mic phong, tieng may quay). Rut dung rung can dung thi ban go chu
    khong dinh tieng on cua rung kia.

Khong dung ffprobe: ban cai dat chi chep ffmpeg.exe vao runtime\\ffmpeg, va
"ffmpeg -i" da in danh sach stream ra stderr.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass

from am_thanh_io import CO_KHONG_CUA_SO, tim_ffmpeg

# Duoi file video duoc nhan mac dinh (xem [XU_LY_VIDEO] duoi_file_video).
DUOI_VIDEO_MAC_DINH = (".mp4", ".mkv", ".mov", ".avi", ".wmv", ".webm", ".m4v",
                       ".mpg", ".mpeg", ".ts", ".flv", ".3gp")

# "  Stream #0:1[0x2](vie): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 128 kb/s"
# Phan [0x2] chi co o ffmpeg moi, phan (vie) chi co khi file khai bao ngon ngu.
_RE_STREAM = re.compile(
    r"^\s*Stream #\d+:(\d+)(?:\[[^\]]*\])?(?:\(([^)]*)\))?:\s*(\w+):\s*(.*)$", re.MULTILINE)


@dataclass
class RungAmThanh:
    """Mot rung tieng trong file video. chi_so la thu tu TRONG CAC RUNG TIENG (0, 1, 2...),
    dung cho "-map 0:a:<chi_so>"; chi_so_stream la so thu tu that trong file (#0:1)."""
    chi_so: int
    chi_so_stream: int
    codec: str = ""
    ngon_ngu: str = ""
    chi_tiet: str = ""

    def mo_ta(self) -> str:
        phan = [f"#{self.chi_so}"]
        if self.ngon_ngu:
            phan.append(self.ngon_ngu)
        if self.codec:
            phan.append(self.codec)
        if self.chi_tiet:
            phan.append(self.chi_tiet)
        return " · ".join(phan)


def la_file_video(duong_dan: str, duoi_video) -> bool:
    return os.path.splitext(duong_dan)[1].lower() in tuple(duoi_video)


def cac_rung_am_thanh(duong_dan: str) -> list[RungAmThanh]:
    """
    Danh sach rung tieng trong file, theo thu tu ffmpeg liet ke. Danh sach rong =
    file doc duoc nhung khong co rung tieng nao (video cam).

    Nem RuntimeError neu khong chay duoc ffmpeg, hoac ffmpeg khong mo noi file:
    file hong phai bao loi chu khong duoc lan thanh "video khong co tieng" roi bi
    bo qua am tham.
    """
    lenh = [tim_ffmpeg(), "-hide_banner", "-nostdin", "-i", duong_dan]
    try:
        kq = subprocess.run(lenh, capture_output=True, creationflags=CO_KHONG_CUA_SO, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"Khong doc duoc {os.path.basename(duong_dan)}: {e}") from None

    loi = kq.stderr.decode("utf-8", "replace")
    cac_stream = _RE_STREAM.findall(loi)
    # "ffmpeg -i" khong co tham so dau ra nen luon tra ve khac 0; file mo duoc thi
    # van liet ke duoc stream. Khong stream nao = khong mo noi file.
    if not cac_stream:
        raise RuntimeError(f"ffmpeg khong mo duoc {os.path.basename(duong_dan)}: {loi.strip()[-600:]}")

    rung = []
    for chi_so_stream, ngon_ngu, kieu, phan_con_lai in cac_stream:
        if kieu.lower() != "audio":
            continue
        # "aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 128 kb/s"
        phan = [p.strip() for p in phan_con_lai.split(",")]
        codec = phan[0].split(" ")[0] if phan else ""
        # Bo cac phan ky thuat (fltp, 128 kb/s), giu tan so va so kenh cho de doc.
        chi_tiet = ", ".join(p for p in phan[1:3] if p)
        rung.append(RungAmThanh(len(rung), int(chi_so_stream), codec,
                                (ngon_ngu or "").strip(), chi_tiet))
    return rung


def chon_rung(cac_rung: list[RungAmThanh], yeu_cau: str | int | None) -> int | None:
    """
    Chi so rung se dung. yeu_cau: "auto" / None = rung dau tien; so = rung thu do
    (khong co thi lui ve rung dau tien). Tra ve None neu file khong co rung tieng nao.
    """
    if not cac_rung:
        return None
    if yeu_cau is None or str(yeu_cau).strip().lower() in ("", "auto"):
        return cac_rung[0].chi_so
    try:
        so = int(str(yeu_cau).strip())
    except ValueError:
        return cac_rung[0].chi_so
    return so if 0 <= so < len(cac_rung) else cac_rung[0].chi_so


def tach_am_thanh(vao: str, ra: str, rung: int | None = None, sr: int | None = None):
    """
    Rut mot rung tieng cua file video ra file audio (dinh dang theo duoi file ra),
    bo luong hinh. sr = None thi giu nguyen tan so goc.

    Ghi ra file .part roi moi doi ten: tat may giua chung khong de lai file hong
    mang ten that, va lan chay lai se rut lai tu dau.
    """
    tam = ra + ".part"
    dinh_dang = os.path.splitext(ra)[1].lstrip(".").lower()
    lenh = [tim_ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", vao]
    if rung is not None:
        lenh += ["-map", f"0:a:{int(rung)}"]
    lenh += ["-vn", "-ac", "1"]
    if sr:
        lenh += ["-ar", str(int(sr))]
    lenh += ["-f", dinh_dang, tam]

    os.makedirs(os.path.dirname(os.path.abspath(ra)), exist_ok=True)
    kq = subprocess.run(lenh, capture_output=True, creationflags=CO_KHONG_CUA_SO)
    if kq.returncode != 0:
        try:
            os.remove(tam)
        except OSError:
            pass
        loi = kq.stderr.decode("utf-8", "replace").strip()[-600:]
        raise RuntimeError(f"ffmpeg khong tach duoc tieng tu {os.path.basename(vao)}: {loi}")
    os.replace(tam, ra)
