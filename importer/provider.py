import os
from pathlib import Path
from datetime import datetime, timedelta
from collections.abc import Generator

from importer.data_setup import SourceInfo, ZoomSrcInfo, YTSrcInfo, YTChannalSrcInfo
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
        self.yt_link = args.yt_link
        self.hd_video = args.hd_video if hasattr(args, 'hd_video') else False

    def get_info(self)-> Generator[YTSrcInfo]:

        ydl_opts = {
            'playlist_items': '1',
            'extractor_args': {'youtubetab': {'approximate_date': ['']}},
            'writesubtitles': True,
            'subtitleslangs': ['zh'],
            'subtitlesformat': 'srt',
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.args.yt_link, download=False)

            yield YTSrcInfo(self.args.proj_setup.audio_dir, video_info=info)
        
        except Exception as e:
            err_msg = str(e).lower()
            if "members-only content" in err_msg:
                print("The video is member-only, skip: {}".format(self.yt_link))            
            elif "channel's members" in err_msg:
                print("The video is member-only, skip: {}".format(self.yt_link))
            elif "live event will begin in" in err_msg:
                print("The live record is not ready: {}".format(self.yt_link))
            return
        
    def get_src(self, src: YTSrcInfo):
        if self.download_captions(src):
            return True
        
        if self.hd_video:
            downloaded_fp = self.download_hd_video(src)
        else:
            downloaded_fp = self.download_lowest_quality_audio(src)
        
        if not downloaded_fp or not os.path.exists(downloaded_fp):
            print("===== Download failed. =====")
            return False
        
        src.set_src_fp_same_as_srt(downloaded_fp) # Ensure srt_fp is updated based on the downloaded file
        return True

    def download_captions(self, src: YTSrcInfo):
        if src.video_info.get('requested_subtitles'):
            for lang in ['zh']:
                if lang in src.video_info['requested_subtitles']:
                    subtitle_url = src.video_info['requested_subtitles'][lang]['url']
                    srt_path = Path(src.default_audio_fp()).with_suffix(f".{lang}.srt").as_posix()
                    try:
                        # Use requests to download the subtitle file
                        response = requests.get(subtitle_url)
                        response.raise_for_status() # Raise an exception for HTTP errors
                        with open(srt_path, 'wb') as f:
                            f.write(response.content)
                        src.srt_fp = srt_path # Update src.srt_fp to the downloaded srt
                        print(f"Downloaded {lang} captions to {srt_path}")
                        return True
                    except Exception as e:
                        print(f"Failed to download {lang} captions: {e}")
        else:
            print("No subtitles.")
        return False

    def download_hd_video(self, src: YTSrcInfo, video_format='.mp4'):
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

    def download_lowest_quality_audio(self, src: YTSrcInfo, audio_format='.wav'):

        fp = src.default_audio_fp()

        if os.path.exists(fp):
            print("Audio exists: " + fp)
            return fp
        
        # The ydl will transform audio format as you assign, if your fp has ext in path, ydl will append ext directly.
        # Like input: aaa.wav
        # In result: aaa.wav.wav
        no_ext_fp = Path(fp).with_suffix("").as_posix()

        ydl_opts = {
            'outtmpl': no_ext_fp,
            'format': 'worstaudio/worst',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': audio_format.replace(".", ""), # Remove '.' for user to keep consistency of meaning.
            }],
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([src.video_url])

        except Exception as e:
            err_msg = str(e).lower()
            if "members-only content" in err_msg:
                print("The video is member-only, skip: {}".format(src.video_url))
                return None
            elif "channel's members" in err_msg:
                print("The video is member-only, skip: {}".format(src.video_url))
                return None
            elif "live event will begin in" in err_msg:
                print("The live record is not ready: {}".format(src.video_url))
                return None
            else:
                raise e
            
        return fp


class YTChannelsLatestVideoProvider(YTVideoProvider):

    def __init__(self, args):
        self.args = args
        self.monitor_list_path = os.path.abspath(os.path.expanduser(args.monitor_list_path))

    def get_info(self)-> Generator[YTChannalSrcInfo]:

        with open(self.monitor_list_path, 'r') as f:
            monitor_list = yaml.load(f, Loader=yaml.BaseLoader)

        for data in monitor_list:

            print("Checking: " + data.get('channel_name'))

            is_live = data.get("is_live", False)

            url = 'https://www.youtube.com/@{}/{}'.format(data.get("username"), "streams" if is_live else "videos")

            ydl_opts = {
                'playlist_items': '1',
                'extract_flat': 'in_playlist',
                'extractor_args': {'youtubetab': {'approximate_date': ['']}}
            }

            try:
                with YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

            except Exception as e:
                err_msg = str(e).lower()
                if "members-only content" in err_msg:
                    print("The video is member-only, skip: {}".format(url))
                    continue
                elif "channel's members" in err_msg:
                    print("The video is member-only, skip: {}".format(url))
                    continue
                
            first_v_info = info['entries'][0]
            ts = first_v_info.get('timestamp')
            if not ts:
                print("Video is not ready, skip: {} {}".format(first_v_info.get("title"), first_v_info.get("url")))
                continue

            pt = datetime.fromtimestamp(ts)
            
            if (datetime.today() - pt) / timedelta(hours=1) > 24:
                print("Video publish at {} is not fresh.".format(pt))
                continue

            yield YTChannalSrcInfo(
                self.args.proj_setup.audio_dir,
                data, 
                channel_info=info,
            )