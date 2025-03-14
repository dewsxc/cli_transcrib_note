# CLI Transcription and Summarization Tool

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

### Dependencies
- yt-dlp
- zhconv
- pyyaml
- google-api-python-client
- google-cloud-aiplatform
- anthropic
- mlx-whisper

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
