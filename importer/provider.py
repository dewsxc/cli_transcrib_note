import os
from pathlib import Path
from datetime import datetime, timedelta
from collections.abc import Generator

from importer.data_setup import SourceInfo, ZoomSrcInfo, YTVideoSrcInfo, YTChannelSrcInfo
from utils import file_utils

from yt_dlp import YoutubeDL
import yaml
import requests


class SourceProvider:

    def __init__(self, args):
        # Take your parameters from args.
        self.args = args
    
    def get_info(self) -> Generator[SourceInfo]:
        # Get source info before go, so we can check first.
        pass

    def get_src(self, src: SourceInfo) -> bool:
        # Get source from download or somewhere else.
        return os.path.exists(src.src_fp)


class AudioSourceProvider(SourceProvider):

    def __init__(self, args):
        super().__init__(args)
        self.src_fp = args.src_fp
        self.ext = args.ext if args.ext else '.wav' # Path is dir need assign ext.
        
    def get_info(self)-> Generator[SourceInfo]:
        if os.path.isdir(self.src_fp):
            for fn in os.listdir(self.src_fp):
                if fn.endswith(self.ext):
                    yield SourceInfo(src_fp=os.path.join(self.src_fp, fn))
        else:
            yield SourceInfo(src_fp=self.src_fp)


class ZoomVideoProvider(AudioSourceProvider):
    
    def get_info(self)-> Generator[ZoomSrcInfo]:
        if os.path.isdir(self.src_fp):
            for fp in file_utils.get_all_file_with_ext(self.src_fp, '.mp4'):
                yield ZoomSrcInfo(fp)
        else:
            yield ZoomSrcInfo(self.src_fp)


class YTVideoProvider(SourceProvider):

    def __init__(self, args):
        super().__init__(args)
        self.yt_link = args.yt_link if hasattr(args, 'yt_link') else None
        self.hd_video = args.hd_video if hasattr(args, 'hd_video') else False
    
    def get_info_from_url(self, url)-> YTVideoSrcInfo:
        ydl_opts = {
            'playlist_items': '1',
            'extractor_args': {'youtubetab': {'approximate_date': ['']}},
            'writesubtitles': True,
            'subtitleslangs': ['zh-TW', 'zh-CN', 'zh', 'zh-Hans', 'zh-Hant'],
            'subtitlesformat': 'srt',
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            return YTVideoSrcInfo(self.args.proj_setup.audio_dir, info)
        
        except Exception as e:
            err_msg = str(e).lower()
            if "members-only content" in err_msg:
                print(f"The video is member-only, skip: {url}")            
            elif "channel's members" in err_msg:
                print(f"The video is member-only, skip: {url}")
            elif "live event will begin in" in err_msg:
                print(f"The live record is not ready: {url}")
            raise e

    def get_info(self)-> Generator[YTVideoSrcInfo]:
        yield self.get_info_from_url(self.args.yt_link)
    
    def get_src(self, src: YTVideoSrcInfo):
        if self.download_captions(src):
            return True
        
        if self.hd_video:
            downloaded_fp = self.download_hd_video(src)
        else:
            downloaded_fp = self.download_lowest_quality_audio(src)
        
        if not downloaded_fp or not os.path.exists(downloaded_fp):
            print("===== Download failed. =====")
            return False
        
        src.set_src_fp_same_as_srt(downloaded_fp)
        return True

    def download_captions(self, src: YTVideoSrcInfo):
        preferred_format = 'srt'
        
        # Priority order for languages (including language variants)
        preferred_langs = ['zh-TW', 'zh-CN', 'zh', 'zh-Hans', 'zh-Hant']
        
        selected_sub_info = None
        selected_lang = None

        if src.subtitles:
            print(f"Available subtitles: {list(src.subtitles.keys())}")
            for lang in preferred_langs:
                if lang in src.subtitles:
                    for sub in src.subtitles[lang]:
                        if sub.get('ext') == preferred_format:
                            selected_sub_info = sub
                            selected_lang = lang
                            break
                if selected_sub_info:
                    break
        
        if not selected_sub_info:
            print(f"No {preferred_format} subtitles found for preferred languages: {', '.join(preferred_langs)}")
            return False
            
        try:
            subtitle_url = selected_sub_info.get('url')
            if not subtitle_url:
                print(f"No URL found for {preferred_format} subtitles for language {selected_lang}")
                return False
            
            srt_path = Path(src.default_audio_fp()).with_suffix(".srt").as_posix()
            
            print(f"Downloading {selected_lang} captions from: {subtitle_url}")
            response = requests.get(subtitle_url, timeout=30)
            response.raise_for_status()
            
            with open(srt_path, 'wb') as f:
                f.write(response.content)
            
            src.srt_fp = srt_path
            print(f"Successfully downloaded {selected_lang} {preferred_format} captions to {srt_path}")
            return True

        except Exception as e:
            print(f"Failed to download {selected_lang} {preferred_format} captions: {e}")
            return False

    def download_hd_video(self, src: YTVideoSrcInfo, video_format='.mp4'):
        fp = Path(src.default_audio_fp()).with_suffix(video_format).as_posix()

        if os.path.exists(fp):
            print("Video exists: " + fp)
            return fp
        
        no_ext_fp = Path(fp).with_suffix("").as_posix()

        ydl_opts = {
            'outtmpl': no_ext_fp,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
            'merge_output_format': 'mp4',
        }

        try:
            print("Start download:", src.video_url, "\nto:", fp)
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([src.video_url])
        except Exception as e:
            print(f"Failed to download HD video: {e}")
            return None
        
        return fp

    def download_lowest_quality_audio(self, src: YTVideoSrcInfo, audio_format='.wav'):

        fp = src.default_audio_fp()

        if os.path.exists(fp):
            print("Audio exists: " + fp)
            return fp
        
        no_ext_fp = Path(fp).with_suffix("").as_posix()

        ydl_opts = {
            'outtmpl': no_ext_fp,
            'format': 'worstaudio/worst',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': audio_format.replace(".", ""),
            }],
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([src.video_url])

        except Exception as e:
            err_msg = str(e).lower()
            if "members-only content" in err_msg:
                print(f"The video is member-only, skip: {src.video_url}")
                return None
            elif "channel's members" in err_msg:
                print(f"The video is member-only, skip: {src.video_url}")
                return None
            elif "live event will begin in" in err_msg:
                print(f"The live record is not ready: {src.video_url}")
                return None
            else:
                raise e
            
        return fp


class YTChannelsLatestVideoProvider(YTVideoProvider):

    def __init__(self, args):
        super().__init__(args)
        self.args = args
        self.monitor_list_path = os.path.abspath(os.path.expanduser(args.monitor_list_path))

    def get_info(self)-> Generator[YTChannelSrcInfo]:

        with open(self.monitor_list_path, 'r') as f:
            monitor_list = yaml.load(f, Loader=yaml.BaseLoader)

        for channel_config in monitor_list:

            print("Checking: " + channel_config.get('channel_name'))

            is_live = channel_config.get("is_live", False)

            url = 'https://www.youtube.com/@{}/{}'.format(channel_config.get("username"), "streams" if is_live else "videos")

            ydl_opts = {
                'playlist_items': '1',
                'extract_flat': 'in_playlist',
                'extractor_args': {'youtubetab': {'approximate_date': ['']}},
                'writesubtitles': True,
                'subtitleslangs': ['zh-TW', 'zh-CN', 'zh', 'zh-Hans', 'zh-Hant'],
                'subtitlesformat': 'srt',
            }

            try:
                with YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

            except Exception as e:
                err_msg = str(e).lower()
                if "members-only content" in err_msg:
                    print(f"The video is member-only, skip: {url}")
                    continue
                elif "channel's members" in err_msg:
                    print(f"The video is member-only, skip: {url}")
                    continue
                
            channel_src_info = YTChannelSrcInfo(self.args.proj_setup.audio_dir, info)
            latest_video = channel_src_info.get_latest_video()

            if not latest_video:
                print(f"No latest video found for channel: {channel_config.get('channel_name')}")
                continue

            ts = latest_video.video_data.get('timestamp')
            if not ts:
                print(f"Video is not ready, skip: {latest_video.title} {latest_video.video_url}")
                continue

            pt = datetime.fromtimestamp(ts)
            
            if (datetime.today() - pt) / timedelta(hours=1) > 24:
                print(f"Video publish at {pt} is not fresh.")
                continue
            
            # If want subtitles, need to request video info again, the data in channal info is not included.
            yield latest_video

    def get_src(self, src):
        v = src
        # Video info from channel list, did not include subtitles and info is minimal, need request again.
        if not src.subtitles:
            v = self.get_info_from_url(src.video_url)
        # Member only video or other can not access.
        if not v:
            return None
        return super().get_src(v)
