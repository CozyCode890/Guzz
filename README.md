# Guzz — chuyển âm thanh và video thành văn bản

Guzz là app riêng chỉ làm một việc: **chọn tệp âm thanh hoặc video → bấm Bắt đầu → ra bản gõ chữ**.
Không theo dõi thư mục, không thời khoá biểu, không chạy ngầm. Phần xử lý lấy từ
GoogleAITranscribe (làm sạch âm thanh, cắt đoạn, Google AI Studio, điều tiết token),
giao diện theo GoogleAITranscribe, lớp nhận diện người nói tham khảo LecturerCleaner.

## 1. Ý tưởng trong một hình

```
bai giang.m4a / bai giang.mp4  (chọn / kéo thả vào app, lẫn lộn hai loại cũng được)
   │
   ├─ (0) là video: tách rãnh tiếng ra tệp tạm                  ← thẻ "Tệp video", mục 7
   ├─ (1) làm sạch: khử ồn, cân bằng âm lượng, cắt khoảng lặng  ← preset "Âm thanh, video & cắt đoạn"
   ├─ (2) cắt đoạn ~10 phút ở chỗ lặng nhất
   ├─ (3) (nếu bật) nhận diện người nói — 3 cách, xem mục 5
   ├─ (4) gửi từng đoạn lên Google AI Studio (hết hạn mức / quá tải → model dự phòng, mục 6)
   └─ (5) ghép lại → bai giang.txt
          nằm CÙNG THƯ MỤC với tệp nguồn nếu ô "Lưu vào" để trống
```

Mốc thời gian trong bản gõ chữ luôn tính theo **tệp gốc**, kể cả khi đã cắt khoảng lặng.

## 2. Cài đặt (Windows 10 / 11, 64-bit)

Mọi thư viện nằm **trong thư mục app** (`runtime\`), không dùng Python hay ffmpeg của máy:

```
runtime\python\      Python 3.12 embeddable + thư viện app (≈450 MB)
runtime\ffmpeg\      ffmpeg.exe
runtime\nguoi_noi\   (tuỳ chọn) Python embeddable + torch + pyannote.audio (vài GB)
```

Mở PowerShell tại thư mục app:

```powershell
powershell -ExecutionPolicy Bypass -File .\cai_dat.ps1              # runtime app + ffmpeg + shortcut
powershell -ExecutionPolicy Bypass -File .\cai_dat.ps1 -NguoiNoi    # thêm runtime nhận diện người nói
```

| Tuỳ chọn | Ý nghĩa |
|---|---|
| `-NguoiNoi` | cài thêm `runtime\nguoi_noi` |
| `-ChiNguoiNoi` | chỉ cài `runtime\nguoi_noi` (nút **Cài đặt runtime** trong app gọi cách này) |
| `-Cpu` / `-CudaTag cu128` | torch bản CPU / chọn bản CUDA (mặc định tự thấy GPU NVIDIA thì dùng cu126, lỗi thì thử cu128) |
| `-KhongShortcut` | không tạo shortcut Desktop / Start Menu |
| `-GoBo` | xoá `runtime\` và shortcut, giữ nguyên dữ liệu |

Script viết cho **Windows PowerShell 5.1** (có sẵn trên Windows 10): tự bật TLS 1.2, không dùng
cú pháp của PowerShell 7. ffmpeg: có sẵn trên máy (kể cả bản scoop) thì chép vào, không có thì
tải bản essentials từ gyan.dev.

Mở app: shortcut **Guzz**, hoặc `Guzz.cmd`, hoặc
`runtime\python\pythonw.exe gui\main.py "tệp 1.m4a" "tệp 2.mp3"`.
Mở app lần hai (vd kéo tệp thả lên shortcut) thì tệp được thêm vào cửa sổ đang mở.

Thư viện được ghim phiên bản trong `requirements.txt` (cài `--no-deps`, cố ý bỏ PySide6-Addons
≈550 MB và matplotlib vì app không dùng) và `requirements_nguoi_noi.txt`.

## 3. API key của Google AI Studio

Trang **Google AI Studio** → dán key → **Lưu key** → **Kiểm tra kết nối**. Key lưu trong
`%LOCALAPPDATA%\Guzz\api_key.txt`, không nằm trong config. Chưa nhập thì app lần lượt dùng biến
môi trường `GEMINI_API_KEY` / `GOOGLE_API_KEY`, rồi key đã lưu của GoogleAITranscribe.

## 4. Dùng app — trang Chuyển đổi

- **Thêm tệp / Thêm thư mục** hoặc kéo thả (cả thư mục). Tệp âm thanh và tệp video kéo chung một lượt
  đều được, app xử lý lẫn lộn trong cùng hàng đợi. Cột Thời lượng tự đọc bằng ffmpeg.
- **Lưu vào**: để trống = cùng thư mục với từng tệp nguồn; đường dẫn tương đối (vd `Transcripts`)
  tính từ thư mục chứa tệp nguồn.
- Công tắc nhanh: Khử ồn, Cắt khoảng lặng, Nhận diện người nói + chọn cách, **Model**. Model đang bị khoá
  (hết hạn mức, quá tải…) hiện mờ kèm `🔒 14:00` và không chọn được; cách nhận diện không hợp với model hiện
  `🔒` (xem mục 5).
- **Bắt đầu** chạy các tệp đang chờ / lỗi / đã dừng. Đang chạy vẫn thêm tệp được, tệp mới vào luôn hàng đợi.
- **Dừng**: dừng ở chỗ an toàn gần nhất. Bấm Bắt đầu lại thì làm tiếp từ đoạn đang dở,
  **không gửi lại** các đoạn đã gõ chữ xong.
- Chuột phải một dòng: mở bản gõ chữ, mở thư mục, mở tệp nguồn, **Chạy lại**, bỏ khỏi danh sách.
  Nhấp đúp: mở bản gõ chữ (hoặc tệp nguồn nếu chưa có).
- Lỗi API key sai, model không hợp cách nhận diện, hay mọi model đều khoá lâu thì dừng cả hàng đợi (lỗi sẽ
  lặp lại ở mọi tệp); lỗi khác thì làm tiếp hoặc dừng tuỳ **Cài đặt → Hàng đợi**. Hết hạn mức, quá tải,
  bị bộ lọc chặn thì **không** làm hỏng tệp: app đổi sang model dự phòng (mục 6).

## 5. Nhận diện người nói

Bật ở trang Chuyển đổi hoặc tab **Nhận diện người nói** (tab này chứa toàn bộ tuỳ chỉnh).

| | pyannote + prompt | Gemini tự tách | Kết hợp |
|---|---|---|---|
| Ai tách người nói | pyannote trên máy | gemini-3.5-transcribe | pyannote trên máy |
| Gửi cho Google | **2 tệp**: âm thanh + bản đồ người nói (.txt), kèm prompt | âm thanh | âm thanh |
| Model (trang Google AI Studio) | **chỉ model đa năng** | **chỉ *-transcribe** | **chỉ *-transcribe** (mốc từng từ) |
| Ghép tên | Google ghi tên theo bản đồ | Google gắn nhãn, app đặt tên | app ghép trên máy (thuật toán LecturerCleaner) |
| Tên thống nhất cả buổi | có | **chỉ trong từng đoạn** | có |
| Từ vựng chuyên ngành | có | không (Google từ chối) | không |
| Chế độ smart | tuỳ model | không, bắt buộc verbatim | không, bắt buộc verbatim |
| Cần torch | có | không | có |

Vì sao có 3 cách: model `*-transcribe` **không nhận prompt hay tệp kèm**, nên muốn gửi bản đồ
người nói cho Google thì phải dùng model đa năng (cách 1). Google cũng có sẵn tách người nói trong
`gemini-3.5-transcribe` (cách 2), nhưng theo tài liệu của Google: từ 3 người trở lên còn là thử
nghiệm, không đi cùng smart / từ vựng, và nhãn `spk_1`, `spk_2` chỉ đúng trong một yêu cầu. App gọi
người nói lâu nhất mỗi đoạn là giảng viên, người khác đánh số lại mỗi đoạn. Cách 3 lấy mốc thời gian
từng từ của Google ghép với lượt nói của pyannote, giống LecturerCleaner ghép với Buzz.
**Nên thử cả ba trên cùng một buổi học rồi giữ cách cho kết quả tốt nhất.**

### Model quyết định cách nào dùng được

App chỉ còn **một** model chính (trang Google AI Studio, hoặc ô Model ở trang Chuyển đổi); không còn
`model_google` / `model_go_chu` riêng cho từng cách như trước. Ràng buộc:

| Model chính | Dùng được | Bị khoá |
|---|---|---|
| `*-transcribe` (gemini-3.5-transcribe) | Gemini tự tách, Kết hợp | pyannote + prompt (model không nhận prompt / tệp kèm) |
| model đa năng (gemini-3.8-flash, 3.5-flash, 3.5-flash-lite…) | pyannote + prompt | Gemini tự tách, Kết hợp (tách giọng trên Google cần *-transcribe) |

Mục bị khoá có dấu `🔒` và không bấm được. Đổi model mà cách đang chọn không còn hợp thì app tự chuyển:
pyannote + prompt ↔ Kết hợp (cả hai đều dùng pyannote trên máy), Gemini tự tách → pyannote + prompt, kèm
thông báo. `config.txt` sửa tay mà không hợp thì bấm Bắt đầu sẽ báo lỗi ngay, trước khi xử lý âm thanh.

### Cài runtime pyannote (cách 1 và 3, chỉ một lần)

1. Tab Nhận diện người nói → **Cài đặt runtime** (hoặc `cai_dat.ps1 -ChiNguoiNoi`).
2. Đăng nhập huggingface.co, bấm **Đồng ý điều khoản model** (pyannote/speaker-diarization-community-1).
3. **Tạo token** loại Read, dán vào ô token → **Lưu token**. Token lưu trong
   `%LOCALAPPDATA%\Guzz\hf_token.txt`; chưa nhập thì dùng token của `hf auth login` nếu có.
4. **Kiểm tra môi trường**: lần đầu tải model về thư mục model (`HF_HOME`) của app.

### Các tuỳ chỉnh chính

- Thiết bị (tự động / CUDA / CPU), số người nói (chính xác, hoặc ít nhất – nhiều nhất), nhận diện trên
  âm thanh đã làm sạch hay tệp gốc, chỉ dùng model đã tải (máy không mạng).
- **Làm mượt** (như LecturerCleaner): quy tắc 1 (mảnh ngắn kẹp giữa cùng một người), quy tắc 2
  (người phụ nói quá ít quanh đó), chỉnh được từng ngưỡng; gộp các lượt cùng người.
- Tên: người nói chính (`Giảng viên`), tiền tố người khác (`Người hỏi 1, 2…`), hoặc đánh số tất cả.
- Định dạng: mốc thời gian, **mẫu đoạn văn** `[{moc}] {nguoi}: {noi_dung}` (có xem trước), độ dài
  đoạn văn, đánh dấu `[?]` chỗ nên nghe lại (cách kết hợp).
- Cách 1: gửi bản đồ dạng **tệp .txt thứ hai** hay **chèn vào prompt**, sửa prompt.

## 6. Hạn mức, khoá model và tự đổi model

Vì sao có phần này (nhật ký ngày 17/09): `gemini-3.5-transcribe` gói miễn phí chỉ cho **25 yêu cầu/ngày**
(lỗi 429 `generate_content_free_tier_requests, limit: 25`) nhưng app cũ tưởng là lỗi tạm thời nên cứ thử
lại; `gemini-3.8-flash` báo **HTTP 500 high demand** rồi **HTTP 400 Input blocked** (bộ lọc của Google chặn
nhầm) và app cũ coi 400 là lỗi cấu hình nên dừng cả hàng đợi.

Bây giờ mỗi loại lỗi được xử lý riêng:

| Lỗi | App làm gì |
|---|---|
| 429 hết hạn mức **theo ngày** | không thử lại; **khoá model tới lúc Google tính lại** (0h giờ Mỹ - Thái Bình Dương = 14h hè / 15h đông giờ Việt Nam), đổi model dự phòng |
| 429 hết hạn mức **theo phút** | chờ đúng thời gian Google yêu cầu rồi thử lại; vẫn lỗi thì khoá vài phút và đổi model (lặp lại nhiều lần thì coi là hết hạn mức ngày) |
| 5xx quá tải / high demand | thử lại `so_lan_thu_truoc_khi_doi` lần, rồi khoá model `phut_khoa_khi_qua_tai` phút và đổi model |
| 400 Input blocked (bộ lọc) | gửi **riêng đoạn đó** cho model dự phòng, không khoá model; mọi model đều chặn thì chỉ tệp đó lỗi |
| 404 model không tồn tại | khoá tới khi mở tay, đổi model |
| mọi model dùng được đều khoá | model mở sớm nhất trong `cho_toi_da_khi_het_model_phut` phút thì chờ, lâu hơn thì dừng hàng đợi và nói rõ model nào khoá tới mấy giờ |

App biết lỗi 429 là theo ngày hay theo phút nhờ `quotaId` Google gửi kèm; không có (Interactions API chỉ ghi
`limit: 25`) thì so với số yêu cầu app đã gửi trong 60 giây qua. Con số `limit` được **ghi nhớ** để lần sau
app đếm và **khoá model trước** khi bị 429.

**Model dự phòng** (trang Google AI Studio → thẻ **Tự đổi model**, hay `[DOI_MODEL]` trong config): danh sách
theo thứ tự ưu tiên. App tự bỏ model trùng model chính và model không hợp cách nhận diện đang bật (bật
pyannote + prompt thì chỉ lấy model đa năng…), dòng gợi ý ngay dưới ô cho biết thứ tự thật sẽ thử. Tắt
**Quay lại model chính** nếu muốn cả tệp giữ một model sau khi đã đổi. Đầu tệp (bật "phần đầu") và nhật ký ghi
rõ mỗi model gõ bao nhiêu đoạn.

**Tab Hạn mức & sử dụng**:
- *Bây giờ*: app đang chờ gì, còn bao lâu (đếm ngược từng giây): chờ hạn mức token/phút, chờ thử lại, hay
  chờ model mở khoá; thứ tự model sẽ thử; giờ Google tính lại hạn mức ngày.
- *Các model*: trạng thái (sẵn sàng / khoá tới mấy giờ, lý do), yêu cầu hôm nay / hạn mức ngày, token hôm nay,
  token 60 giây qua / hạn mức phút, số lỗi từng loại, lỗi gần nhất. Nút **Mở khoá**, **Quên hạn mức Google đã
  báo**, **Đặt lại bộ đếm hôm nay**.
- *Hạn mức từng model* (`[HAN_MUC]`): token/phút, yêu cầu/phút, yêu cầu/ngày; xem số thật của key ở
  ai.dev/rate-limit. Mặc định đã khai `gemini-3.5-transcribe = 10000, 0, 25`.
- *Lịch sử*: khoá, mở khoá, đổi model, lỗi (300 sự kiện gần nhất). Mọi thứ cũng nằm trong `logs\guzz.log`.

Số liệu lưu ở `su_dung.json` trong thư mục dùng chung (mục 8), nên khoá theo ngày vẫn còn khi mở lại app.
Guzz và GoogleAITranscribe **dùng chung tệp này**: hai app cùng một API key nên hạn mức Google là một —
model bị 429 ở app này thì app kia cũng tránh luôn, và số token hôm nay là tổng của cả hai. Mỗi lần ghi,
app giành khoá tệp (`su_dung.json.khoa`) rồi đọc lại trước khi sửa, nên chạy cả hai cùng lúc không mất số đếm.

## 7. Cài đặt tổng

| Nhóm | Mục |
|---|---|
| Giao diện | ngôn ngữ, chủ đề sáng/tối/theo Windows, màu nhấn, Mica (Windows 11), tỷ lệ hiển thị, cỡ chữ nhật ký, nhớ vị trí cửa sổ |
| Bản gõ chữ | thư mục lưu, **mẫu tên tệp** (`{ten}` `{ngay_ghi}` `{ngay}` `{gio}` `{model}`), .txt/.md, khi trùng tên (đánh số / ghi đè / bỏ qua), UTF-8 hoặc UTF-8 BOM (Notepad cũ của Windows 10), CRLF/LF, phần đầu tệp, dòng đánh dấu đoạn, lưu kèm bản đồ người nói, lưu kèm âm thanh đã làm sạch, mở tệp/thư mục khi xong |
| Hàng đợi | khi tệp lỗi, thông báo + âm báo khi xong, chống ngủ máy, nhớ thư mục chọn tệp, thư mục mở sẵn, lấy cả thư mục con, đuôi tệp âm thanh và đuôi tệp video được nhận |
| Hệ thống | thư mục tạm (+ dọn), xoá tạm khi xong, đường dẫn ffmpeg, mức nhật ký (DEBUG ghi cả yêu cầu gửi Google), dung lượng / số tệp nhật ký |
| Thông tin | phiên bản, thư mục dữ liệu, mở config.txt, khởi động lại, khôi phục cài đặt gốc |

Trang **Âm thanh, video & cắt đoạn** và **Google AI Studio** giữ nguyên như GoogleAITranscribe (preset
Ngồi gần giảng viên / Ngồi gần loa / Giảng viên đi lại / Tuỳ chỉnh; model, chế độ, ngôn ngữ, từ vựng,
prompt, hạn mức token/phút…; thêm thẻ Tự đổi model). Mọi thứ đều nằm trong `config.txt` có chú thích, sửa tay
cũng được.

Thẻ **Tệp video** (cuối trang Âm thanh, video & cắt đoạn) — mục `[XU_LY_VIDEO]` trong `config.txt`:

| Cài đặt | Nghĩa |
|---|---|
| Nhận cả tệp video | Tắt thì kéo thả video bị bỏ qua, chỉ nhận tệp âm thanh. |
| Rãnh tiếng sẽ dùng | Video hội thảo hay có nhiều rãnh (mic cài áo, mic phòng, tiếng máy quay). `auto` = rãnh đầu tiên, hoặc chọn Rãnh 1…8. Số ngoài khoảng thì lùi về rãnh đầu. |
| Tách tiếng ra tệp tạm trước khi xử lý | Nên bật: video nặng hàng GB, đọc thẳng thì mỗi bước lại giải mã lại cả luồng hình. Tắt thì đỡ tốn chỗ trong thư mục tạm nhưng chậm hơn. |
| Định dạng tệp tiếng tách ra | flac (mặc định) / wav / mp3. |
| Lưu kèm tệp tiếng tách từ video | Chép ra cạnh bản gõ chữ (`<tên>.am_thanh.flac`), nghe lại không cần mở cả video. |
| Video không có rãnh tiếng thì bỏ qua | Tắt thì những video đó bị báo lỗi thay vì bỏ qua. |

Đổi rãnh tiếng thì mã băm cache đổi theo, nên chạy lại sẽ cắt đoạn và gõ chữ lại từ đầu — không dùng nhầm
kết quả của rãnh cũ. Mã băm của **tệp âm thanh** không đổi, nên các tệp đang dở vẫn làm tiếp được.

## 8. Dữ liệu nằm ở đâu

- Có tệp `portable` cạnh code (thư mục đang phát triển): `data\` ngay trong thư mục app.
- Không có (bản cài đặt): `%LOCALAPPDATA%\Guzz\` — Program Files không ghi được.
- Biến môi trường `GUZZ_DATA_DIR` ghi đè cả hai (để chạy thử).

Trong đó: `config.txt`, `prompt.txt`, `prompt_nguoi_noi.txt`, `tmp\`, `hf\` (model pyannote),
`giao_dien.json` (vị trí cửa sổ, thư mục chọn tệp lần cuối). Lần đầu chạy, app chép
`config.mac_dinh.txt` và các prompt mẫu sang đây.

**Dùng chung với GoogleAITranscribe** — `%LOCALAPPDATA%\GoogleAI\` (biến môi trường
`GOOGLEAI_DIR_CHUNG` ghi đè):

| Tệp | Là gì |
|---|---|
| `su_dung.json` | Lượt dùng, hạn mức đã học, model đang khoá, lịch sử (mục 6). Cả hai app đọc/ghi. |
| `su_dung.json.khoa` | Tệp khoá, rỗng — để hai app không ghi đè nhau. |
| `logs\guzz.log` | Nhật ký Guzz. |
| `logs\google_ai_transcribe.log` | Nhật ký GoogleAITranscribe. |

Lần đầu chạy bản này, app tự dồn `su_dung.json` và thư mục `logs\` cũ của cả hai bên sang đây (cộng dồn
số đếm, giữ khoá đang có), rồi đổi tên tệp cũ thành `su_dung.json.da_gop`. Nên tắt cả hai app trước lần
chạy đầu tiên, để không bên nào còn giữ số cũ trong bộ nhớ.

## 9. Làm tiếp khi lỗi

Mỗi tệp có một thư mục tạm riêng. Tên các tệp trong đó có mã băm theo tham số, nên:
- đổi preset âm thanh (hoặc đổi rãnh tiếng của video) → xử lý âm thanh lại; không đổi → dùng lại các đoạn
  đã cắt;
- tiếng tách từ video (`am_thanh_video.flac`) còn trong thư mục tạm → không tách lại;
- kết quả pyannote còn → không chạy lại;
- đoạn đã gõ chữ xong với cùng cách nhận diện / prompt / bản đồ → không gửi lại, **kể cả khi đoạn đó do model
  dự phòng gõ** (đổi model chính rồi chạy tiếp cũng dùng lại).

Tệp xong thì xoá thư mục tạm (tắt được); lỗi giữa chừng thì luôn giữ.

## 10. Chạy tay không cần giao diện

```powershell
.\runtime\python\python.exe chuyen_doi.py "bai 1.m4a" "bai 2.mp4" --ra D:\Transcripts
.\runtime\python\python.exe xu_ly_am_thanh.py bai.m4a          # nghe thử bản làm sạch
.\runtime\python\python.exe xu_ly_am_thanh.py bai.mp4 --rung 1 # ... từ rãnh tiếng thứ hai của video
.\runtime\nguoi_noi\python.exe tach_nguoi_noi_worker.py --kiem-tra
```

## 11. Kiểm thử

```powershell
.\runtime\python\python.exe -m unittest discover -s tests
```

Có test cho: gọi Google (giả lập HTTP: tải lên 2 tệp, tách người nói, word_info, phân loại 429 ngày/phút,
500 high demand, 400 Input blocked, điều tiết token và yêu cầu/phút), sổ hạn mức (giờ Pacific, khoá, lưu
tệp), ràng buộc model ↔ cách nhận diện, tự đổi model (kể cả chạy lại đúng chuỗi lỗi trong nhật ký 17/09),
xử lý lượt nói / làm mượt / ghép từ, bản đồ thời gian, và cả luồng chuyển đổi trên âm thanh tổng hợp với 4
chế độ (cần ffmpeg).

`tests\test_video.py` dựng sẵn video thật bằng ffmpeg (hai rãnh tiếng khác tần số, và một video câm) để
kiểm tra: đọc danh sách rãnh, chọn rãnh, tách đúng rãnh, chạy cả luồng trên video, lưu kèm tiếng tách ra,
và video không có tiếng thì bỏ qua hay báo lỗi.

`TestDungChungVoiAppKia` trong `tests\test_han_muc.py` giữ ba điều app này phải luôn đúng khi chạy cùng
GoogleAITranscribe: app kia ghi thì bên này thấy ngay (kể cả khi đồng hồ của máy thô đến mức mã băm mtime
của tệp đứng yên), lúc cả hai đều rảnh thì không mở lại `su_dung.json` lần nào, và lúc chờ khoá tệp thì
luồng giao diện vẫn chạy chứ không đứng hình.

## 12. Chuẩn bị làm bản cài đặt

- Đóng gói: toàn bộ code + `runtime\` + `gui\assets\`. **Không** đóng gói `data\`, `portable`, `tests\`,
  `__pycache__\`.
- Shortcut trỏ tới `runtime\python\pythonw.exe` với tham số `"<app>\gui\main.py"`, thư mục làm việc là
  thư mục app, icon `gui\assets\icon.ico`. Có thể đăng ký "Open with" với `"%1"`.
- Runtime nhận diện người nói có thể là thành phần tuỳ chọn (vài GB). Muốn máy không mạng dùng được
  ngay: chép `data\hf` sang `runtime\hf` rồi đóng gói — app tự dùng `runtime\hf` nếu có.
- Python embeddable cần Universal CRT, có sẵn trên Windows 10.
