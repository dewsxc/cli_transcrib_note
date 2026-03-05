import os
import time

from utils import content_utils
from utils import file_utils
from setup import ServiceSetup
from importer.provider import SourceInfo

import mlx_whisper
from mlx_whisper import writers


class AudioTranscriptor():

    def __init__(self, args):
        self.args = args

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
            if not self.src_info.src_fp.endswith('.wav'):
                tmp = file_utils.transform_to_audio(self.src_info.src_fp)

            # TODO Add Whisper.cpp support.
            print(f"Transcribing with {lang} using {self.args.speech_to_text}: {tmp if tmp else self.src_info.src_fp}")

            if self.args.speech_to_text == 'lightning-whisper-mlx':
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

        except Exception as e:
            print(e)
            if tmp and os.path.exists(tmp):
                os.remove(tmp)

            raise e

        return True

    def post_process(self):
        if self.src_info.srt_fp and os.path.exists(self.src_info.srt_fp):
            content_utils.s_to_t(self.src_info.srt_fp)
    
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
