from argparse import Namespace

from setup import ServiceSetup
from importer.data_setup import SourceInfo, YTSrcInfo, YTChannalSrcInfo
from importer.provider import AudioSourceProvider, ZoomVideoProvider, YTVideoProvider, YTChannelsLatestVideoProvider
from importer.transcriber import AudioTranscriptor, YTTranscriptor
from importer.recorder import SimpleRecorder
from importer.questioner import ClaudeSrtSummary
from importer.output_helper import LogseqHelper


"""
audio <Path>

Input: File or dir path.
Output: From graph options.
"""

class AudioImporter:

    def __init__(self, args:Namespace):
        self.args = args
        self.proj_setup: ServiceSetup = args.proj_setup
        self.output_helper = LogseqHelper(self.proj_setup)
        self.proj_setup.change_to_graph(self.args.graph)

        self.setup()
        
    def setup(self):
        """
        Override to customize source, transcripor and AI model service.
        """
        self.provider = AudioSourceProvider(self.args)
        self.transcriptor = AudioTranscriptor(self.args)
        self.questioner = ClaudeSrtSummary(self.proj_setup)
    
    def start_import(self):

        self.questioner.prepare(self.args.ai_model)

        for src in self.provider.get_info():
            
            if SimpleRecorder.check_if_had_read(self.args.proj_setup, src.get_main_id(), src.get_id()):
                print("Already read: {} {}".format(src.get_main_id(), src.get_id()))
                continue
            
            if not src.is_srt_exists():

                if not self.provider.get_src(src):
                    continue

                if not self.transcriptor.start_transcribe(src):
                    print("Skip transcribing: {}".format(src.src_fp))
                    continue

            self.questioner.summarize_srt(self.get_prompt(src), src.srt_fp)

            self.save(self.args.page, self.questioner.qa_list, src)
            SimpleRecorder.mark_video_as_read(self.args.proj_setup, src.get_main_id(), src.get_id())

            self.questioner.close_conversation()
    
    def get_prompt(self, src):
        """
        Override to get prompt by source.
        """
        return "列出大綱並且摘要重點內容"

    def save(self, page, qa_list, src:SourceInfo):
        if page:
            self.output_helper.save_summary_under_page(page, qa_list, src.srt_fp)
        else:
            self.output_helper.save_summary_under_daily(qa_list, src.srt_fp)


"""
zoom <Path>

Source: File or Dir path.
Output: From graph options.
"""

class ZoomRecordImporter(AudioImporter):

    def setup(self):
        self.provider = ZoomVideoProvider(self.args)
        self.transcriptor = AudioTranscriptor(self.args)
        self.questioner = ClaudeSrtSummary(self.proj_setup)


"""
yt <Link>
"""

class YTImporter(AudioImporter):

    def setup(self):
        self.provider = YTVideoProvider(self.args)
        self.transcriptor = YTTranscriptor(self.args)
        self.questioner = ClaudeSrtSummary(self.proj_setup)
    
    def save(self, page, qa_list, src:YTSrcInfo):
        if page:
            self.output_helper.save_summary_under_page_with_url(page, qa_list,src.video_url, src.srt_fp)
        else:
            self.output_helper.save_summary_under_daily_with_url(qa_list, src.video_url, src.srt_fp)


"""
news
"""

class DailyNewsImporter(YTImporter):

    def setup(self):
        self.provider = YTChannelsLatestVideoProvider(self.args)
        self.transcriptor = YTTranscriptor(self.args)
        self.questioner = ClaudeSrtSummary(self.proj_setup)

    def get_prompt(self, src:YTChannalSrcInfo):
        return src.question
