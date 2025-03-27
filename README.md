# CLI Transcription and Summarization Tool

This project meant to scan all channels I monitored on Youtube and sent summarize into my Logseq or Obsidian knoledge base, so that I won't need to spend lots of time for listening, just read summarize and search I need in transcription, life saver.

The output files I put on iCloud, so I can read it on my iPhone, recommand use Obsidian as frontend reader, the sync and read experience better than Loqseg, but Logseq is greater than Obsidian on manage knowledge, so I keep naming style and path for Loqseq.

It can input audio or video or zoom record as well.

This project is still on refactoring, you will see lots options still on implement like support Gemini or Whisper.cpp, but it can work with MLX and Claude option, the combination is best for saving money and work on Macbook air.


## Overview

This CLI tool provides a comprehensive solution for transcribing and summarizing audio and video content from multiple sources, including:
- Local audio/video files
- Zoom recordings
- YouTube videos
- YouTube news channels

The tool supports multiple features:
- Speech-to-text transcription using Whisper models
- AI-powered summarization with Claude models
- Flexible output options (different graph/page destinations)
- Support for multiple languages

## Features

### Supported Sources
- Local audio/video files
- Zoom recordings
- YouTube videos
- YouTube news channels

### Transcription Options
- Speech-to-text models:
  - MLX Whisper: This is more suitable for run on your laptop, it won't occupied resources and slow down other service, it can run on background without notice and faster compare to whisper.cpp.
  - whisper.cpp: This model is great, but will comsume all resoureces.
- Model sizes: small, medium, large
- Language detection support

### AI Summarization
- The Anthropic Claude series are cheap and summary quality are great compare with others.
- Supported AI Models:
  - Claude 3 Haiku
  - Claude 3.5 Haiku
  - Claude 3.5 Sonnet

The most suitable in Traditional Chinese context is Claude 3 Haiku, fast, cheap and good quality, but it must sent all prompt, include init prompt, transcription at once, if not, the quality drop very crazy.
The Claude 3.5 Haiku is good quality without any tricks but lack of detail, the Gemini is too creative for summarizing, ChatGPT is too expensive considered quality.


### Output Options
- Save summaries to specific pages
- Multiple graph destinations:
  - NewsFeed
  - Trading
  - Note
  - Test

## Prerequisites

### System Requirements
- Python 3.8+
- FFmpeg
- Whisper.cpp (optional)


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

## Usage

### General Command Structure
```bash
python main.py [global_options] <command> [command_options]
```

### Commands

#### Transcribe Local Audio/Video
```bash
python main.py audio /path/to/audio/or/video
```

#### Transcribe Zoom Recording
```bash
python main.py zoom /path/to/zoom/recording
```

#### Transcribe YouTube Video
```bash
python main.py yt [YouTube_URL]
```

#### Monitor News Channels
```bash
python main.py news
```

### Global Options

- `--setup`: Custom config file path
- `--page`: Specify output page
- `--graph`: Choose output graph (NewsFeed, Trading, Note, Test)
- `--speech-to-text`: Choose transcription model (mlx-whisper, whisper.cpp)
- `--model-size`: Whisper model size (small, medium, large)
- `--lang`: Language for transcription
- `--ai-model`: Choose AI summarization model

## Configuration

### Config File (`config.yml`)
- Specify root directory
- Configure FFmpeg path
- Set Whisper.cpp directory
- Define graph configurations

### Secret File (`secret.yml`)
- Store API keys:
  - OpenAI
  - YouTube Developer Key
  - Google Cloud Project ID
  - Anthropic API Key

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

[Specify your license here]

## Disclaimer

This tool is for educational and personal use. Ensure compliance with terms of service for transcribed content sources.
