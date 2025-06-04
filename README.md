# CLI Transcription and Summarization Tool


## Overview

This project meant to scan all channels I monitored on YT and sent summarize into my Logseq or Obsidian knoledge base, so that I won't need to spend lots of time for listening, just read summarize and search I need in transcription, life saver.

This CLI tool can input audio or video or zoom record as well.

This project is still on refactoring, you will see lots options still on implement like support Gemini or Whisper.cpp, but it can work with MLX and Claude option, the combination is best for saving money and work on Macbook air.


## Features

### Supported Sources
- Local audio/video files
- Zoom recordings
- YouTube videos
- YouTube news channels

### Speec-to-Text

Using web services are very expensive, if you use Apple Silicon Chip series product, should try transcribing on your computer.
- MLX Whisper: This is more suitable for run on your laptop, it won't occupied resources and slow down other service, it can run on background without notice and faster compare to whisper.cpp.
  - [Download from Hugging Face - MXL Community](https://huggingface.co/collections/mlx-community/whisper-663256f9964fbb1177db93dc)
- whisper.cpp: This model is great, but will comsume all resoureces.
  - [Pull from github](https://github.com/ggerganov/whisper.cpp)

### AI Summarization
- The Anthropic Claude series are cheap and quality are great compare with others. 


### Output Options
- The output files I put on iCloud, so I can read it on my iPhone, recommand use Obsidian as frontend reader, the sync and read experience better than Loqseg.
- The path construct is follow Logseq, which is greater than Obsidian on manage knowledge, so I keep naming style for it.


## Prerequisites

### System Requirements
- Python 3.8+
- FFmpeg
- MXL Whisper model
- Whisper.cpp (optional)
- Anthropic Service


## Installation

1. Clone the repository
```bash
git clone https://github.com/yourusername/cli-transcribe-note.git
cd cli-transcribe-note
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Configure the tool
- Create a `config.yml` in `./resources/` directory
- Create a `secret.yml` with necessary API keys


## Configuration

- Remember to config following files:
  - `config.yml`: For all kinds of setup
  - `secret.yml`: Setup keys for ai model services.
  - `channels.yml`: The yt channels you want to monitor.


## Usage

Scan all channels:
```
  python main.py news
```

Transcribe yt video:
```
  python main.py yt "YT Video Link"
```

Use `python main.py -h` for more commands.


## License

[Specify your license here]

## Disclaimer

This tool is for educational and personal use. Ensure compliance with terms of service for transcribed content sources.
