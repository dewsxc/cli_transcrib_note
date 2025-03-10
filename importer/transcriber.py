import os
from pathlib import Path

from utils import content_utils
from utils import file_utils
from setup import ServiceSetup
from importer.provider import SourceInfo, YTSrcInfo

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
import mlx_whisper
from mlx_whisper import writers


class AudioTranscriptor():

    def __init__(self, args, src:SourceInfo):
        self.args = args
        self.src_info = src

    def start_transcribe(self):
        result = True
        if self.pre_process():  # True if need transcription.
            result = self.__transcribe()
        else:
            result = False
        self.post_process()
        return result


    def pre_process(self):
        """ 
        Return True will execute __transcribe()
        Check:
            .srt exists
            Transcription record.
        """
        # TODO: Check over write.
        if self.src_info.srt_fp and os.path.exists(self.src_info.srt_fp):
            print("SRT exists, skip transcribing: " + self.src_info.srt_fp)
            return False

        return True

    def __transcribe(self):
        """ Will bypass if file exists. """
        
        if not self.src_info.src_fp or not os.path.exists(self.src_info.src_fp):
            raise Exception("Source is not exists: " + str(self.src_info.src_fp))
        
        tmp = None
        try:
            if not self.src_info.src_fp.endswith('.wav'):
                tmp = file_utils.transform_to_audio(self.src_info.src_fp)

            self.use_mlx(
                self.args.proj_setup,
                tmp if tmp else self.src_info.src_fp,
                self.src_info.srt_fp,
                model_size=self.args.model_size,
            )

            if tmp and os.path.exists(tmp):
                os.remove(tmp)

        except Exception as e:
            print(e)
            if os.path.exists(tmp):
                os.remove(tmp)

            raise e

        return True

    def post_process(self):
        if self.src_info.srt_fp and os.path.exists(self.src_info.srt_fp):
            content_utils.s_to_t(self.src_info.srt_fp)
    
    def use_mlx(self, proj_setup:ServiceSetup, src, srt_fp, format='srt', model_size="small", lang='zh', override=False):
        # Use mlx framework.

        model_dir = proj_setup.get_dir_for_whisper_model(model_size)
        if not os.path.exists(model_dir):
            raise Exception("Unkonwn model: " + str(model_dir))
        
        # Transcribe
        result = mlx_whisper.transcribe(
            src,
            path_or_hf_repo=model_dir,
            language=lang,
            verbose=True,
        )
        writer = writers.get_writer(format, os.path.dirname(srt_fp))
        writer(result, srt_fp)
        
        return False


class YTTranscriptor(AudioTranscriptor):

    def __init__(self, args, src:YTSrcInfo):
        super().__init__(args, src)
        self.src = src
    
    def pre_process(self):
        should_proceed = super().pre_process()
        
        if should_proceed:
            self.src.src_fp = self.download_lowest_quality_audio() # Should be .wav
        
            if not self.src.src_fp or not os.path.exists(self.src.src_fp):
                print("===== Donwload failed. =====")
                should_proceed = False

        return should_proceed

    def post_process(self):
        super().post_process()
        if self.src_info.src_fp and os.path.exists(self.src_info.src_fp):
            os.remove(self.src_info.src_fp)
    
    def download_lowest_quality_audio(self, audio_format='.wav'):

        fp = self.src.src_fp

        if os.path.exists(fp):
            print("Audio exists: " + fp)
            return fp
        
        no_ext_fp = Path(fp).with_suffix("").as_posix()

        ydl_opts = {
            'outtmpl': no_ext_fp,  # 'e:/python/downloadedsongs/%(title)s.%(ext)s',
            'format': 'worstaudio/worst',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': audio_format.replace(".", ""),
            }],
        }

        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([self.src.video_url])
            
        return fp
