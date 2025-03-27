import os

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
            result = self.__transcribe()
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

    def __transcribe(self):
        """ Will bypass if file exists. """
        
        if not self.src_info.src_fp or not os.path.exists(self.src_info.src_fp):
            raise Exception("Source is not exists: " + str(self.src_info.src_fp))
        
        tmp = None
        try:
            if not self.src_info.src_fp.endswith('.wav'):
                tmp = file_utils.transform_to_audio(self.src_info.src_fp)

            # TODO Add Whisper.cpp support.
            self.use_mlx(
                self.args.proj_setup,
                tmp if tmp else self.src_info.src_fp,
                self.src_info.srt_fp,
                model_size=self.args.model_size,
                lang=self.args.lang,
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

        model_dir = proj_setup.get_dir_for_mlx_whisper_model(model_size)
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

    def post_process(self):
        super().post_process()
        if self.src_info.src_fp and os.path.exists(self.src_info.src_fp):
            os.remove(self.src_info.src_fp)
