import os
import re
import time

from utils import content_utils
from utils import file_utils
from setup import ServiceSetup
from importer.provider import SourceInfo


class CoverageIncompleteError(Exception):
    """Raised when Gemini cannot produce sufficient coverage after all retries."""
    pass

import mlx_whisper
from mlx_whisper import writers


def _get_audio_duration(fp):
    """Return audio duration in seconds via ffprobe."""
    if not fp or not os.path.exists(fp):
        return 0.0
    try:
        import subprocess, json
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', fp],
            capture_output=True, text=True,
        )
        for stream in json.loads(result.stdout).get('streams', []):
            dur = stream.get('duration')
            if dur:
                return float(dur)
    except Exception:
        pass
    return 0.0


def _get_srt_end_seconds(srt_content: str) -> float:
    """Return the end timestamp (seconds) of the last SRT entry, or 0 if unparseable."""
    matches = re.findall(r'-->\s*(\d{2}):(\d{2}):(\d{2})[,\.](\d+)', srt_content)
    if not matches:
        return 0.0
    h, m, s, ms = matches[-1]
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def _get_srt_entry_count(srt_content: str) -> int:
    return len(re.findall(r'-->', srt_content))


def _is_srt_monolithic(srt_content: str, audio_duration: float) -> bool:
    """True if the SRT has far too few entries relative to audio length."""
    count = _get_srt_entry_count(srt_content)
    min_expected = max(2, audio_duration / 30)
    return count < min_expected


_GEMINI_MAX_RETRIES = 3
_GEMINI_COVERAGE_THRESHOLD = 0.85


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

        base_prompt = (
            f"請將這段音訊轉錄為SRT字幕格式（語言：{lang}），包含準確的時間戳記。"
            "請只輸出標準SRT格式內容（序號、時間範圍、字幕文字），不需要任何額外說明或Markdown標記。"
        )
        retry_prompt = base_prompt + "每個字幕條目只能包含一句話或約10個字，不可將所有內容放入單一條目。"

        model = genai.GenerativeModel(model_name)
        audio_duration = _get_audio_duration(src)

        retry_elapsed = 0.0  # time spent on failed attempts
        last_elapsed = 0.0   # time spent on the final accepted attempt
        total_in_tok = 0
        total_out_tok = 0
        retry_in_tok = 0     # tokens from failed retry attempts
        retry_out_tok = 0
        srt_content = None

        for attempt in range(1, _GEMINI_MAX_RETRIES + 1):
            prompt = base_prompt if attempt == 1 else retry_prompt
            print(f"Uploading audio to Gemini ({model_name}): {src}")
            audio_file = genai.upload_file(path=src)

            while audio_file.state.name == "PROCESSING":
                print("Waiting for Gemini audio file processing...")
                time.sleep(3)
                audio_file = genai.get_file(audio_file.name)

            if audio_file.state.name == "FAILED":
                raise Exception("Gemini audio file processing failed")

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
            if audio_duration > 0:
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
                print("Max retries reached (monolithic SRT); saving best result so far.")
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
