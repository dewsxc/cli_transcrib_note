import os
import re
from pathlib import Path


"""
Source Info
"""

class SourceInfo:

    def __init__(self, src_fp=None):
        self.set_src_fp_same_as_srt(src_fp)
    
    def set_src_fp_same_as_srt(self, fp):
        self.src_fp = fp
        self.srt_fp = Path(self.src_fp).with_suffix(".srt").as_posix() if fp else None

    def get_src_fn(self):
        return Path(self.src_fp).with_suffix("").name if self.src_fp else ""
    
    def get_srt_fn(self):
        return Path(self.srt_fp).with_suffix("").name if self.srt_fp else ""

    def get_main_id(self):
        return Path(self.src_fp).name

    def get_id(self):
        return "1"
    
    def is_srt_exists(self):
        return self.srt_fp and os.path.exists(self.srt_fp)


class ZoomSrcInfo(SourceInfo):

    def set_src_fp_same_as_srt(self, fp):
        self.src_fp = fp
        p = Path(self.src_fp)
        self.srt_fp = os.path.join(p.parent.as_posix(), p.parent.name + ".srt")

    def get_main_id(self):
        return Path(self.src_fp).parent.name


class YTVideoSrcInfo(SourceInfo):
    def __init__(self, audio_dir, video_data):
        super().__init__()
        self.audio_dir = audio_dir
        self.video_data = video_data

        self.video_id = video_data.get('id')
        self.title = self._remove_mk_symbol(video_data.get('title'))
        self.author = self._remove_mk_symbol(video_data.get('uploader'))
        self.channel_id = video_data.get('channel_id')
        self.video_url = video_data.get('webpage_url')
        self.watch_url = self.video_url # Alias for consistency
        self.subtitles = video_data.get('subtitles')

        self.set_src_fp_same_as_srt(self.default_audio_fp())

    def default_audio_fp(self):
        return os.path.join(self.audio_dir, f"{self.author} - {self.title}.wav")

    def _remove_mk_symbol(self, s):
        if not s:
            return s
        markdown_chars = {
            "[": " ",
            "]": " ",
            "(": "\u0028",
            ")": "\u0029",
            "#": "",
            "|": " ",
            "\\": " ",
            "/": " ",
        }
        return re.sub(r'[\[\]()#|\\/]', lambda m: markdown_chars.get(m.group(), ""), s).strip()
    
    def get_main_id(self):
        return self.author

    def get_id(self):
        return self.video_id


class YTChannelSrcInfo:
    
    def __init__(self, audio_dir, yt_dlp_info):
        self.audio_dir = audio_dir
        self.yt_dlp_info = yt_dlp_info

        self.channel_id = yt_dlp_info.get('channel_id')
        self.channel_name = yt_dlp_info.get('channel')
        self.uploader = yt_dlp_info.get('uploader')
        self.uploader_id = yt_dlp_info.get('uploader_id')
        self.description = yt_dlp_info.get('description')
        self.tags = yt_dlp_info.get('tags')
        self.thumbnails = yt_dlp_info.get('thumbnails')
        self.webpage_url = yt_dlp_info.get('webpage_url')

        self.entries = []
        
        for entry in yt_dlp_info.get('entries', []):
            entry['channel_id'] = entry.get('channel_id') or self.channel_id
            entry['uploader'] = entry.get('uploader') or self.uploader
            entry['webpage_url'] = entry.get('webpage_url') or entry.get('url')
            v = YTVideoSrcInfo(audio_dir, entry)
            self.entries.append(v)

    def get_latest_video(self):
        if self.entries:
            return self.entries[0]
        return None
