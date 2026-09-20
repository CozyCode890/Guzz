# ============================================================================
#  cai_dat.ps1
#  Tao runtime CUC BO cho Guzz ngay trong thu muc app, khong dung Python / ffmpeg
#  cua he thong. Nho vay sau nay dong goi ban cai dat chi can chep ca thu muc.
#
#      runtime\python\      Python embeddable + thu vien cua app (requirements.txt)
#      runtime\ffmpeg\      ffmpeg.exe
#      runtime\nguoi_noi\   (tuy chon) Python embeddable + torch + pyannote.audio
#
#  Viet cho Windows PowerShell 5.1 (co san tren Windows 10), chay duoc ca PowerShell 7.
#
#  Cach chay: chuot phai file nay -> "Run with PowerShell", hoac mo PowerShell tai
#  thu muc app roi go:
#      powershell -ExecutionPolicy Bypass -File .\cai_dat.ps1
#
#  Tuy chon:
#      -NguoiNoi        cai them runtime nhan dien nguoi noi (torch, vai GB)
#      -ChiNguoiNoi     chi cai runtime nhan dien nguoi noi
#      -Cpu             torch ban CPU (may khong co GPU NVIDIA)
#      -CudaTag cu128   chon ban CUDA cua torch (mac dinh: cu126, loi thi thu cu128)
#      -KhongShortcut   khong tao shortcut o Desktop / Start Menu
#      -GoBo            xoa thu muc runtime va shortcut (giu nguyen du lieu, config)
# ============================================================================

param(
    [switch]$NguoiNoi,
    [switch]$ChiNguoiNoi,
    [switch]$Cpu,
    [string]$CudaTag = "",
    [switch]$KhongShortcut,
    [switch]$GoBo
)

$ErrorActionPreference = "Stop"
# Thanh tien do cua Invoke-WebRequest tren PowerShell 5.1 lam tai file cham di hang chuc lan.
$ProgressPreference = "SilentlyContinue"
# Windows 10 ban cu mac dinh TLS 1.0, python.org va pypi tu choi.
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

$PhienBanPython = "3.12.10"
$TorchPhienBan = "2.14.0"
$TorchaudioPhienBan = "2.11.0"

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runtime = Join-Path $AppDir "runtime"
$PyApp = Join-Path $Runtime "python"
$PyNguoiNoi = Join-Path $Runtime "nguoi_noi"
$FfmpegDir = Join-Path $Runtime "ffmpeg"
$TaiVe = Join-Path $Runtime "_tai_ve"
$Icon = Join-Path $AppDir "gui\assets\icon.ico"
$MainPy = Join-Path $AppDir "gui\main.py"
$Shortcuts = @(
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "Guzz.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Programs")) "Guzz.lnk")
)

function Bao($chu, $mau = "Cyan") { Write-Host $chu -ForegroundColor $mau }

function Dung($chu) {
    Write-Host $chu -ForegroundColor Red
    exit 1
}

if ($GoBo) {
    foreach ($s in $Shortcuts) { Remove-Item -Path $s -Force -ErrorAction SilentlyContinue }
    Remove-Item -Recurse -Force $Runtime -ErrorAction SilentlyContinue
    Bao "Da xoa $Runtime va shortcut. Du lieu (config, nhat ky) van con." "Yellow"
    exit 0
}

if ([Environment]::OSVersion.Version.Major -lt 10) {
    Dung "Guzz can Windows 10 tro len."
}
if (-not [Environment]::Is64BitOperatingSystem) {
    Dung "Guzz can Windows 64-bit."
}

New-Item -ItemType Directory -Force -Path $TaiVe | Out-Null

function Tai-Ve($url, $dich) {
    if (Test-Path $dich) { return }
    Bao "Tai $url"
    $tam = "$dich.part"
    Invoke-WebRequest -Uri $url -OutFile $tam -UseBasicParsing
    Move-Item -Force $tam $dich
}

# Out-Host: trong mot ham PowerShell, output cua lenh ngoai se bi gop vao gia tri tra ve.
function Chay($exe, [string[]]$thamSo) {
    & $exe @thamSo | Out-Host
    if ($LASTEXITCODE -ne 0) { Dung "Lenh that bai (ma $LASTEXITCODE): $exe $($thamSo -join ' ')" }
}

# PowerShell 5.1: chuyen huong stderr cua lenh ngoai khi ErrorActionPreference = Stop
# bien moi dong stderr thanh loi va dung ca script.
function Chay-Im($exe, [string[]]$thamSo) {
    $cu = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $exe @thamSo *> $null
    $ma = $LASTEXITCODE
    $ErrorActionPreference = $cu
    return $ma
}

# ---------------------------------------------------------------------------
#  Python embeddable: giai nen, bat "import site" de doc Lib\site-packages, cai pip.
# ---------------------------------------------------------------------------
function Tao-Python($thuMuc) {
    $py = Join-Path $thuMuc "python.exe"
    if (-not (Test-Path $py)) {
        $zip = Join-Path $TaiVe "python-$PhienBanPython-embed-amd64.zip"
        Tai-Ve "https://www.python.org/ftp/python/$PhienBanPython/python-$PhienBanPython-embed-amd64.zip" $zip
        Bao "Giai nen Python $PhienBanPython vao $thuMuc"
        Expand-Archive -Path $zip -DestinationPath $thuMuc -Force
        $pth = Get-ChildItem -Path $thuMuc -Filter "python*._pth" | Select-Object -First 1
        $dong = Get-Content $pth.FullName | ForEach-Object { $_ -replace '^\s*#\s*import site', 'import site' }
        Set-Content -Path $pth.FullName -Value $dong -Encoding ASCII
    }
    if ((Chay-Im $py @("-m", "pip", "--version")) -ne 0) {
        $getPip = Join-Path $TaiVe "get-pip.py"
        Tai-Ve "https://bootstrap.pypa.io/get-pip.py" $getPip
        Bao "Cai pip cho $thuMuc"
        Chay $py @($getPip, "--no-warn-script-location")
    }
    return $py
}

# ---------------------------------------------------------------------------
#  ffmpeg: chep ffmpeg dang co tren may (ke ca ban scoop), khong co thi tai ban essentials.
# ---------------------------------------------------------------------------
function Tim-Ffmpeg-Tren-May {
    $cmd = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
    if (-not $cmd) { return $null }
    $p = $cmd.Source
    # Scoop dat mot "shim" nho trong PATH; file .shim canh no ghi duong dan that.
    $shim = [IO.Path]::ChangeExtension($p, ".shim")
    if (Test-Path $shim) {
        foreach ($d in Get-Content $shim) {
            if ($d -match '^\s*path\s*=\s*"?([^"]+)"?\s*$') { return $Matches[1] }
        }
    }
    return $p
}

function Cai-Ffmpeg {
    $dich = Join-Path $FfmpegDir "ffmpeg.exe"
    if (Test-Path $dich) { Bao "ffmpeg da co: $dich"; return }
    New-Item -ItemType Directory -Force -Path $FfmpegDir | Out-Null
    $coSan = Tim-Ffmpeg-Tren-May
    if ($coSan -and (Test-Path $coSan)) {
        Bao "Chep ffmpeg tu $coSan"
        Copy-Item $coSan $dich
        return
    }
    $zip = Join-Path $TaiVe "ffmpeg-release-essentials.zip"
    Tai-Ve "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" $zip
    $giaiNen = Join-Path $TaiVe "ffmpeg"
    Expand-Archive -Path $zip -DestinationPath $giaiNen -Force
    $exe = Get-ChildItem -Path $giaiNen -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
    if (-not $exe) { Dung "Khong thay ffmpeg.exe trong $zip" }
    Copy-Item $exe.FullName $dich
    Remove-Item -Recurse -Force $giaiNen -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
#  Shortcut
# ---------------------------------------------------------------------------
function Tao-Shortcut {
    $pythonw = Join-Path $PyApp "pythonw.exe"
    $shell = New-Object -ComObject WScript.Shell
    foreach ($s in $Shortcuts) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $s) | Out-Null
        $lnk = $shell.CreateShortcut($s)
        $lnk.TargetPath = $pythonw
        $lnk.Arguments = "`"$MainPy`""
        $lnk.WorkingDirectory = $AppDir
        if (Test-Path $Icon) { $lnk.IconLocation = "$Icon,0" }
        $lnk.Description = "Guzz - chuyen audio va video thanh van ban bang Google AI Studio"
        $lnk.Save()
        Bao "Da tao shortcut: $s" "Green"
    }
}

# ---------------------------------------------------------------------------
#  1. Runtime cua app
# ---------------------------------------------------------------------------
if (-not $ChiNguoiNoi) {
    Bao "==== Runtime cua app ====" "Green"
    $py = Tao-Python $PyApp
    # --no-deps: requirements.txt da liet ke du, bo PySide6-Addons va matplotlib khong can.
    Chay $py @("-m", "pip", "install", "--no-deps", "--no-warn-script-location", "-r", (Join-Path $AppDir "requirements.txt"))
    Cai-Ffmpeg
    Chay $py @("-c", "import numpy, scipy, noisereduce, PySide6.QtNetwork, PySide6.QtSvgWidgets, qfluentwidgets; print('App runtime OK, PySide6', PySide6.__version__)")
    if (-not $KhongShortcut) { Tao-Shortcut }
}

# ---------------------------------------------------------------------------
#  2. Runtime nhan dien nguoi noi
# ---------------------------------------------------------------------------
if ($NguoiNoi -or $ChiNguoiNoi) {
    Bao "==== Runtime nhan dien nguoi noi (torch + pyannote.audio) ====" "Green"
    $py = Tao-Python $PyNguoiNoi

    if ($Cpu) {
        $tags = @("cpu")
    } elseif ($CudaTag) {
        $tags = @($CudaTag)
    } elseif (Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue) {
        $tags = @("cu126", "cu128")
    } else {
        Bao "Khong thay GPU NVIDIA (nvidia-smi), cai torch ban CPU." "Yellow"
        $tags = @("cpu")
    }

    $daCaiTorch = $false
    foreach ($tag in $tags) {
        Bao "Cai torch $TorchPhienBan + torchaudio $TorchaudioPhienBan ($tag)..."
        & $py -m pip install --no-warn-script-location "torch==$TorchPhienBan" "torchaudio==$TorchaudioPhienBan" --index-url "https://download.pytorch.org/whl/$tag" | Out-Host
        if ($LASTEXITCODE -eq 0) { $daCaiTorch = $true; break }
        Bao "Ban $tag khong cai duoc, thu ban khac..." "Yellow"
    }
    if (-not $daCaiTorch) { Dung "Khong cai duoc torch." }

    Chay $py @("-m", "pip", "install", "--no-warn-script-location", "-r", (Join-Path $AppDir "requirements_nguoi_noi.txt"))
    Chay $py @("-c", "import torch, pyannote.audio; print('torch', torch.__version__, '| CUDA:', torch.cuda.is_available(), '| pyannote', pyannote.audio.__version__)")

    Bao ""
    Bao "==== VIEC BAN CAN TU LAM (chi mot lan) ====" "Green"
    Bao "1. Dang nhap https://huggingface.co, mo trang model va bam dong y dieu khoan:" "White"
    Bao "      https://huggingface.co/pyannote/speaker-diarization-community-1" "White"
    Bao "2. Tao token loai 'Read' tai https://huggingface.co/settings/tokens" "White"
    Bao "3. Mo Guzz -> trang Nhan dien nguoi noi -> dan token -> Kiem tra moi truong." "White"
}

Remove-Item -Recurse -Force $TaiVe -ErrorAction SilentlyContinue
Bao ""
Bao "Xong. Mo app bang shortcut Guzz, hoac: `"$(Join-Path $PyApp 'pythonw.exe')`" `"$MainPy`"" "Green"
