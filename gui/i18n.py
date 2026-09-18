"""
i18n.py
Bang dich VI/EN cho GUI (cach lam cua GoogleAITranscribe). Moi trang tu dang ky
ham doi chu cua minh vao bo_dich.doi_ngon_ngu de cap nhat lai khi doi ngon ngu,
khong can khoi dong lai.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

ngon_ngu_hien_tai = "vi"

_BANG = {
    "app_title": ("Guzz", "Guzz"),
    "lang_vi": ("Tiếng Việt", "Tiếng Việt"),
    "lang_en": ("English", "English"),

    "nav_convert": ("Chuyển đổi", "Convert"),
    "nav_audio": ("Âm thanh & cắt đoạn", "Audio & chunks"),
    "nav_google": ("Google AI Studio", "Google AI Studio"),
    "nav_speakers": ("Nhận diện người nói", "Speaker recognition"),
    "nav_usage": ("Hạn mức & sử dụng", "Quota & usage"),
    "nav_logs": ("Nhật ký", "Logs"),
    "nav_settings": ("Cài đặt", "Settings"),

    "common_save": ("Lưu", "Save"),
    "common_browse": ("Chọn...", "Browse..."),
    "common_saved": ("Đã lưu vào config.txt.", "Saved to config.txt."),
    "common_on": ("Bật", "On"),
    "common_off": ("Tắt", "Off"),
    "common_cancel": ("Huỷ", "Cancel"),
    "common_restore_default": ("Khôi phục mặc định", "Restore default"),

    # ------------------------------------------------------------ chuyen doi
    "conv_title": ("Chuyển đổi", "Convert"),
    "conv_subtitle": (
        "Chọn hoặc kéo thả tệp âm thanh, bấm Bắt đầu. Bản gõ chữ nằm cùng thư mục với tệp âm thanh "
        "nếu để trống ô Lưu vào.",
        "Pick or drop audio files and press Start. Transcripts are saved next to each audio file "
        "when Save to is empty.",
    ),
    "conv_files": ("Tệp âm thanh", "Audio files"),
    "conv_total": ("{0} tệp · {1}", "{0} files · {1}"),
    "conv_btn_add_files": ("Thêm tệp", "Add files"),
    "conv_btn_add_folder": ("Thêm thư mục", "Add folder"),
    "conv_btn_remove": ("Bỏ đã chọn", "Remove selected"),
    "conv_btn_clear_done": ("Dọn tệp đã xong", "Clear finished"),
    "conv_btn_clear_all": ("Xoá cả danh sách", "Clear the whole list"),
    "conv_drop_hint": ("Kéo thả tệp hoặc thư mục âm thanh vào đây, hoặc bấm Thêm tệp.",
                       "Drop audio files or folders here, or click Add files."),
    "conv_drop_formats": ("Định dạng nhận: {0}", "Accepted formats: {0}"),
    "conv_filter_audio": ("Âm thanh", "Audio"),
    "conv_filter_all": ("Tất cả tệp", "All files"),
    "conv_no_new_files": ("Không có tệp âm thanh mới nào (trùng danh sách hoặc sai định dạng).",
                          "No new audio files (already listed or unsupported format)."),
    "conv_col_file": ("Tệp", "File"),
    "conv_col_duration": ("Thời lượng", "Duration"),
    "conv_col_status": ("Trạng thái", "Status"),
    "conv_col_progress": ("Tiến độ", "Progress"),
    "conv_col_result": ("Bản gõ chữ", "Transcript"),
    "conv_save_to": ("Lưu vào", "Save to"),
    "conv_save_to_placeholder": ("Để trống = cùng thư mục với tệp âm thanh",
                                 "Empty = same folder as the audio file"),
    "conv_quick_denoise": ("Khử ồn", "Denoise"),
    "conv_quick_trim": ("Cắt khoảng lặng", "Trim silence"),
    "conv_quick_speakers": ("Nhận diện người nói", "Speaker recognition"),
    "conv_summary": ("Model: {0}  ·  Âm thanh: {1}  ·  Mỗi đoạn {2} phút",
                     "Model: {0}  ·  Audio: {1}  ·  {2} min per chunk"),
    "conv_summary_no_runtime": ("chưa cài runtime nhận diện người nói", "speaker runtime not installed"),
    "conv_btn_start": ("Bắt đầu", "Start"),
    "conv_btn_stop": ("Dừng", "Stop"),
    "conv_activity": ("Hoạt động", "Activity"),
    "conv_status_waiting": ("Đang chờ", "Waiting"),
    "conv_status_running": ("Đang chạy", "Running"),
    "conv_status_done": ("Xong", "Done"),
    "conv_status_skipped": ("Bỏ qua (đã có bản gõ chữ)", "Skipped (transcript exists)"),
    "conv_status_error": ("Lỗi", "Error"),
    "conv_status_stopped": ("Đã dừng — chạy lại sẽ làm tiếp", "Stopped — run again to resume"),
    "conv_stage_prepare": ("Chuẩn bị", "Preparing"),
    "conv_stage_clean": ("Làm sạch âm thanh ({0}/6)", "Cleaning audio ({0}/6)"),
    "conv_stage_clean_short": ("Làm sạch âm thanh", "Cleaning audio"),
    "conv_stage_diarize": ("Nhận diện người nói", "Recognising speakers"),
    "conv_stage_transcribe": ("Gõ chữ đoạn {0}/{1}", "Transcribing chunk {0}/{1}"),
    "conv_stage_transcribe_model": ("Gõ chữ đoạn {0}/{1} · {2}", "Transcribing chunk {0}/{1} · {2}"),
    "conv_model": ("Model", "Model"),
    "conv_summary_fallback": ("dự phòng: {0}", "fallback: {0}"),
    "conv_constraint": ("Không chạy được: {0}", "Cannot start: {0}"),
    "conv_all_locked": (
        "Mọi model dùng được đều đang khoá: {0}. Chọn model khác, thêm model dự phòng hoặc mở khoá ở trang "
        "Hạn mức & sử dụng.",
        "Every usable model is locked: {0}. Pick another model, add fallback models or unlock one on the "
        "Quota & usage page.",
    ),
    "conv_go_usage": ("Mở trang Hạn mức", "Open Quota page"),
    "conv_stage_merge": ("Ghép bản gõ chữ", "Merging transcript"),
    "diar_step_segmentation": ("phân đoạn", "segmentation"),
    "diar_step_speaker_counting": ("đếm người nói", "counting speakers"),
    "diar_step_embeddings": ("đặc trưng giọng", "voice embeddings"),
    "diar_step_discrete_diarization": ("gán nhãn", "labelling"),
    "conv_progress": ("Tệp {0}/{1}: {2} — {3} · {4}%", "File {0}/{1}: {2} — {3} · {4}%"),
    "conv_stopping": ("Đang dừng... (đợi bước hiện tại kết thúc)", "Stopping... (waiting for the current step)"),
    "conv_done_summary": ("Xong hàng đợi: {0} tệp thành công, {1} tệp lỗi.",
                          "Queue finished: {0} succeeded, {1} failed."),
    "conv_stopped_summary": ("Đã dừng: {0} tệp xong, {1} tệp lỗi. Bấm Bắt đầu để làm tiếp.",
                             "Stopped: {0} done, {1} failed. Press Start to resume."),
    "conv_nothing_to_do": ("Không có tệp nào đang chờ. Thêm tệp, hoặc chuột phải một tệp đã xong → Chạy lại.",
                           "Nothing is waiting. Add files, or right-click a finished file → Run again."),
    "conv_no_key": ("Chưa có API key của Google AI Studio.", "No Google AI Studio API key yet."),
    "conv_go_google": ("Nhập API key", "Enter API key"),
    "conv_no_runtime": ("Cách nhận diện người nói đang chọn cần runtime pyannote, nhưng chưa cài.",
                        "The selected speaker recognition method needs the pyannote runtime, which is not installed."),
    "conv_go_speakers": ("Mở trang Người nói", "Open Speakers page"),
    "conv_menu_open_result": ("Mở bản gõ chữ", "Open transcript"),
    "conv_menu_open_folder": ("Mở thư mục chứa", "Show in folder"),
    "conv_menu_play": ("Mở tệp âm thanh", "Open audio file"),
    "conv_menu_redo": ("Chạy lại", "Run again"),
    "conv_menu_remove": ("Bỏ khỏi danh sách", "Remove from list"),
    "notify_done": ("Xong: {0} tệp thành công, {1} tệp lỗi.", "Finished: {0} succeeded, {1} failed."),

    "close_title": ("Đang chuyển đổi", "Conversion in progress"),
    "close_body": (
        "Thoát bây giờ sẽ dừng tệp đang làm. Các đoạn đã gõ chữ xong vẫn được giữ, lần sau chạy lại sẽ làm tiếp. "
        "Thoát?",
        "Quitting now stops the current file. Finished chunks are kept and the next run resumes. Quit?",
    ),
    "close_yes": ("Dừng và thoát", "Stop and quit"),
    "restart_busy": ("Đang chuyển đổi, dừng trước rồi hãy khởi động lại.",
                     "A conversion is running; stop it before restarting."),

    # ------------------------------------------------------------ am thanh (GoogleAITranscribe)
    "audio_title": ("Âm thanh & cắt đoạn", "Audio & chunks"),
    "audio_clean_section": ("Làm sạch trước khi gửi đi", "Clean up before uploading"),
    "audio_denoise": ("Khử ồn (lọc dải tần + giảm tiếng ồn nền)", "Noise reduction (band-pass + denoise)"),
    "audio_trim": ("Cắt các khoảng lặng dài", "Trim long silences"),
    "audio_trim_hint": (
        "Cắt khoảng lặng giúp tải lên ít hơn và gõ chữ nhanh hơn. Mốc thời gian trong bản gõ chữ vẫn tính "
        "theo tệp gốc.",
        "Trimming silence means less to upload and faster transcription. Timestamps in the transcript still "
        "refer to the original file.",
    ),
    "audio_preset_near_lecturer": ("Ngồi gần giảng viên", "Near the lecturer"),
    "audio_preset_near_speaker": ("Ngồi gần loa (rè)", "Near a speaker (buzzy)"),
    "audio_preset_moving": ("Giảng viên đi lại", "Lecturer moves around"),
    "audio_preset_custom": ("Tuỳ chỉnh", "Custom"),
    "audio_preset_hint": (
        "Bộ tham số dựng sẵn giống GoogleAITranscribe / LecturerCleaner. Tắt \"Xoá thư mục tạm\" trong Cài đặt "
        "để nghe lại các đoạn đã làm sạch rồi chỉnh nếu cần.",
        "Same presets as GoogleAITranscribe / LecturerCleaner. Turn off \"Delete temp folder\" in Settings to "
        "listen to the cleaned chunks and fine-tune.",
    ),
    "audio_advanced": ("Thông số chi tiết", "Advanced parameters"),
    "audio_target_dbfs": ("Âm lượng mục tiêu (dBFS)", "Target loudness (dBFS)"),
    "audio_silence_offset": ("Ngưỡng im lặng (offset dB)", "Silence threshold offset (dB)"),
    "audio_min_silence": ("Đoạn lặng tối thiểu (ms)", "Minimum silence length (ms)"),
    "audio_keep_silence": ("Đệm giữ lại quanh câu (ms)", "Keep-silence padding (ms)"),
    "audio_noise_sample": ("Cửa sổ ước lượng tiếng ồn (giây)", "Noise estimation window (s)"),
    "audio_bandpass_low": ("Bandpass — ngưỡng dưới (Hz)", "Bandpass — low cutoff (Hz)"),
    "audio_bandpass_high": ("Bandpass — ngưỡng trên (Hz)", "Bandpass — high cutoff (Hz)"),
    "audio_prop_decrease": ("Tỷ lệ giảm ồn (0-1)", "Noise reduction ratio (0-1)"),
    "audio_level_window": ("Cân bằng âm lượng theo thời gian (giây, 0 = tắt)",
                           "Loudness leveling window (s, 0 = off)"),
    "audio_resample": ("Tần số lấy mẫu (Hz)", "Sample rate (Hz)"),
    "audio_chunk_section": ("Cắt đoạn", "Chunking"),
    "audio_chunk_minutes": ("Mỗi đoạn dài (phút)", "Minutes per chunk"),
    "audio_chunk_search": ("Tìm chỗ lặng quanh mốc cắt (± giây)", "Look for a pause around the cut (± s)"),
    "audio_chunk_last_min": ("Đoạn cuối ngắn hơn (giây) thì gộp vào đoạn trước",
                             "Merge a last chunk shorter than (s)"),
    "audio_chunk_format": ("Định dạng tệp đoạn", "Chunk file format"),
    "audio_chunk_hint": (
        "Không cắt đúng phút thứ 10 mà cắt ở chỗ lặng nhất gần đó, để không cắt ngang một từ. "
        "Nhận diện người nói bằng model *-transcribe: tối đa 30 phút mỗi đoạn.",
        "Chunks are cut at the quietest point near each mark so no word is split. "
        "Speaker recognition with *-transcribe models allows at most 30 minutes per chunk.",
    ),

    # ------------------------------------------------------------ google
    "google_title": ("Google AI Studio", "Google AI Studio"),
    "google_key_section": ("API key", "API key"),
    "google_key_hint": (
        "Key được lưu riêng trong hồ sơ Windows của bạn ({0}), không nằm trong config.txt. Chưa nhập thì app "
        "dùng lại key của GoogleAITranscribe nếu có.",
        "The key is stored in your Windows profile ({0}), not in config.txt. Without one, the app reuses "
        "GoogleAITranscribe's key if present.",
    ),
    "google_key_placeholder": ("Dán API key vào đây", "Paste your API key here"),
    "google_link_get_key": ("Lấy API key", "Get an API key"),
    "google_key_status_none": ("Chưa có API key.", "No API key yet."),
    "google_key_status_file": ("Đang dùng key {0} (đã lưu trong app).", "Using key {0} (saved by the app)."),
    "google_key_status_gait": ("Đang dùng key {0} của GoogleAITranscribe.", "Using GoogleAITranscribe's key {0}."),
    "google_key_status_env": ("Đang dùng key {0} từ biến môi trường {1}.",
                              "Using key {0} from the {1} environment variable."),
    "google_btn_save_key": ("Lưu key", "Save key"),
    "google_btn_delete_key": ("Xoá key đã lưu", "Delete saved key"),
    "google_btn_check": ("Kiểm tra kết nối", "Test connection"),
    "google_key_saved": ("Đã lưu API key.", "API key saved."),
    "google_key_deleted": ("Đã xoá API key đã lưu.", "Saved API key deleted."),
    "google_checking": ("Đang kiểm tra...", "Checking..."),
    "google_check_ok": ("Kết nối được. Key này dùng được {0} model.", "Connected. This key can use {0} models."),
    "google_check_model_missing": (
        "Kết nối được, nhưng không thấy model \"{0}\" trong danh sách của key này.",
        "Connected, but model \"{0}\" is not in this key's model list.",
    ),
    "google_check_fail": ("Không kết nối được", "Connection failed"),
    "google_model_section": ("Model", "Model"),
    "google_model": ("Model", "Model"),
    "google_model_hint": (
        "gemini-3.5-transcribe là model chuyên gõ chữ (chỉ nhận âm thanh, không cần prompt). Model khác như "
        "gemini-3.8-flash dùng prompt ở dưới. Bấm \"Kiểm tra kết nối\" để nạp danh sách model key của bạn dùng được.",
        "gemini-3.5-transcribe is a dedicated speech-to-text model (audio only, no prompt). Other models such as "
        "gemini-3.8-flash use the prompt below. Click \"Test connection\" to load the models your key can use.",
    ),
    "google_model_locked": (
        "Model {0} đang {1}. Chọn model khác hoặc mở khoá ở trang Hạn mức & sử dụng.",
        "Model {0} is {1}. Pick another model or unlock it on the Quota & usage page.",
    ),
    "google_model_locked_note": ("⚠ Model này đang {0}.", "⚠ This model is {0}."),
    "google_fallback_section": ("Tự đổi model", "Automatic model switching"),
    "google_fallback_hint": (
        "Model đang dùng hết hạn mức (429), quá tải (\"high demand\"), bị bộ lọc của Google chặn (\"Input "
        "blocked\") hay không tồn tại thì app gửi đoạn đó cho model dự phòng, không báo lỗi cả tệp. Model hết hạn "
        "mức ngày bị khoá tới lúc Google tính lại và không chọn được cho tới lúc đó.",
        "When the current model runs out of quota (429), is overloaded (\"high demand\"), gets blocked by Google's "
        "filters (\"Input blocked\") or doesn't exist, the app sends that chunk to a fallback model instead of "
        "failing the whole file. A model out of daily quota is locked (not selectable) until Google resets it.",
    ),
    "google_fallback_enable": ("Tự đổi sang model dự phòng", "Switch to fallback models automatically"),
    "google_fallback_models": ("Model dự phòng (theo thứ tự, cách nhau dấu phẩy)",
                               "Fallback models (in order, comma-separated)"),
    "google_fallback_chain": ("Với cách nhận diện đang chọn, app thử lần lượt: {0}",
                              "With the current speaker setting the app tries, in order: {0}"),
    "google_fallback_skipped": ("Bỏ qua vì không hợp cách nhận diện: {0}", "Skipped as incompatible: {0}"),
    "google_fallback_retries": ("Quá tải / 429 theo phút: thử lại mấy lần rồi mới đổi model",
                                "Overload / per-minute 429: attempts before switching"),
    "google_fallback_overload_lock": ("Khoá model quá tải trong (phút, 0 = không khoá)",
                                      "Lock an overloaded model for (min, 0 = don't lock)"),
    "google_fallback_return": ("Model chính hết khoá thì quay lại model chính", "Return to the main model once unlocked"),
    "google_fallback_return_hint": (
        "Tắt: đã đổi sang model dự phòng thì dùng nó tới hết tệp (văn phong đồng đều hơn).",
        "Off: once switched, keep the fallback model until the end of the file (more consistent style).",
    ),
    "google_fallback_wait_switch": ("Đổi model khi phải chờ hạn mức token/phút lâu hơn (giây, 0 = luôn chờ)",
                                    "Switch when the per-minute wait is longer than (s, 0 = always wait)"),
    "google_fallback_max_wait": ("Mọi model đều khoá: chờ tối đa (phút), lâu hơn thì dừng hàng đợi",
                                 "All models locked: wait at most (min), longer stops the queue"),
    "google_fallback_proactive": ("Khoá model khi đã gửi đủ số yêu cầu/ngày (không đợi Google báo 429)",
                                  "Lock a model once its daily request count is reached (don't wait for 429)"),
    "rb_transcribe": (
        "Model *-transcribe: nhận diện người nói dùng được Gemini tự tách hoặc Kết hợp. Khoá pyannote + prompt "
        "(model này không nhận prompt hay tệp kèm).",
        "*-transcribe model: speaker recognition can use Gemini native or Hybrid. pyannote + prompt is locked "
        "(this model takes no prompt or attachments).",
    ),
    "rb_general": (
        "Model đa năng: nhận diện người nói chỉ dùng được pyannote + prompt. Khoá Gemini tự tách và Kết hợp "
        "(tách giọng trên Google cần model *-transcribe).",
        "General model: speaker recognition can only use pyannote + prompt. Gemini native and Hybrid are locked "
        "(cloud speaker separation needs a *-transcribe model).",
    ),
    "rb_auto_switched": (
        "Model {0} không đi được với cách \"{1}\" nên cách nhận diện người nói đã chuyển sang \"{2}\".",
        "Model {0} doesn't work with \"{1}\", so speaker recognition was switched to \"{2}\".",
    ),
    "model_kind_transcribe": ("*-transcribe", "*-transcribe"),
    "model_kind_general": ("đa năng", "general"),
    "model_locked_until": ("khoá tới {0} (còn {1}) — {2}", "locked until {0} ({1} left) — {2}"),
    "model_locked_manual": ("khoá tới khi mở tay — {0}", "locked until unlocked manually — {0}"),
    "model_locked_short": ("khoá", "locked"),
    "google_mode": ("Chế độ gõ chữ (model *-transcribe)", "Transcription mode (*-transcribe models)"),
    "google_mode_smart": ("smart — bỏ từ đệm, tự đặt dấu câu", "smart — drop fillers, punctuate"),
    "google_mode_verbatim": ("verbatim — giữ nguyên từng từ", "verbatim — every word as spoken"),
    "google_language": ("Mã ngôn ngữ (để trống = tự nhận diện)", "Language codes (empty = auto-detect)"),
    "google_vocabulary": ("Từ chuyên ngành, cách nhau dấu phẩy", "Domain terms, comma-separated"),
    "google_prompt_section": ("Prompt (tắt nhận diện người nói, model đa năng — kể cả model dự phòng)",
                              "Prompt (speaker recognition off, general models — fallbacks included)"),
    "google_request_section": ("Gửi yêu cầu", "Requests"),
    "google_store": ("Cho phép Google lưu lại cuộc trao đổi", "Allow Google to store the interaction"),
    "google_delete_remote": ("Xoá tệp trên Google ngay sau khi xong đoạn", "Delete uploaded files right after each chunk"),
    "google_timeout": ("Chờ tối đa mỗi đoạn (giây)", "Timeout per chunk (s)"),
    "google_retries": ("Số lần thử khi lỗi tạm thời", "Attempts on temporary errors"),
    "google_token_limit": ("Hạn mức token mỗi phút cho model chưa khai báo (0 = không giới hạn)",
                           "Tokens per minute for undeclared models (0 = no limit)"),
    "google_token_limit_hint": (
        "App tự giãn nhịp gửi các đoạn để không vượt hạn mức và không bị lỗi 429. Hạn mức riêng từng model "
        "(token/phút, yêu cầu/phút, yêu cầu/ngày) khai báo ở trang Hạn mức & sử dụng; model chưa khai báo dùng số "
        "này. Đã bật thanh toán thì tăng theo hạn mức thật (ai.dev/rate-limit).",
        "The app spaces out chunk uploads to stay under quota and avoid 429 errors. Per-model limits (tokens/min, "
        "requests/min, requests/day) are set on the Quota & usage page; undeclared models use this number. With "
        "billing enabled, raise it to your real limit (ai.dev/rate-limit).",
    ),

    # ------------------------------------------------------------ nguoi noi
    "nn_title": ("Nhận diện người nói", "Speaker recognition"),
    "nn_section_mode": ("Bật & cách nhận diện", "Enable & method"),
    "nn_enable": ("Ghi rõ ai nói đoạn nào trong bản gõ chữ", "Label who says what in the transcript"),
    "nn_enable_hint": ("Cũng bật / tắt được ngay ở trang Chuyển đổi.", "Can also be toggled on the Convert page."),
    "nn_mode_pyannote": ("pyannote + prompt", "pyannote + prompt"),
    "nn_mode_gemini": ("Gemini tự tách", "Gemini native"),
    "nn_mode_hybrid": ("Kết hợp", "Hybrid"),
    "nn_mode_pyannote_desc": (
        "pyannote chạy trên máy lập bản đồ người nói cho cả buổi. Mỗi đoạn gửi cho model đa năng (vd gemini-3.8-flash) "
        "hai tệp: âm thanh và bản đồ người nói, kèm prompt yêu cầu ghi tên người nói. Tên thống nhất từ đầu đến cuối "
        "buổi, dùng được từ vựng chuyên ngành. Cần runtime pyannote (torch).",
        "pyannote runs locally and maps speakers for the whole session. Each chunk is sent to a general model "
        "(e.g. gemini-3.8-flash) as two files — audio and the speaker map — with a prompt asking for speaker labels. "
        "Names stay consistent across the session and domain terms still work. Needs the pyannote runtime (torch).",
    ),
    "nn_mode_gemini_desc": (
        "gemini-3.5-transcribe tự tách người nói, không cần cài gì thêm. Hạn chế theo tài liệu Google: nhãn người nói "
        "chỉ đúng trong từng đoạn (app gọi người nói lâu nhất mỗi đoạn là giảng viên, người khác đánh số lại mỗi đoạn), "
        "từ 3 người trở lên còn là thử nghiệm, bắt buộc verbatim, không dùng được từ vựng chuyên ngành.",
        "gemini-3.5-transcribe separates speakers on its own, nothing to install. Limits per Google's docs: speaker "
        "labels only hold within a chunk (the app calls the longest speaker of each chunk the lecturer and renumbers "
        "others per chunk), 3+ speakers is experimental, verbatim only, no custom vocabulary.",
    ),
    "nn_mode_hybrid_desc": (
        "gemini-3.5-transcribe trả mốc thời gian từng từ, pyannote cho lượt nói cả buổi, app ghép hai thứ trên máy "
        "bằng thuật toán của LecturerCleaner. Tên thống nhất cả buổi, chính xác tới từng từ; bắt buộc verbatim và "
        "không dùng được từ vựng chuyên ngành. Cần runtime pyannote.",
        "gemini-3.5-transcribe returns per-word timestamps, pyannote provides session-wide speaker turns, and the app "
        "merges them locally with LecturerCleaner's algorithm. Consistent names, word-level precision; verbatim only, "
        "no custom vocabulary. Needs the pyannote runtime.",
    ),
    "nn_req_gemini": ("Sẵn sàng — không cần runtime. Model: {0}", "Ready — no runtime needed. Model: {0}"),
    "nn_req_ready": ("Sẵn sàng. Model Google: {0}", "Ready. Google model: {0}"),
    "nn_req_missing": ("Chưa sẵn sàng: xem mục Môi trường pyannote bên dưới. Model Google: {0}",
                       "Not ready: see the pyannote environment section below. Google model: {0}"),
    "nn_section_env": ("Môi trường pyannote", "pyannote environment"),
    "nn_env_hint": (
        "pyannote cần torch (vài GB) nên chạy trong runtime riêng runtime\\nguoi_noi, không cài vào Python của app. "
        "Lần đầu dùng: bấm Cài đặt runtime, đồng ý điều khoản model trên Hugging Face, dán token rồi bấm Kiểm tra.",
        "pyannote needs torch (several GB), so it runs in its own runtime\\nguoi_noi, separate from the app's Python. "
        "First time: click Install runtime, accept the model terms on Hugging Face, paste a token, then click Check.",
    ),
    "nn_env_python": ("Python runtime: {0}", "Runtime Python: {0}"),
    "nn_env_token": ("Token Hugging Face", "Hugging Face token"),
    "nn_env_model": ("Model đã tải về {0}", "Model downloaded to {0}"),
    "nn_btn_check": ("Kiểm tra môi trường", "Check environment"),
    "nn_btn_install": ("Cài đặt runtime", "Install runtime"),
    "nn_btn_open_models": ("Mở thư mục model", "Open model folder"),
    "nn_checking": ("Đang nạp model (lần đầu có thể phải tải về, vài phút)...",
                    "Loading the model (first time may download it, a few minutes)..."),
    "nn_check_ok": ("Sẵn sàng: thiết bị {0} ({1}), torch {2}, pyannote {3}.",
                    "Ready: device {0} ({1}), torch {2}, pyannote {3}."),
    "nn_check_ok_short": ("Môi trường nhận diện người nói sẵn sàng.", "Speaker recognition environment is ready."),
    "nn_check_fail": ("Môi trường chưa sẵn sàng", "Environment not ready"),
    "nn_install_title": ("Cài runtime nhận diện người nói", "Install the speaker recognition runtime"),
    "nn_install_body": (
        "Một cửa sổ PowerShell sẽ tải Python embeddable, torch và pyannote.audio vào runtime\\nguoi_noi (khoảng "
        "3-5 GB với bản GPU). Máy không có GPU NVIDIA sẽ tự cài bản CPU. App vẫn dùng được trong lúc cài.",
        "A PowerShell window will download embeddable Python, torch and pyannote.audio into runtime\\nguoi_noi "
        "(about 3-5 GB for the GPU build). Machines without an NVIDIA GPU get the CPU build. The app stays usable.",
    ),
    "nn_install_yes": ("Cài đặt", "Install"),
    "nn_install_started": ("Đã mở cửa sổ cài đặt. Cài xong bấm Kiểm tra môi trường.",
                           "Installer window opened. When it finishes, click Check environment."),
    "nn_token_section": ("Token Hugging Face", "Hugging Face token"),
    "nn_token_hint": (
        "Model pyannote cần token loại Read và bạn phải bấm đồng ý điều khoản trên trang model. Token lưu riêng trong "
        "hồ sơ Windows ({0}); chưa nhập thì app dùng token của \"hf auth login\" nếu có.",
        "pyannote models need a Read token and you must accept the terms on the model page. The token is stored in "
        "your Windows profile ({0}); without one the app uses the \"hf auth login\" token if present.",
    ),
    "nn_token_placeholder": ("Dán token hf_... vào đây", "Paste your hf_... token here"),
    "nn_btn_save_token": ("Lưu token", "Save token"),
    "nn_btn_delete_token": ("Xoá token", "Delete token"),
    "nn_token_saved": ("Đã lưu token.", "Token saved."),
    "nn_token_status_none": ("Chưa có token.", "No token yet."),
    "nn_token_status_file": ("Đang dùng token đã lưu trong app.", "Using the token saved by the app."),
    "nn_token_status_other": ("Đang dùng token từ {0}.", "Using the token from {0}."),
    "nn_link_accept_terms": ("Đồng ý điều khoản model", "Accept model terms"),
    "nn_link_create_token": ("Tạo token", "Create token"),
    "nn_python": ("Python của runtime", "Runtime Python"),
    "nn_auto": ("tự động", "automatic"),
    "nn_auto_path": ("tự động: {0}", "automatic: {0}"),
    "nn_pyannote_model": ("Model pyannote", "pyannote model"),
    "nn_model_dir": ("Thư mục lưu model (HF_HOME)", "Model folder (HF_HOME)"),
    "nn_offline": ("Chỉ dùng model đã tải (không kết nối Hugging Face)", "Use downloaded model only (offline)"),
    "nn_offline_hint": ("Bật khi máy không có mạng; model phải được tải về trước.",
                        "Turn on for offline machines; the model must be downloaded first."),
    "nn_device": ("Thiết bị", "Device"),
    "nn_device_auto": ("Tự động (GPU nếu có)", "Automatic (GPU if available)"),
    "nn_device_cuda": ("GPU NVIDIA (CUDA)", "NVIDIA GPU (CUDA)"),
    "nn_device_cpu": ("CPU (chậm hơn nhiều)", "CPU (much slower)"),
    "nn_num_speakers": ("Số người nói chính xác (0 = tự đoán)", "Exact number of speakers (0 = guess)"),
    "nn_min_speakers": ("Ít nhất (0 = không giới hạn)", "At least (0 = no limit)"),
    "nn_max_speakers": ("Nhiều nhất (0 = không giới hạn)", "At most (0 = no limit)"),
    "nn_run_on": ("Nhận diện trên", "Run recognition on"),
    "nn_run_on_clean": ("Âm thanh đã làm sạch", "Cleaned audio"),
    "nn_run_on_original": ("Tệp gốc (giọng ít bị méo hơn)", "Original file (less voice distortion)"),
    "nn_timeout": ("Chờ tối đa mỗi tệp (phút)", "Timeout per file (min)"),
    "nn_section_smooth": ("Làm mượt & gộp lượt nói", "Smoothing & turn merging"),
    "nn_smooth": ("Làm mượt (như LecturerCleaner)", "Smoothing (as in LecturerCleaner)"),
    "nn_smooth_hint": (
        "pyannote hay tách giọng giảng viên thành hai \"người\" (lúc gần / xa micro). Quy tắc 1 trả mảnh ngắn kẹp "
        "giữa cùng một người về người đó; quy tắc 2 trả lượt của người phụ nói quá ít quanh đó về người nói chính. "
        "Đổi lại, một câu hỏi rất ngắn đứng lẻ loi có thể bị gộp vào giảng viên — tắt nếu thấy mất câu hỏi.",
        "pyannote often splits the lecturer into two \"people\" (near / far from the mic). Rule 1 gives short pieces "
        "sandwiched by the same speaker back to them; rule 2 gives turns of secondary speakers who say too little "
        "nearby back to the main speaker. A very short isolated question may be merged into the lecturer — turn off "
        "if questions go missing.",
    ),
    "nn_sandwich_max": ("Quy tắc 1: mảnh kẹp ngắn hơn (giây)", "Rule 1: sandwiched piece shorter than (s)"),
    "nn_sandwich_gap": ("Quy tắc 1: khoảng nghỉ hai bên tối đa (giây)", "Rule 1: max gap on each side (s)"),
    "nn_density_window": ("Quy tắc 2: cửa sổ ± (giây)", "Rule 2: window ± (s)"),
    "nn_density_min": ("Quy tắc 2: người phụ nói ít hơn (giây, 0 = tắt)", "Rule 2: secondary speech under (s, 0 = off)"),
    "nn_merge_turns": ("Gộp hai lượt cùng người cách nhau tối đa (giây)", "Merge same-speaker turns closer than (s)"),
    "nn_section_names": ("Tên người nói", "Speaker names"),
    "nn_name_main": ("Gọi người nói lâu nhất bằng tên riêng", "Give the longest speaker a special name"),
    "nn_name_main_hint": ("Tắt: mọi người đánh số theo thứ tự xuất hiện.", "Off: everyone is numbered by first appearance."),
    "nn_main_label": ("Tên người nói chính", "Main speaker name"),
    "nn_other_label": ("Tiền tố người khác", "Prefix for others"),
    "nn_generic_label": ("Tiền tố khi không đặt tên riêng", "Prefix when no special name"),
    "nn_names_preview": ("Ví dụ: {0}", "Example: {0}"),
    "nn_section_output": ("Gửi cho Google & định dạng", "Sending to Google & formatting"),
    "nn_send_map": ("Gửi bản đồ người nói", "Send the speaker map"),
    "nn_send_map_file": ("Tệp .txt thứ hai kèm âm thanh", "As a second .txt file"),
    "nn_send_map_inline": ("Chèn thẳng vào cuối prompt", "Inline at the end of the prompt"),
    "nn_timestamps": ("Mốc thời gian đầu mỗi đoạn văn", "Timestamp at the start of each paragraph"),
    "nn_timestamps_hint": ("Mốc tính theo tệp âm thanh gốc (kể cả khi đã cắt khoảng lặng).",
                           "Times refer to the original audio file (even after silence trimming)."),
    "nn_paragraph_template": ("Mẫu đoạn văn ({moc} {nguoi} {noi_dung})", "Paragraph template ({moc} {nguoi} {noi_dung})"),
    "nn_template_sample": ("Hôm nay chúng ta học về cây quyết định.", "Today we'll look at decision trees."),
    "nn_template_preview": ("Xem trước: {0}", "Preview: {0}"),
    "nn_template_invalid": ("Mẫu không hợp lệ: chỉ dùng {moc}, {nguoi}, {noi_dung}.",
                            "Invalid template: only {moc}, {nguoi}, {noi_dung} are allowed."),
    "nn_para_max": ("Đoạn văn dài tối đa (giây, 0 = không giới hạn)", "Max paragraph length (s, 0 = unlimited)"),
    "nn_para_gap": ("Ngắt đoạn khi im lặng quá (giây)", "Break paragraph after a pause of (s)"),
    "nn_review_marks": ("Đánh dấu [?] chỗ nên nghe lại", "Mark [?] where you should re-listen"),
    "nn_review_marks_hint": ("Đoạn dài mà người thứ hai cũng nói nhiều trong đó.",
                             "Long paragraphs where a second speaker also talks a lot."),
    "nn_transcribe_limits": (
        "Model *-transcribe khi tách người nói / cho mốc từng từ: tự chuyển sang verbatim, bỏ qua từ vựng chuyên ngành, "
        "tối đa 30 phút mỗi đoạn.",
        "*-transcribe models with diarization / word timestamps: forced verbatim, custom vocabulary ignored, "
        "at most 30 minutes per chunk.",
    ),
    "nn_prompt_section": ("Prompt khi nhận diện bằng pyannote", "Prompt for the pyannote method"),
    "nn_prompt_hint": (
        "{danh_sach_nguoi_noi} được thay bằng tên những người nói trong đoạn. Hướng dẫn ghi mốc thời gian được app "
        "tự thêm khi bật Mốc thời gian.",
        "{danh_sach_nguoi_noi} is replaced with the speakers in the chunk. The timestamp instruction is appended "
        "automatically when Timestamps is on.",
    ),
    "nn_current_model": ("Model đang chọn: {0} ({1}) · dự phòng hợp lệ: {2}",
                         "Selected model: {0} ({1}) · usable fallbacks: {2}"),
    "nn_no_fallback": ("không có", "none"),
    "nn_btn_change_model": ("Đổi model", "Change model"),
    "nn_modes_locked": ("Đang khoá: {0}. {1}", "Locked: {0}. {1}"),
    "nn_mode_forced": (
        "config.txt đang chọn \"{0}\" nhưng cách này không đi được với model {1}; tạm chọn \"{2}\". Bấm Lưu để ghi.",
        "config.txt selects \"{0}\", which doesn't work with model {1}; \"{2}\" is selected for now. Press Save.",
    ),

    # ------------------------------------------------------------ han muc
    "use_title": ("Hạn mức & sử dụng", "Quota & usage"),
    "use_subtitle": (
        "Số yêu cầu, token, lỗi và các model đang bị khoá. Model bị khoá không chọn được ở các ô chọn model cho tới "
        "khi hết khoá (hoặc bấm Mở khoá). Số liệu này dùng chung với GoogleAITranscribe: hai app cùng một API key "
        "nên hạn mức Google là một. Mọi sự kiện ở đây cũng được ghi vào nhật ký (logs\\guzz.log).",
        "Requests, tokens, errors and locked models. A locked model can't be selected until the lock ends (or you "
        "press Unlock). These numbers are shared with GoogleAITranscribe: both apps use the same API key, so Google "
        "counts one quota. Every event here is also written to the log (logs\\guzz.log).",
    ),
    "use_section_now": ("Bây giờ", "Right now"),
    "use_wait_none": ("Không chờ gì.", "Not waiting for anything."),
    "use_wait_tpm": ("⏳ Chờ {0} cho khỏi vượt hạn mức {1} token/phút của {2}",
                     "⏳ Waiting {0} to stay under {2}'s {1} tokens/min"),
    "use_wait_rpm": ("⏳ Chờ {0} cho khỏi vượt hạn mức {1} yêu cầu/phút của {2}",
                     "⏳ Waiting {0} to stay under {2}'s {1} requests/min"),
    "use_wait_retry": ("⏳ Chờ {0} rồi thử lại {1} (lỗi {2})", "⏳ Waiting {0} before retrying {1} ({2} error)"),
    "use_wait_all_locked": ("⏳ Mọi model dùng được đều khoá, chờ {0} (tới {1}): {2}",
                            "⏳ Every usable model is locked, waiting {0} (until {1}): {2}"),
    "use_reset": ("Hạn mức theo ngày của Google tính lại lúc {0} (giờ máy), còn {1}.",
                  "Google's daily quotas reset at {0} (local time), in {1}."),
    "use_chain": ("Thứ tự model sẽ thử: {0}", "Model order: {0}"),
    "use_section_models": ("Các model", "Models"),
    "use_col_model": ("Model", "Model"),
    "use_col_status": ("Trạng thái", "Status"),
    "use_col_today": ("Yêu cầu hôm nay", "Requests today"),
    "use_col_tokens_today": ("Token hôm nay", "Tokens today"),
    "use_col_minute": ("Token 60 giây qua", "Tokens last 60 s"),
    "use_col_errors": ("Lỗi", "Errors"),
    "use_col_last_error": ("Lỗi gần nhất", "Last error"),
    "use_status_ok": ("Sẵn sàng", "Ready"),
    "use_status_locked": ("Khoá tới {0} (còn {1}) — {2}", "Locked until {0} ({1} left) — {2}"),
    "use_status_locked_manual": ("Khoá tới khi mở tay — {0}", "Locked until unlocked — {0}"),
    "use_btn_unlock": ("Mở khoá", "Unlock"),
    "use_btn_forget": ("Quên hạn mức Google đã báo", "Forget limits reported by Google"),
    "use_btn_reset_counts": ("Đặt lại bộ đếm hôm nay", "Reset today's counters"),
    "use_btn_open_log": ("Mở nhật ký", "Open logs"),
    "use_select_model": ("Chọn một dòng model trước.", "Select a model row first."),
    "use_unlocked": ("Đã mở khoá {0}.", "Unlocked {0}."),
    "use_section_limits": ("Hạn mức từng model", "Per-model limits"),
    "use_limits_hint": (
        "Hạn mức thật của API key xem ở ai.dev/rate-limit. 0 = không giới hạn (trừ khi Google đã báo một con số). "
        "App giãn nhịp theo token/phút và yêu cầu/phút, đếm yêu cầu/ngày để khoá model trước khi bị 429. Model không "
        "có dòng nào dùng hạn mức token/phút ở trang Google AI Studio.",
        "See your key's real limits at ai.dev/rate-limit. 0 = no limit (unless Google already reported one). The app "
        "paces by tokens/min and requests/min and counts requests/day to lock a model before a 429. Models without "
        "a row use the tokens/min limit on the Google AI Studio page.",
    ),
    "use_col_tpm": ("Token/phút", "Tokens/min"),
    "use_col_rpm": ("Yêu cầu/phút", "Requests/min"),
    "use_col_rpd": ("Yêu cầu/ngày", "Requests/day"),
    "use_col_learned": ("Google đã báo", "Reported by Google"),
    "use_not_declared": ("(chưa khai báo)", "(not declared)"),
    "use_add_model_placeholder": ("Tên model, vd gemini-3.5-flash", "Model name, e.g. gemini-3.5-flash"),
    "use_btn_add": ("Thêm dòng", "Add row"),
    "use_btn_remove_row": ("Bỏ khai báo", "Remove declaration"),
    "use_section_events": ("Lịch sử khoá, đổi model và lỗi", "Lock, switch and error history"),
    "use_btn_clear_events": ("Xoá lịch sử", "Clear history"),
    "use_col_time": ("Lúc", "Time"),
    "use_col_event": ("Sự kiện", "Event"),
    "use_col_detail": ("Chi tiết", "Details"),
    "use_ev_khoa": ("Khoá · {0}", "Locked · {0}"),
    "use_ev_mo_khoa": ("Mở khoá", "Unlocked"),
    "use_ev_het_khoa": ("Hết khoá", "Lock ended"),
    "use_ev_doi_model": ("Đổi model {0} → {1}", "Switched {0} → {1}"),
    "use_ev_loi": ("Lỗi · {0}", "Error · {0}"),
    "use_ev_hoc_han_muc": ("Ghi nhớ hạn mức", "Limit learned"),
    "use_ev_cho": ("Chờ", "Wait"),
    "use_reason_han_muc_ngay": ("hết hạn mức trong ngày", "daily quota exhausted"),
    "use_reason_han_muc_phut": ("hết hạn mức theo phút", "per-minute quota exhausted"),
    "use_reason_cham_han_muc_ngay": ("đã gửi đủ số yêu cầu/ngày", "daily request count reached"),
    "use_reason_qua_tai": ("quá tải (HTTP 5xx)", "overloaded (HTTP 5xx)"),
    "use_reason_khong_ton_tai": ("key không dùng được model này (HTTP 404)", "not available to this key (HTTP 404)"),
    "use_reason_bi_chan": ("bộ lọc của Google chặn đoạn này", "Google's filters blocked this chunk"),
    "use_reason_cho_han_muc": ("model trước phải chờ hạn mức token/phút", "the previous model had to wait for its per-minute quota"),
    "use_reason_uu_tien": ("quay lại model ưu tiên", "back to the preferred model"),
    "use_err_qua_tai": ("quá tải", "overloaded"),
    "use_err_han_muc": ("hạn mức phút", "per-minute quota"),
    "use_err_han_muc_ngay": ("hạn mức ngày", "daily quota"),
    "use_err_bi_chan": ("bị bộ lọc chặn", "blocked by filters"),
    "use_err_model": ("không tồn tại", "not found"),
    "use_err_cau_hinh": ("cấu hình / key", "config / key"),
    "use_err_tam_thoi": ("mạng", "network"),
    "use_err_khac": ("khác", "other"),

    # ------------------------------------------------------------ nhat ky
    "logs_title": ("Nhật ký", "Logs"),
    "logs_search_placeholder": ("Tìm trong nhật ký...", "Search logs..."),
    "logs_level_all": ("Tất cả", "All"),
    "logs_level_warning": ("Cảnh báo & lỗi", "Warnings & errors"),
    "logs_level_error": ("Chỉ lỗi", "Errors only"),
    "logs_btn_open_file": ("Mở tệp nhật ký", "Open log file"),
    "logs_btn_open_folder": ("Mở thư mục", "Open folder"),
    "logs_btn_clear_view": ("Xoá màn hình", "Clear view"),

    # ------------------------------------------------------------ cai dat
    "set_title": ("Cài đặt", "Settings"),
    "set_section_appearance": ("Giao diện", "Appearance"),
    "set_language": ("Ngôn ngữ giao diện", "Interface language"),
    "set_theme": ("Chủ đề", "Theme"),
    "set_theme_auto": ("Theo Windows", "Follow Windows"),
    "set_theme_light": ("Sáng", "Light"),
    "set_theme_dark": ("Tối", "Dark"),
    "set_accent": ("Màu nhấn", "Accent color"),
    "set_mica": ("Hiệu ứng Mica", "Mica effect"),
    "set_mica_hint": ("Chỉ có trên Windows 11; Windows 10 tự bỏ qua.", "Windows 11 only; ignored on Windows 10."),
    "set_scale": ("Tỷ lệ hiển thị", "Display scaling"),
    "set_scale_auto": ("Theo Windows", "Follow Windows"),
    "set_restart_needed": ("Cần khởi động lại app để áp dụng.", "Restart the app to apply."),
    "set_log_font": ("Cỡ chữ khung nhật ký (px)", "Log font size (px)"),
    "set_remember_window": ("Nhớ kích thước và vị trí cửa sổ", "Remember window size and position"),
    "set_section_output": ("Bản gõ chữ", "Transcripts"),
    "set_output_folder": ("Thư mục lưu", "Output folder"),
    "set_name_template": ("Mẫu tên tệp", "File name template"),
    "set_name_preview": (
        "Ví dụ: {0}   ·   Biến: {{ten}} tên tệp, {{ngay_ghi}} lúc tạo tệp âm thanh, {{ngay}} {{gio}} lúc chuyển, "
        "{{model}}",
        "Example: {0}   ·   Variables: {{ten}} file name, {{ngay_ghi}} audio creation time, {{ngay}} {{gio}} "
        "conversion time, {{model}}",
    ),
    "set_name_invalid": ("Mẫu không hợp lệ. Biến: {ten} {ngay_ghi} {ngay} {gio} {model}",
                         "Invalid template. Variables: {ten} {ngay_ghi} {ngay} {gio} {model}"),
    "set_extension": ("Đuôi tệp", "File extension"),
    "set_on_conflict": ("Khi đã có tệp trùng tên", "When a file with the same name exists"),
    "set_conflict_number": ("Đánh số thêm (tên (2).txt)", "Add a number (name (2).txt)"),
    "set_conflict_overwrite": ("Ghi đè", "Overwrite"),
    "set_conflict_skip": ("Bỏ qua tệp âm thanh đó", "Skip that audio file"),
    "set_encoding": ("Mã hoá", "Encoding"),
    "set_encoding_utf8": ("UTF-8", "UTF-8"),
    "set_encoding_bom": ("UTF-8 có BOM (Notepad cũ của Windows 10)", "UTF-8 with BOM (old Windows 10 Notepad)"),
    "set_newline": ("Kiểu xuống dòng", "Line endings"),
    "set_newline_crlf": ("Windows (CRLF)", "Windows (CRLF)"),
    "set_newline_lf": ("Unix (LF)", "Unix (LF)"),
    "set_open_when_done": ("Chuyển xong một tệp thì", "When a file is done"),
    "set_open_nothing": ("Không làm gì", "Do nothing"),
    "set_open_file": ("Mở bản gõ chữ", "Open the transcript"),
    "set_open_folder": ("Mở thư mục chứa", "Show in folder"),
    "set_header": ("Thêm phần đầu tệp", "Add a header"),
    "set_header_hint": ("Tên tệp âm thanh, lúc chuyển, model, thời lượng và thời gian nói của từng người.",
                        "Audio file name, conversion time, model, duration and speaking time per speaker."),
    "set_chunk_markers": ("Chèn dòng \"----- Đoạn 2/15 -----\" giữa các đoạn",
                          "Insert \"----- Đoạn 2/15 -----\" lines between chunks"),
    "set_chunk_markers_hint": ("Tiện để đối chiếu với âm thanh của từng đoạn khi thấy chỗ nào gõ sai.",
                               "Handy for finding the matching chunk audio when something looks wrong."),
    "set_save_map": ("Lưu kèm bản đồ người nói (.nguoi_noi.txt)", "Also save the speaker map (.nguoi_noi.txt)"),
    "set_save_map_hint": ("Chỉ có với cách pyannote và kết hợp.", "Only for the pyannote and hybrid methods."),
    "set_save_clean": ("Lưu kèm âm thanh đã làm sạch (.sach.flac)", "Also save the cleaned audio (.sach.flac)"),
    "set_save_clean_hint": ("Đã cắt khoảng lặng nên ngắn hơn tệp gốc.", "Silence is trimmed, so it is shorter than the original."),
    "set_section_queue": ("Hàng đợi", "Queue"),
    "set_on_error": ("Khi một tệp bị lỗi", "When a file fails"),
    "set_on_error_continue": ("Làm tiếp tệp sau", "Continue with the next file"),
    "set_on_error_stop": ("Dừng cả hàng đợi", "Stop the queue"),
    "set_notify": ("Thông báo khi xong hàng đợi", "Notify when the queue finishes"),
    "set_notify_hint": ("Nháy nút app trên taskbar, và hiện thông báo nếu đang ở cửa sổ khác.",
                        "Flashes the taskbar button, and shows a notification if another window is active."),
    "set_sound": ("Phát âm báo khi xong hàng đợi", "Play a sound when the queue finishes"),
    "set_keep_awake": ("Không cho máy ngủ trong lúc chuyển đổi", "Keep the PC awake while converting"),
    "set_keep_awake_hint": ("Màn hình vẫn tắt theo cài đặt Windows.", "The display still turns off as configured."),
    "set_remember_folder": ("Hộp chọn tệp mở lại thư mục lần trước", "File dialog reopens the last folder"),
    "set_open_dialog_folder": ("Thư mục mở sẵn khi chọn tệp", "Default folder for the file dialog"),
    "set_open_dialog_folder_placeholder": ("Để trống = Downloads", "Empty = Downloads"),
    "set_subfolders": ("Thêm thư mục thì lấy cả thư mục con", "Adding a folder includes subfolders"),
    "set_accepted_ext": ("Đuôi tệp âm thanh được nhận", "Accepted audio extensions"),
    "set_section_system": ("Hệ thống", "System"),
    "set_temp_folder": ("Thư mục tạm", "Temp folder"),
    "set_temp_placeholder": ("Để trống = tmp trong thư mục dữ liệu", "Empty = tmp in the data folder"),
    "set_temp_usage": ("{0} — {1} thư mục, {2:.1f} MB", "{0} — {1} folders, {2:.1f} MB"),
    "set_btn_clean_temp": ("Dọn thư mục tạm", "Clean temp folder"),
    "set_btn_open_temp": ("Mở", "Open"),
    "set_temp_cleaned": ("Đã xoá {0} thư mục tạm.", "Removed {0} temp folders."),
    "set_delete_temp": ("Xoá thư mục tạm của tệp khi xong", "Delete a file's temp folder when done"),
    "set_delete_temp_hint": (
        "Lỗi giữa chừng thì thư mục tạm luôn được giữ để lần sau làm tiếp mà không gửi lại các đoạn đã xong.",
        "On errors the temp folder is always kept so the next run resumes without resending finished chunks.",
    ),
    "set_ffmpeg": ("ffmpeg.exe", "ffmpeg.exe"),
    "set_ffmpeg_using": ("Đang dùng: {0}", "Using: {0}"),
    "set_log_level": ("Mức chi tiết nhật ký", "Log detail level"),
    "set_log_info": ("Bình thường (INFO)", "Normal (INFO)"),
    "set_log_debug": ("Chi tiết (DEBUG, ghi cả yêu cầu gửi Google)", "Detailed (DEBUG, includes Google requests)"),
    "set_log_size": ("Dung lượng mỗi tệp nhật ký (MB)", "Size per log file (MB)"),
    "set_log_count": ("Số tệp nhật ký cũ giữ lại", "Old log files to keep"),
    "set_section_about": ("Thông tin & dữ liệu", "About & data"),
    "set_about_data": ("Thư mục dữ liệu: {0}", "Data folder: {0}"),
    "set_about_chung": ("Dùng chung với GoogleAITranscribe (nhật ký, hạn mức): {0}",
                        "Shared with GoogleAITranscribe (logs, quota): {0}"),
    "set_about_runtime": ("Runtime: {0}  (python {1} · nhận diện người nói {2} · ffmpeg {3})",
                          "Runtime: {0}  (python {1} · speaker recognition {2} · ffmpeg {3})"),
    "set_btn_open_data": ("Mở thư mục dữ liệu", "Open data folder"),
    "set_btn_open_config": ("Mở config.txt", "Open config.txt"),
    "set_btn_restart": ("Khởi động lại", "Restart"),
    "set_btn_reset": ("Khôi phục cài đặt gốc", "Reset settings"),
    "set_reset_title": ("Khôi phục cài đặt gốc?", "Reset all settings?"),
    "set_reset_body": (
        "config.txt được thay bằng bản mặc định (bản cũ lưu thành config.txt.<ngày giờ>.bak) và app khởi động lại. "
        "API key, token và prompt không bị xoá.",
        "config.txt is replaced with the default (the old one is kept as config.txt.<timestamp>.bak) and the app "
        "restarts. API key, token and prompts are kept.",
    ),
}


class _BoDich(QObject):
    doi_ngon_ngu = Signal(str)


bo_dich = _BoDich()


def dat_ngon_ngu(ma: str):
    global ngon_ngu_hien_tai
    if ma not in ("vi", "en"):
        ma = "vi"
    ngon_ngu_hien_tai = ma
    bo_dich.doi_ngon_ngu.emit(ma)


def tr(key: str, *tham_so) -> str:
    cap = _BANG.get(key)
    if not cap:
        return key
    chu = cap[0] if ngon_ngu_hien_tai == "vi" else cap[1]
    return chu.format(*tham_so) if tham_so else chu
