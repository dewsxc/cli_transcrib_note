
from importer.data_setup import SourceInfo, YTChannalSrcInfo
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

    def __init__(self, args):
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
                print("Already read: {} {} {}".format(src.get_main_id, src.get_id, src.get_src_fn()))
                continue

            t = self.transcriptor_cls(self.args, src)
            t.start_transcribe()
            
            c = self.questioner_cls(self.proj_setup.anthropic_key)
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
            sum_md = MarkDownHelper.compose_summarize_md(
                MarkDownHelper.compose_page_link(page, src.get_src_fn()),
                MarkDownHelper.compose_summarize_from_qa_lsit_md(qa_list)
            )
            self.output_helper.save_under_page(sum_md, page, src.srt_fp)

        else:
            sum_md = MarkDownHelper.compose_summarize_md(
                MarkDownHelper.compose_file_link(src.get_src_fn()),
                MarkDownHelper.compose_summarize_from_qa_lsit_md(qa_list)
            )
            self.output_helper.save_under_diary(sum_md, src.srt_fp)


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


"""
news
"""

class DailyNewsImporter(AudioImporter):

    def setup(self):
        self.provider = YTChannelsLatestVideoProvider(self.args)
        self.transcriptor_cls = YTTranscriptor
        self.questioner_cls = ClaudeSrtSummary

        self.proj_setup.change_to_graph("NewsFeed")

    def get_prompt(self, src:YTChannalSrcInfo):
        return src.question
