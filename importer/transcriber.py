import os
import re
import time

from utils import content_utils
from utils import file_utils
from setup import ServiceSetup
from importer.provider import SourceInfo


class CoverageIncompleteError(Exception):
    """Raised when Gemini cannot produce a usable transcript after all retries.

    Caught by __transcribe() to skip the item gracefully so a batch run keeps
    going and the item is retried on the next run.
    """
    pass

import mlx_whisper
from mlx_whisper import writers


def _ffprobe(fp):
    """Return parsed ffprobe JSON (format + streams), or {} if it cannot be read."""
    if not fp or not os.path.exists(fp):
        return {}
    try:
        import subprocess, json
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', fp],
            capture_output=True, text=True,
        )
        return json.loads(result.stdout)
    except Exception:
        return {}


def _get_audio_duration(fp):
    """Return audio duration in seconds via ffprobe."""
    for stream in _ffprobe(fp).get('streams', []):
        dur = stream.get('duration')
        if dur:
            return float(dur)
    return 0.0


# ffprobe format_name -> the audio MIME type Gemini accepts for that container.
_AUDIO_MIME_BY_FORMAT = {
    'aac': 'audio/aac',
    'mp3': 'audio/mpeg',
    'wav': 'audio/wav',
    'flac': 'audio/flac',
    'ogg': 'audio/ogg',
    'matroska,webm': 'audio/webm',
    'mov,mp4,m4a,3gp,3g2,mj2': 'audio/mp4',
}


def _detect_gemini_mime(fp):
    """Return the MIME type to declare when uploading to Gemini, or None to let
    the SDK infer it from the file extension.

    The extension cannot be trusted: yt-dlp saves YouTube's HLS audio formats as
    .mp4 while the bytes are actually a raw ADTS AAC stream. And Gemini picks its
    decoder from the MIME's top-level type, so any audio-only file announced as
    video/* is handed to the video transcoder and comes back FAILED — that holds
    even for a genuine MP4 container. So probe the real container and declare
    audio/* whenever there is no video stream.
    """
    probe = _ffprobe(fp)
    streams = probe.get('streams', [])
    if not streams:
        return None  # unprobeable — the extension is the only hint we have
    # Cover art is stored as a video stream; it does not make the file a video.
    if any(s.get('codec_type') == 'video' and not s.get('disposition', {}).get('attached_pic')
           for s in streams):
        return None
    return _AUDIO_MIME_BY_FORMAT.get(probe.get('format', {}).get('format_name'))


def _get_srt_end_seconds(srt_content: str) -> float:
    """Return the latest end timestamp (seconds) in the SRT, or 0 if unparseable.

    Uses the maximum rather than the last entry: Gemini sometimes emits cues out
    of chronological order, which would otherwise under-report the coverage.
    """
    matches = re.findall(r'-->\s*(\d{2}):(\d{2}):(\d{2})[,\.](\d+)', srt_content)
    if not matches:
        return 0.0
    return max(int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
               for h, m, s, ms in matches)


def _get_srt_entry_count(srt_content: str) -> int:
    return len(re.findall(r'-->', srt_content))


def _is_srt_monolithic(srt_content: str, audio_duration: float) -> bool:
    """True if the SRT has far too few entries relative to audio length."""
    count = _get_srt_entry_count(srt_content)
    min_expected = max(2, audio_duration / 30)
    return count < min_expected


# Gemini follows a named language far more reliably than a bare code, and has to
# be told not to translate: asked for "語言：zh" it will happily return a Chinese
# recording as English subtitles.
_LANG_NAMES = {
    'zh': '中文', 'zh-tw': '中文', 'zh-cn': '中文', 'zh-hans': '中文', 'zh-hant': '中文',
    'en': 'English', 'ja': '日本語', 'ko': '한국어',
}

_CJK_RE = re.compile(r'[\u4e00-\u9fff]')
_LATIN_RE = re.compile(r'[A-Za-z]')


def _srt_text_only(srt_content: str) -> str:
    """Strip sequence numbers and timestamp lines, leaving just the subtitle text."""
    return '\n'.join(ln for ln in srt_content.splitlines()
                     if '-->' not in ln and not ln.strip().isdigit())


def _is_wrong_language(srt_content: str, lang: str) -> bool:
    """True if a Chinese transcript came back in Latin script, i.e. translated.

    Only Chinese is checked: it is what this pipeline targets, and CJK-vs-Latin
    script is a signal we can trust without a language-detection dependency.
    """
    if not (lang or '').lower().startswith('zh'):
        return False
    text = _srt_text_only(srt_content)
    return len(_LATIN_RE.findall(text)) > len(_CJK_RE.findall(text))


_GEMINI_MAX_RETRIES = 3
_GEMINI_COVERAGE_THRESHOLD = 0.85
# Past this much of the audio length the timestamps are hallucinated, not drift.
_GEMINI_OVERRUN_THRESHOLD = 1.25

# Extra instruction added on a retry, aimed at whatever the previous attempt got wrong.
_RETRY_HINTS = {
    'language':   "注意：上一次你把內容翻譯成了其他語言，這是錯的。請逐字轉錄，保持與音訊完全相同的語言。",
    'coverage':   "注意：上一次只轉錄了前面一小段就停了。請務必轉錄到音訊的最後一秒。",
    'overrun':    "注意：上一次的時間戳超出了音訊長度。請重新校準，最後一個時間戳必須接近音訊結尾。",
    'monolithic': "注意：上一次把大段內容塞進單一條目。請每個條目只放一句話（約 10-20 字）。",
}


class AudioTranscriptor():

    def __init__(self, args):
        self.args = args
        self.stats = None

    def start_transcribe(self, src:SourceInfo):
        self.src_info = src
        result = True
        if self.pre_process():  # True if need transcription.
            result = self.__transcribe(src.lang)
        else:
            result = False
        self.post_process()
        return result

    def pre_process(self):
        """ 
        Return True will execute __transcribe()
        """
        # TODO: Check over write.
        if self.src_info.srt_fp and os.path.exists(self.src_info.srt_fp):
            print("SRT exists, skip transcribing: " + self.src_info.srt_fp)
            return False

        return True

    def __transcribe(self, lang=None):
        """ Will bypass if file exists. """

        if not self.src_info.src_fp or not os.path.exists(self.src_info.src_fp):
            raise Exception("Source is not exists: " + str(self.src_info.src_fp))

        tmp = None
        try:
            # Gemini receives the raw audio file directly; other backends need wav.
            if self.args.speech_to_text != 'gemini' and not self.src_info.src_fp.endswith('.wav'):
                tmp = file_utils.transform_to_audio(self.src_info.src_fp)

            # TODO Add Whisper.cpp support.
            print(f"Transcribing with {lang} using {self.args.speech_to_text}: {tmp if tmp else self.src_info.src_fp}")

            if self.args.speech_to_text == 'gemini':
                self.use_gemini(
                    self.args.proj_setup,
                    self.src_info.src_fp,
                    self.src_info.srt_fp,
                    model_size=self.args.model_size,
                    lang=lang if lang else self.args.lang,
                )
            elif self.args.speech_to_text == 'lightning-whisper-mlx':
                self.use_lightning_mlx(
                    self.args.proj_setup,
                    tmp if tmp else self.src_info.src_fp,
                    self.src_info.srt_fp,
                    model_size=self.args.model_size,
                    lang=lang if lang else self.args.lang,
                )
            else:
                self.use_mlx(
                    self.args.proj_setup,
                    tmp if tmp else self.src_info.src_fp,
                    self.src_info.srt_fp,
                    model_size=self.args.model_size,
                    lang=lang if lang else self.args.lang,
                )

            if tmp and os.path.exists(tmp):
                os.remove(tmp)

        except CoverageIncompleteError:
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
            return False

        except Exception as e:
            print(e)
            if tmp and os.path.exists(tmp):
                os.remove(tmp)

            raise e

        return True

    def post_process(self):
        if self.src_info.srt_fp and os.path.exists(self.src_info.srt_fp):
            content_utils.s_to_t(self.src_info.srt_fp)
    
    def use_gemini(self, proj_setup: ServiceSetup, src, srt_fp, model_size="medium", lang='zh', override=False):
        import google.generativeai as genai

        _MODEL_MAP = {
            'small':  'gemini-flash-lite-latest',
            'medium': 'gemini-flash-latest',
            'large':  'gemini-pro-latest',
        }
        model_name = _MODEL_MAP.get(model_size, 'gemini-flash-latest')

        genai.configure(
            api_key=proj_setup.gc_gemini_api_key,
            transport="rest",
        )

        model = genai.GenerativeModel(model_name)
        audio_duration = _get_audio_duration(src)

        lang_name = _LANG_NAMES.get((lang or '').lower(), lang)
        total = int(audio_duration)
        length_rule = (
            f"2. 音訊總長度為 {total // 60} 分 {total % 60} 秒（共 {total} 秒）。所有時間戳都必須落在 "
            f"00:00:00,000 到 {total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d},000 之間，"
            "且必須由小到大遞增。\n"
        ) if audio_duration > 0 else "2. 所有時間戳都必須由小到大遞增。\n"

        base_prompt = (
            "請將這段音訊逐字轉錄成 SRT 字幕檔。\n"
            f"1. 語言：音訊內容是{lang_name}，字幕必須用{lang_name}逐字記錄原話，"
            "嚴禁翻譯成英文或任何其他語言。\n"
            + length_rule +
            "3. 時間戳格式必須是 HH:MM:SS,mmm（兩位小時:兩位分鐘:兩位秒,三位毫秒），"
            "例如 00:01:05,360。禁止使用 MM:SS.mmm、方括號或任何其他格式。\n"
            "4. 每個字幕條目只包含一句話（約 10-20 字），不可把大段內容塞進單一條目。\n"
            "5. 只輸出標準 SRT：序號一行、時間範圍一行、字幕文字一行、條目間空一行。"
            "不要任何說明文字或 Markdown 標記。"
        )

        retry_elapsed = 0.0  # time spent on failed attempts
        last_elapsed = 0.0   # time spent on the final accepted attempt
        total_in_tok = 0
        total_out_tok = 0
        retry_in_tok = 0     # tokens from failed retry attempts
        retry_out_tok = 0
        srt_content = None

        retry_reason = None
        for attempt in range(1, _GEMINI_MAX_RETRIES + 1):
            hint = _RETRY_HINTS.get(retry_reason)
            prompt = base_prompt + ("\n\n" + hint if hint else "")
            print(f"Uploading audio to Gemini ({model_name}): {src}")
            audio_file = genai.upload_file(path=src, mime_type=_detect_gemini_mime(src))

            while audio_file.state.name == "PROCESSING":
                print("Waiting for Gemini audio file processing...")
                time.sleep(3)
                audio_file = genai.get_file(audio_file.name)

            if audio_file.state.name == "FAILED":
                raise Exception(
                    f"Gemini audio file processing failed (mime_type={audio_file.mime_type}, "
                    f"error={getattr(audio_file, 'error', None)}): {src}"
                )

            start_time = time.time()
            response = model.generate_content([prompt, audio_file])
            elapsed = time.time() - start_time
            last_elapsed = elapsed
            print(f"Gemini transcription finished in {elapsed:.2f} seconds.")

            try:
                genai.delete_file(audio_file.name)
            except Exception:
                pass

            attempt_in_tok = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
            attempt_out_tok = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0
            total_in_tok += attempt_in_tok
            total_out_tok += attempt_out_tok

            try:
                raw = response.text.strip()
            except ValueError:
                candidates = getattr(response, 'candidates', [])
                if candidates:
                    parts = getattr(getattr(candidates[0], 'content', None), 'parts', []) or []
                    if parts:
                        raw = parts[0].text.strip()
                    else:
                        finish_reason = getattr(candidates[0], 'finish_reason', 'unknown')
                        msg = (
                            f"Gemini returned no content (finish_reason={finish_reason}). "
                            "Audio may have been blocked by content policy."
                        )
                        # finish_reason 3=SAFETY, 4=RECITATION — unretryable; skip gracefully
                        if finish_reason in (3, 4):
                            print(msg + " Skipping item.")
                            raise CoverageIncompleteError(msg)
                        raise Exception(msg)
                else:
                    raise Exception("Gemini returned no candidates — response was empty.")

            if raw.startswith('```'):
                lines = raw.split('\n')
                inner = lines[1:]
                if inner and inner[-1].strip() == '```':
                    inner = inner[:-1]
                raw = '\n'.join(inner)

            srt_content = content_utils.normalize_srt(raw)

            needs_retry = False
            retry_reason = None
            coverage = 0.0

            if _is_wrong_language(srt_content, lang):
                print(
                    f"Wrong language (attempt {attempt}/{_GEMINI_MAX_RETRIES}): asked for "
                    f"{lang_name} but got Latin script — the model translated instead of "
                    "transcribing. Retrying..."
                )
                needs_retry = True
                retry_reason = 'language'
            elif audio_duration > 0:
                srt_end = _get_srt_end_seconds(srt_content)
                coverage = srt_end / audio_duration
                if coverage < _GEMINI_COVERAGE_THRESHOLD:
                    print(
                        f"Incomplete transcription (attempt {attempt}/{_GEMINI_MAX_RETRIES}): "
                        f"SRT ends at {srt_end:.0f}s but audio is {audio_duration:.0f}s "
                        f"({coverage*100:.1f}% coverage). Retrying..."
                    )
                    needs_retry = True
                    retry_reason = 'coverage'
                elif coverage > _GEMINI_OVERRUN_THRESHOLD:
                    print(
                        f"Hallucinated timestamps (attempt {attempt}/{_GEMINI_MAX_RETRIES}): "
                        f"SRT ends at {srt_end:.0f}s but audio is only {audio_duration:.0f}s "
                        f"({coverage*100:.1f}% coverage). Retrying..."
                    )
                    needs_retry = True
                    retry_reason = 'overrun'
                elif _is_srt_monolithic(srt_content, audio_duration):
                    entry_count = _get_srt_entry_count(srt_content)
                    print(
                        f"Monolithic SRT detected (attempt {attempt}/{_GEMINI_MAX_RETRIES}): "
                        f"only {entry_count} entries for {audio_duration:.0f}s audio. Retrying..."
                    )
                    needs_retry = True
                    retry_reason = 'monolithic'
                else:
                    entry_count = _get_srt_entry_count(srt_content)
                    warn = " (WARNING: timestamps exceed audio length)" if coverage > 1.1 else ""
                    print(f"Coverage {coverage*100:.1f}% / {entry_count} entries — accepted.{warn}")

            if needs_retry and attempt < _GEMINI_MAX_RETRIES:
                retry_elapsed += last_elapsed
                retry_in_tok += attempt_in_tok
                retry_out_tok += attempt_out_tok
                continue

            if needs_retry and retry_reason == 'language':
                # No amount of retrying fixes this: the weaker models ignore the
                # no-translation instruction every single time.
                print(
                    f"Max retries reached; '{model_name}' keeps translating {lang_name} audio "
                    "into English instead of transcribing it. Skipping item — use a larger "
                    "--model-size for this channel."
                )
                retry_in_tok += attempt_in_tok
                retry_out_tok += attempt_out_tok
                if self.stats:
                    self.stats.record_stt('gemini', audio_duration, last_elapsed,
                                          model=model_name, in_tokens=total_in_tok, out_tokens=total_out_tok,
                                          retry_time=retry_elapsed, retry_count=attempt - 1,
                                          retry_in_tokens=retry_in_tok, retry_out_tokens=retry_out_tok)
                raise CoverageIncompleteError(
                    f"'{model_name}' translated the {lang_name} audio to English on all "
                    f"{_GEMINI_MAX_RETRIES} attempts"
                )

            if needs_retry and retry_reason == 'coverage':
                print(
                    f"Max retries reached; coverage still insufficient. "
                    "Skipping item — will retry on next run."
                )
                # All attempts failed — all tokens are wasted
                retry_in_tok += attempt_in_tok
                retry_out_tok += attempt_out_tok
                if self.stats:
                    self.stats.record_stt('gemini', audio_duration, last_elapsed,
                                          model=model_name, in_tokens=total_in_tok, out_tokens=total_out_tok,
                                          retry_time=retry_elapsed, retry_count=attempt - 1,
                                          retry_in_tokens=retry_in_tok, retry_out_tokens=retry_out_tok)
                raise CoverageIncompleteError(
                    f"SRT coverage insufficient after {_GEMINI_MAX_RETRIES} attempts "
                    f"({coverage*100:.1f}% < {_GEMINI_COVERAGE_THRESHOLD*100:.0f}%)"
                )

            if needs_retry:
                print(f"Max retries reached ({retry_reason}); saving best result so far.")
            break

        with open(srt_fp, 'w', encoding='utf-8') as f:
            f.write(srt_content)

        print(f"SRT written to: {srt_fp}")

        if self.stats:
            self.stats.record_stt('gemini', audio_duration, last_elapsed,
                                  model=model_name, in_tokens=total_in_tok, out_tokens=total_out_tok,
                                  retry_time=retry_elapsed, retry_count=attempt - 1,
                                  retry_in_tokens=retry_in_tok, retry_out_tokens=retry_out_tok)

    def use_mlx(self, proj_setup:ServiceSetup, src, srt_fp, format='srt', model_size="small", lang='zh', override=False):
        # Use mlx framework.
        
        # Map model size for mlx-whisper (local model)
        if model_size == "large":
            model_size = "whisper-large-v3-turbo-q4"

        model_dir = proj_setup.get_dir_for_mlx_whisper_model(model_size)
        if not os.path.exists(model_dir):
            raise Exception("Unkonwn model: " + str(model_dir))
        
        # Transcribe
        start_time = time.time()
        result = mlx_whisper.transcribe(
            src,
            path_or_hf_repo=model_dir,
            language=lang,
            verbose=True,
        )
        end_time = time.time()
        
        # Benchmark
        transcribe_duration = end_time - start_time
        audio_duration = result.get('segments', [])[-1].get('end', 0) if result.get('segments') else 0
        ratio = audio_duration / transcribe_duration if transcribe_duration > 0 else 0
        
        print(f"Transcription finished in {transcribe_duration:.2f} seconds.")
        print(f"Audio duration: {audio_duration:.2f} seconds.")
        print(f"Speedup ratio: {ratio:.2f}x")

        writer = writers.get_writer(format, os.path.dirname(srt_fp))
        writer(result, srt_fp)

        if self.stats:
            self.stats.record_stt('mlx-whisper', audio_duration, transcribe_duration)

        return False

    def use_lightning_mlx(self, proj_setup: ServiceSetup, src, srt_fp, format='srt', model_size="small", lang='zh', override=False):
        # Use lightning-whisper-mlx framework.
        from lightning_whisper_mlx import LightningWhisperMLX

        # Map model size for lightning-whisper-mlx
        if model_size == "large":
            model_size = "distil-large-v3"

        # Transcribe
        start_time = time.time()
        
        # lightning-whisper-mlx supports passing the model name directly (it will download or find in cache)
        # or it can take a path.
        # Quantization is 4bits by default in the library if not specified.
        whisper = LightningWhisperMLX(model=model_size, batch_size=12)
        # verbose is not supported in LightningWhisperMLX.transcribe(), we have to print progress ourselves or omit it.
        result = whisper.transcribe(audio_path=src, language=lang)
        
        end_time = time.time()

        # Benchmark
        transcribe_duration = end_time - start_time
        
        # Wait, if verbose=True, lightning-whisper-mlx might return a generator or different dict format
        # Let's handle it properly by converting to list if needed
        if hasattr(result, '__iter__') and not isinstance(result, dict):
            result = list(result)
            
        # lightning-whisper-mlx return result is a dict with 'segments' as a list of lists: [start_seek, end_seek, text]
        if isinstance(result, dict) and 'segments' in result:
            segments = result['segments']
            formatted_segments = []
            audio_duration = 0
            
            for seg in segments:
                if isinstance(seg, list) and len(seg) >= 3:
                    start_seek, end_seek, text = seg[0], seg[1], seg[2]
                    # convert frame seek to seconds: frame * hop_length / sample_rate
                    # hop_length is 160, sample_rate is 16000
                    start_sec = start_seek * 160 / 16000
                    end_sec = end_seek * 160 / 16000
                    
                    formatted_segments.append({
                        'start': start_sec,
                        'end': end_sec,
                        'text': text
                    })
                    audio_duration = max(audio_duration, end_sec)
                elif isinstance(seg, dict):
                    # In case it gets updated to return dicts in the future
                    formatted_segments.append(seg)
                    audio_duration = max(audio_duration, seg.get('end', 0))

            result['segments'] = formatted_segments
        else:
            audio_duration = 0

        ratio = audio_duration / transcribe_duration if transcribe_duration > 0 else 0

        print(f"Transcription finished in {transcribe_duration:.2f} seconds.")
        print(f"Audio duration: {audio_duration:.2f} seconds.")
        print(f"Speedup ratio: {ratio:.2f}x")

        writer = writers.get_writer(format, os.path.dirname(srt_fp))
        writer(result, srt_fp)

        if self.stats:
            self.stats.record_stt('lightning-whisper-mlx', audio_duration, transcribe_duration)

        return False


class YTTranscriptor(AudioTranscriptor):
    
    def __init__(self, args):
        super().__init__(args)
        self.dont_delete_src = self.args.hd_video if hasattr(self.args, 'hd_video') else False

    def post_process(self):
        super().post_process()
        # Only remove the source file if it's not an HD video download
        if self.src_info.src_fp and os.path.exists(self.src_info.src_fp) and not self.dont_delete_src:
            os.remove(self.src_info.src_fp)
