from argparse import Namespace

from importer.data_setup import SourceInfo, YTSrcInfo, YTChannalSrcInfo
from importer.provider import AudioSourceProvider, ZoomVideoProvider, YTVideoProvider, YTChannelsLatestVideoProvider
from importer.transcriber import AudioTranscriptor, YTTranscriptor
from importer.recorder import SimpleRecorder
from importer.questioner import ClaudeSrtSummary
from importer.output_helper import LogseqHelper, MarkDownHelper


"""
audio <Path>

Input: File or dir path.
Output: From graph options.
"""

class AudioImporter:

    def __init__(self, args:Namespace):
        self.args = args
        self.proj_setup = args.proj_setup
        self.output_helper = LogseqHelper(self.proj_setup)
        self.proj_setup.change_to_graph(self.args.graph)

        self.setup()
        
    def setup(self):
        """
        Contain differences of each instance.
        """
        self.provider = AudioSourceProvider(self.args)
        self.transcriptor_cls = AudioTranscriptor
        self.questioner_cls = ClaudeSrtSummary
    
    def start_import(self):

        for src in self.provider.get_src():
            
            if SimpleRecorder.check_if_had_read(self.args.proj_setup, src.get_main_id(), src.get_id()):
                print("Already read: {} {}".format(src.get_main_id(), src.get_id()))
                continue

            t = self.transcriptor_cls(self.args, src)
            if not t.start_transcribe():
                # TODO: Allow skip.
                print("Skip: {} {}".format(src.get_main_id(), src.get_id()))
                SimpleRecorder.mark_video_as_read(self.args.proj_setup, src.get_main_id(), src.get_id())
                continue
            
            # TODO: Write a func for init and return AI instance instead.
            c = self.questioner_cls(self.proj_setup.anthropic_key)
            c.setup(self.args.ai_model)
            c.prepare_chat()
            c.summarize_srt(self.get_prompt(src), src.srt_fp)
            
            self.save(self.args.page, c.qa_list, src)

            SimpleRecorder.mark_video_as_read(self.args.proj_setup, src.get_main_id(), src.get_id())
    
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
        self.transcriptor_cls = AudioTranscriptor
        self.questioner_cls = ClaudeSrtSummary


"""
yt <Link>
"""

class YTImporter(AudioImporter):

    def setup(self):
        self.provider = YTVideoProvider(self.args)
        self.transcriptor_cls = YTTranscriptor
        self.questioner_cls = ClaudeSrtSummary
    
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
        self.transcriptor_cls = YTTranscriptor
        self.questioner_cls = ClaudeSrtSummary

        self.proj_setup.change_to_graph("NewsFeed")

    def get_prompt(self, src:YTChannalSrcInfo):
        return src.question
