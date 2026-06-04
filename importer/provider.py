import os
from pathlib import Path
from datetime import datetime, timedelta
from collections.abc import Generator

from importer.data_setup import SourceInfo, ZoomSrcInfo, YTVideoSrcInfo, YTChannelSrcInfo
from utils import file_utils, content_utils

from yt_dlp import YoutubeDL
import yaml
import requests


# YouTube now hides formats and caption tracks behind a JS challenge; yt-dlp
# needs a JS runtime plus the yt-dlp-ejs solver to extract them. Prefer deno
# (yt-dlp's default), fall back to node. See run_boy.sh / README for install.
_JS_RUNTIMES = {'deno': {'path': None}, 'node': {'path': None}}


def _ydl(opts):
    """YoutubeDL with the JS runtimes needed to solve YouTube's challenges."""
    opts.setdefault('js_runtimes', _JS_RUNTIMES)
    return YoutubeDL(opts)


class SourceProvider:

    def __init__(self, args):
        # Take your parameters from args.
        self.args = args
    
    def get_info(self) -> Generator[SourceInfo]:
        # Get source info before go, so we can check first.
        pass

    def get_src(self, src: SourceInfo):
        # Get source from download or somewhere else.
        return src


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
        self.no_captions = getattr(args, 'no_captions', False)
    
    # Priority order for languages (including language variants)
    _PREFERRED_LANGS = ['zh-TW', 'zh-CN', 'zh', 'zh-Hans', 'zh-Hant']

    def _caption_langs(self, src: YTVideoSrcInfo = None, extra_lang: str = None):
        """Return subtitle languages to request/search, preserving order and removing duplicates."""
        langs = []

        # Per-channel language from channels.yml should be considered when available.
        if extra_lang:
            langs.append(extra_lang)
        if src and getattr(src, 'lang', None):
            langs.append(src.lang)

        langs.extend(self._PREFERRED_LANGS)
        return list(dict.fromkeys(lang for lang in langs if lang))

    def get_info_from_url(self, url, caption_lang: str = None)-> YTVideoSrcInfo:
        ydl_opts = {
            'playlist_items': '1',
            'extractor_args': {'youtubetab': {'approximate_date': ['']}},
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': self._caption_langs(extra_lang=caption_lang),
            'subtitlesformat': 'srt',
        }

        try:
            with _ydl(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            src = YTVideoSrcInfo(self.args.proj_setup.audio_dir, info)
            if caption_lang:
                src.lang = caption_lang
            return src
        
        except Exception as e:
            err_msg = str(e).lower()
            if "members-only content" in err_msg:
                print(f"The video is member-only, skip: {url}")
                return None
            elif "channel's members" in err_msg:
                print(f"The video is member-only, skip: {url}")
                return None
            elif "live event will begin in" in err_msg:
                print(f"The live record is not ready: {url}")
                return None
            raise e

    def get_info(self)-> Generator[YTVideoSrcInfo]:
        yield self.get_info_from_url(self.args.yt_link)
    
    def get_src(self, src: YTVideoSrcInfo):
        # Prefer existing captions (manual > auto) before paying for STT.
        # --hd-video wants the video file; --no-captions forces STT.
        if not self.hd_video and not self.no_captions and self.download_captions(src):
            return src

        # No captions: fall back to STT. --speech-to-text selects the backend.
        if self.hd_video:
            downloaded_fp = self.download_hd_video(src)
        elif getattr(self.args, 'speech_to_text', None) == 'gemini':
            downloaded_fp = self.download_lowest_quality_audio(src, audio_format=None)
        else:
            downloaded_fp = self.download_lowest_quality_audio(src)

        if not downloaded_fp or not os.path.exists(downloaded_fp):
            print("===== Download failed. =====")
            return None

        src.set_src_fp_same_as_srt(downloaded_fp)
        return src

    def download_captions(self, src: YTVideoSrcInfo):
        caption_langs = self._caption_langs(src)
        # 1) Manually-uploaded subtitles (best quality).
        if self.download_manual_captions(src, caption_langs):
            return True
        # 2) Auto-generated captions (fallback before paying for STT).
        if self.download_auto_captions(src, caption_langs):
            return True
        print("No manual or automatic captions found for preferred languages: "
              f"{', '.join(caption_langs)}")
        return False

    def download_manual_captions(self, src: YTVideoSrcInfo, caption_langs=None):
        preferred_format = 'srt'
        caption_langs = caption_langs or self._caption_langs(src)

        selected_sub_info = None
        selected_lang = None

        if src.subtitles:
            print(f"Available subtitles: {list(src.subtitles.keys())}")
            for lang in caption_langs:
                if lang in src.subtitles:
                    for sub in src.subtitles[lang]:
                        if sub.get('ext') == preferred_format:
                            selected_sub_info = sub
                            selected_lang = lang
                            break
                if selected_sub_info:
                    break

        if not selected_sub_info:
            return False

        try:
            subtitle_url = selected_sub_info.get('url')
            if not subtitle_url:
                print(f"No URL found for {preferred_format} subtitles for language {selected_lang}")
                return False

            print(f"Downloading {selected_lang} captions from: {subtitle_url}")
            response = requests.get(subtitle_url, timeout=30)
            response.raise_for_status()

            with open(src.srt_fp, 'wb') as f:
                f.write(response.content)
            content_utils.s_to_t(src.srt_fp)
            print(f"Successfully downloaded {selected_lang} {preferred_format} captions to {src.srt_fp}")
            return True

        except Exception as e:
            print(f"Failed to download {selected_lang} {preferred_format} captions: {e}")
            return False

    def download_auto_captions(self, src: YTVideoSrcInfo, caption_langs=None):
        auto = getattr(src, 'automatic_captions', None)
        if not auto:
            return False
        caption_langs = caption_langs or self._caption_langs(src)

        print(f"Available auto-captions: {list(auto.keys())}")

        selected_sub_info = None
        selected_lang = None
        for lang in caption_langs:
            subs = auto.get(lang)
            if not subs:
                continue
            # Auto-captions are not offered as srt; prefer vtt, else first available.
            selected_sub_info = next((s for s in subs if s.get('ext') == 'vtt'), subs[0])
            selected_lang = lang
            break

        if not selected_sub_info:
            return False

        subtitle_url = selected_sub_info.get('url')
        if not subtitle_url:
            print(f"No URL found for auto-captions for language {selected_lang}")
            return False

        selected_ext = selected_sub_info.get('ext')
        try:
            print(f"Downloading {selected_lang} auto-captions ({selected_ext}) from: {subtitle_url}")
            response = requests.get(subtitle_url, timeout=30)
            response.raise_for_status()

            srt_content = content_utils.vtt_to_srt(response.text) if selected_ext == 'vtt' else response.text
            if not srt_content.strip():
                print(f"Auto-captions for {selected_lang} converted to empty content, skip.")
                return False

            with open(src.srt_fp, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            content_utils.s_to_t(src.srt_fp)
            print(f"Successfully saved {selected_lang} auto-captions to {src.srt_fp}")
            return True

        except Exception as e:
            print(f"Failed to download {selected_lang} auto-captions: {e}")
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
            with _ydl(ydl_opts) as ydl:
                ydl.download([src.video_url])
        except Exception as e:
            print(f"Failed to download HD video: {e}")
            return None
        
        return fp

    def download_lowest_quality_audio(self, src: YTVideoSrcInfo, audio_format='.wav'):
        """Download lowest quality audio. Pass audio_format=None to keep the original format (no FFmpeg conversion)."""

        base_no_ext = Path(src.default_audio_fp()).with_suffix("").as_posix()

        if audio_format is None:
            # Raw mode: keep native format, capture actual filename via hook.
            downloaded_fp = [None]

            def progress_hook(d):
                if d['status'] == 'finished':
                    downloaded_fp[0] = d.get('filename')

            ydl_opts = {
                'outtmpl': base_no_ext + '.%(ext)s',
                'format': 'worstaudio/worst',
                'progress_hooks': [progress_hook],
            }
        else:
            fp = src.default_audio_fp()
            if os.path.exists(fp):
                print("Audio exists: " + fp)
                return fp

            ydl_opts = {
                'outtmpl': base_no_ext,
                'format': 'worstaudio/worst',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': audio_format.replace(".", ""),
                }],
            }

        try:
            with _ydl(ydl_opts) as ydl:
                ydl.download([src.video_url])

        except Exception as e:
            err_msg = str(e).lower()
            if "members-only content" in err_msg or "channel's members" in err_msg:
                print(f"The video is member-only, skip: {src.video_url}")
                return None
            elif "live event will begin in" in err_msg:
                print(f"The live record is not ready: {src.video_url}")
                return None
            else:
                raise e

        return downloaded_fp[0] if audio_format is None else fp

    _AUDIO_QUALITY_FMT = {
        'lowest': 'worstaudio/worst',
        'mid':    'bestaudio[abr<=128]/bestaudio',
        'high':   'bestaudio/best',
    }
    _VIDEO_QUALITY_FMT = {
        'lowest': 'worstvideo+worstaudio/worst',
        'mid':    'bestvideo[height<=480]+bestaudio/best[height<=480]/best',
        'high':   None,  # filled in per-container below
    }

    def download_with_format(self, src: YTVideoSrcInfo, fmt: str = None, audio_only: bool = False, output_dir: str = None, quality: str = 'high') -> str:
        base_fp = Path(src.default_audio_fp())
        if output_dir:
            out_dir = Path(os.path.expanduser(output_dir))
            out_dir.mkdir(parents=True, exist_ok=True)
            base_fp = out_dir / base_fp.name

        if audio_only:
            codec = fmt or 'mp4'
            fp = base_fp.with_suffix(f'.{codec}').as_posix()
            if os.path.exists(fp):
                print("File exists: " + fp)
                return fp
            ydl_opts = {
                'outtmpl': Path(fp).with_suffix("").as_posix(),
                'format': self._AUDIO_QUALITY_FMT.get(quality, 'bestaudio/best'),
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': codec}],
            }
        else:
            container = fmt or 'mp4'
            fp = base_fp.with_suffix(f'.{container}').as_posix()
            if os.path.exists(fp):
                print("File exists: " + fp)
                return fp
            if quality == 'high':
                video_fmt = f'bestvideo[ext={container}]+bestaudio[ext=m4a]/bestvideo+bestaudio/best'
            else:
                video_fmt = self._VIDEO_QUALITY_FMT.get(quality, 'bestvideo+bestaudio/best')
            ydl_opts = {
                'outtmpl': Path(fp).with_suffix("").as_posix(),
                'format': video_fmt,
                'merge_output_format': container,
            }
        try:
            print("Start download:", src.video_url, "\nto:", fp)
            with _ydl(ydl_opts) as ydl:
                ydl.download([src.video_url])
        except Exception as e:
            print(f"Failed to download: {e}")
            return None
        return fp


class YTChannelsLatestVideoProvider(YTVideoProvider):

    def __init__(self, args):
        super().__init__(args)
        self.args = args
        self.monitor_list_path = os.path.abspath(os.path.expanduser(args.monitor_list_path))
        self.current_channel_config = None

    def get_info(self)-> Generator[YTChannelSrcInfo]:

        with open(self.monitor_list_path, 'r') as f:
            monitor_list = yaml.load(f, Loader=yaml.BaseLoader)

        for channel_config in monitor_list:

            print("Checking: " + channel_config.get('channel_name'))
            self.current_channel_config = channel_config
            channel_lang = channel_config.get('lang', 'zh')
            
            is_live = channel_config.get("is_live", False)

            url = 'https://www.youtube.com/@{}/{}'.format(channel_config.get("username"), "streams" if is_live else "videos")

            ydl_opts = {
                'playlist_items': '1',
                'extract_flat': 'in_playlist',
                'extractor_args': {'youtubetab': {'approximate_date': ['']}},
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': self._caption_langs(extra_lang=channel_lang),
                'subtitlesformat': 'srt',
            }

            try:
                with _ydl(ydl_opts) as ydl:
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
            
            latest_video.lang = channel_lang
            # If want subtitles, need to request video info again, the data in channal info is not included.
            yield latest_video

        self.current_channel_config = None

    def get_src(self, src):
        v = src
        # Video info from channel list, did not include subtitles and info is minimal, need request again.
        if not src.subtitles:
            v = self.get_info_from_url(src.video_url, caption_lang=src.lang)
        # Member only video or other can not access.
        if not v:
            return None
        else:
            # Swap info.
            v.lang = src.lang
        return super().get_src(v)

    def get_prompt(self, src):
        return self.current_channel_config.get('question')
