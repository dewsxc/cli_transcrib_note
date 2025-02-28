import os
from datetime import datetime, timedelta
from collections.abc import Generator

from importer.data_setup import SourceInfo, ZoomSrcInfo, YTSrcInfo, YTChannalSrcInfo
from utils import file_utils

from yt_dlp import YoutubeDL
import yaml


class SourceProvider:
    # Should be constrainted as iterable.
    def __init__(self, args):
        self.args = args
    
    def get_src(self) -> Generator[SourceInfo]:
        pass

    def clean_up(self):
        pass


class AudioSourceProvider(SourceProvider):

    def __init__(self, args):
        super().__init__(args)
        self.src_fp = args.src_fp
        self.ext = args.ext if args.ext else '.wav' # Path is dir need assign ext.
        
    def get_src(self)-> Generator[SourceInfo]:
        if os.path.isdir(self.src_fp):
            for fn in os.listdir(self.src_fp):
                if fn.endswith(self.ext):
                    yield SourceInfo(src_fp=os.path.join(self.src_fp, fn))
        else:
            yield SourceInfo(src_fp=self.src_fp)

        self.clean_up()


class ZoomVideoProvider(AudioSourceProvider):
    
    def get_src(self)-> Generator[ZoomSrcInfo]:
        if os.path.isdir(self.src_fp):
            for fp in file_utils.get_all_file_with_ext(self.src_fp, '.mp4'):
                yield ZoomSrcInfo(fp)
        else:
            yield ZoomSrcInfo(self.src_fp)


class YTVideoProvider(SourceProvider):

    def __init__(self, args):
        super().__init__(args)
        self.yt_link = args.yt_link

    def get_src(self)-> Generator[YTSrcInfo]:

        ydl_opts = {
            'playlist_items': '1',
            # 'extract_flat': 'in_playlist',
            'extractor_args': {'youtubetab': {'approximate_date': ['']}}
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(self.args.yt_link, download=False)

        yield YTSrcInfo(self.args.proj_setup.audio_dir, video_info=info)


class YTChannelsLatestVideoProvider(SourceProvider):

    def __init__(self, args):
        super().__init__(args)
        self.monitor_list_path = args.monitor_list_path

    def get_src(self)-> Generator[YTChannalSrcInfo]:

        with open(self.monitor_list_path, 'r') as f:
            monitor_list = yaml.load(f, Loader=yaml.BaseLoader)

        for data in monitor_list:

            print("Checking: " + data.get('channel_name'))

            url = 'https://www.youtube.com/@{}/videos'.format(data.get("username"))

            ydl_opts = {
                'playlist_items': '1',
                'extract_flat': 'in_playlist',
                'extractor_args': {'youtubetab': {'approximate_date': ['']}}
            }

            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
            first_v_info = info['entries'][0]
            ts = first_v_info.get('timestamp')
            if not ts:
                ts = first_v_info.get('release_timestamp')

            pt = datetime.fromtimestamp(ts)
            
            if (datetime.today() - pt) / timedelta(hours=1) > 24:
                print("Video publish at {} is not fresh.".format(pt))
                continue

            yield YTChannalSrcInfo(
                self.args.proj_setup.audio_dir,
                data, 
                channel_info=info,
            )