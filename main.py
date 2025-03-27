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
    p.add_argument('--speech-to-text', '-t', default='mlx-whisper', choices=["mlx-whisper", "whisper.cpp"], help="Choose whisper models for trascribing.")
    p.add_argument('--model-size', '-s', default="small", choices=["small", "medium", "large"], help="Choose model size.")
    p.add_argument('--lang', '-l', default='zh', help="Assign detected language for transcribing.") # TODO

    # AI
    p.add_argument('--ai-model', '-a', default="claude-3-haiku-20240307", choices=["claude-3-haiku-20240307", "claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022"], help="Only implement Anthropic.")


    # Cmds
    cmd = p.add_subparsers(dest="cmd")
    
    # News
    news_args = cmd.add_parser('news', help="Loop channels for lastest video.")
    news_args.add_argument('--monitor-list-path', '-p', default="./resources/channels.yml", help="Assign channels list YAML.")
    
    # YT
    yt_args = cmd.add_parser('yt', help="Transcribe from YT video link.")
    yt_args.add_argument('yt_link', help="YT link.")

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