import os
import re
from pathlib import Path


"""
Source Info
"""

class SourceInfo:

    def __init__(self, src_fp):
        self.src_fp = src_fp
        self.srt_fp = None

    def get_src_fn(self):
        return Path(self.src_fp).with_suffix("").name if self.src_fp else ""
    
    def get_default_srt_fp(self):
        return Path(self.src_fp).with_suffix(".srt").as_posix()

    def get_main_id(self):
        return Path(self.src_fp).name

    def get_id(self):
        return "1"


class ZoomSrcInfo(SourceInfo):

    def get_default_srt_fp(self):
        p = Path(self.src_fp)
        return os.path.join(p.parent.as_posix(), p.parent.name + ".srt")

    def get_main_id(self):
        return Path(self.src_fp).parent.name


class YTSrcInfo(SourceInfo):

    def __init__(self, audio_dir, channel_info=None, video_info=None):
        super().__init__(None)
        self.audio_dir = audio_dir

        self.video_url = None
        self.author = None
        self.title = None
    
        if channel_info:
            self.channel_info = channel_info
            self.channel_id = channel_info.get('channel_id')
            self.author     = channel_info['uploader']
            self.video_info = channel_info['entries'][0]
            self.video_url  = self.video_info['url']
            self.watch_url  = self.video_url
            self.video_id   = self.video_info['id']
            self.title      = self.video_info['title']

        if video_info:
            self.channel_info = None
            self.channel_id = video_info['channel_id']
            self.author     = video_info['uploader']
            self.video_info = video_info
            self.video_url  = video_info['webpage_url']
            self.watch_url  = self.video_url
            self.video_id   = video_info['id']
            self.title      = video_info['title']

        self.title = self.remove_mk_symbol(self.title)
        self.author = self.remove_mk_symbol(self.author)
        self.src_fp = os.path.join(self.audio_dir, "{} - {}{}".format(self.author, self.title, '.wav'))
        self.srt_fp = Path(self.src_fp).with_suffix('.srt').as_posix()
    
    def remove_mk_symbol(self, s):
        if not s:
            return s
        markdown_chars = {
            "[": "",
            "]": "",
            "(": "\u0028",
            ")": "\u0029",
            "#": "",
            "|": "",
            "\\": "",
        }
        return re.sub(r'[\[\]()#|\\]', lambda m: markdown_chars.get(m.group(), ""), s)
    
    def get_main_id(self):
        return self.author

    def get_id(self):
        return self.video_id


class YTChannalSrcInfo(YTSrcInfo):

    def __init__(self, audio_dir, channel_data, channel_info=None, video_info=None):
        super().__init__(audio_dir, channel_info, video_info)
        self.acc        = channel_data.get("username")
        self.channel_name = channel_data.get("channel_name")
        self.question   = channel_data.get("question")