import argparse

from setup import ServiceSetup
from importer.importer import AudioImporter, ZoomRecordImporter, YTImporter, DailyNewsImporter


def parse_args():

    p = argparse.ArgumentParser()
    p.add_argument('--setup', '-c', default="./resources/config.yml", help="Assign config file.")

    # Graph
    p.add_argument('--page', '-p', help="Save to page.")
    p.add_argument('--graph', '-g', default='NewsFeed', choices=["NewsFeed", "Trading", "Note", "Test"], help="Save to graph.")

    # Whisper
    p.add_argument('--speech-to-text', '-t', default="mlx-whisper", choices=["lightning-whisper-mlx", "mlx-whisper", "whisper.cpp", "gemini"], help="Choose speech-to-text backend for transcribing.")
    p.add_argument('--no-captions', action='store_true', help="Skip YouTube captions and force speech-to-text (whisper/gemini) instead.")
    p.add_argument('--model-size', '-s', default="large", choices=["small", "medium", "large"], help="Choose model size.")
    p.add_argument('--lang', '-l', default='zh', help="Assign detected language for transcribing.") # TODO

    # AI
    p.add_argument(
        '-a',
        '--ai-model',  
        default="gemini-2.5-flash-lite", 
        help="Only support models of Anthropic or Google.",
    )

    # Cmds
    cmd = p.add_subparsers(dest="cmd")
    
    # News
    news_args = cmd.add_parser('news', help="Loop channels for lastest video.")
    news_args.add_argument('--monitor-list-path', '-p', default="./resources/channels.yml", help="Assign channels list YAML.")
    
    # YT
    yt_args = cmd.add_parser('yt', help="Transcribe from YT video link.")
    yt_args.add_argument('yt_link', help="YT link.")
    yt_args.add_argument('--hd-video', action='store_true', help="Download video in HD quality instead of lowest quality audio.")
    yt_args.add_argument('--download-only', action='store_true', help="Download file only, skip transcription and recording.")
    yt_args.add_argument('--format', default=None, help="Output format (e.g. mp4, mp3, m4a, wav). Default: mp4.")
    yt_args.add_argument('--audio-only', action='store_true', help="Download audio stream only.")
    yt_args.add_argument('--output', '-o', default=None, help="Output directory for downloaded file. Defaults to audio_dir in config.")
    yt_args.add_argument('--quality', '-q', default='high', choices=['lowest', 'mid', 'high'], help="Download quality: lowest, mid, high (default: high).")
    
    # Audio or Video
    audio_args = cmd.add_parser('audio', help="Transcrobe from Audio or Video path, support directory.")
    audio_args.add_argument('src_fp', help="Source file path.")
    audio_args.add_argument('--ext', '-t', default='.mp4', help="Audio or Video file extension.")

    # Zoom
    zoom_args = cmd.add_parser('zoom', help="Transcribing from Zoom record.")
    zoom_args.add_argument('src_fp', help="Source file path or directory, it will find matched file recursively.")

    args = p.parse_args()
    args.proj_setup = ServiceSetup(args.setup)

    return args


def main():

    args = parse_args()
        
    importers = {
        'audio': AudioImporter,
        'zoom': ZoomRecordImporter,
        'yt': YTImporter,
        'news': DailyNewsImporter,
    }    
    Importer = importers.get(args.cmd)

    if not Importer:
        return
    
    Importer(args).start_import()
    

if __name__ == "__main__":
    main()
