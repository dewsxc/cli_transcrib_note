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

### Configuration Details

Here is a breakdown of the settings available in the configuration files:

#### `resources/config.yml`

This file contains general settings for the tool's operation.

| Key                      | Description                                       | Example                                                 |
| ------------------------ | ------------------------------------------------- | ------------------------------------------------------- |
| `work_dir`               | The root directory of the project.                | `~/AINoteWorkspace/cli_transcrib_note`                  |
| `secret`                 | Path to the `secret.yml` file.                    | `~/AINoteWorkspace/cli_transcrib_note/resources/secret.yml` |
| `ffmpeg`                 | Path to the `ffmpeg` executable.                  | `ffmpeg`                                                |
| `whisper_cpp_dir`        | Path to your `whisper.cpp` installation.          | `~/AINoteWorkspace/whisper.cpp`                         |
| `mlx_whisper_models_dir` | Path to the directory containing MLX Whisper models. | `~/AINoteWorkspace/mlx-examples/models`                 |
| `graphs`                 | A list of output locations (knowledge graphs).    |                                                         |
| `graphs.name`            | The name of a specific graph.                     | `NewsFeed`                                              |
| `graphs.path`            | The file path to the graph's directory.           | `~/Documents/NewsFeed2`                                 |

#### `resources/secret.yml`

This file is for storing your API keys and other secrets. You should create it based on `secret_example.yml`.

| Service   | Key             | Description                   |
| --------- | --------------- | ----------------------------- |
| OpenAI    | `OPENAI_KEY`    | Your API key for OpenAI.      |
| Google    | `DEVELOPER_KEY` | Your API key for Google AI.   |
| Anthropic | `ANTHROPIC_KEY` | Your API key for Anthropic.   |
| YouTube   | `YT_API_KEY`    | Your API key for YouTube Data API. |
|           | ...             | See `secret_example.yml` for the full list of YouTube-related keys. |

#### `resources/channels.yml`

This file defines the YouTube channels you want to monitor.

| Key            | Description                                           | Example                               |
| -------------- | ----------------------------------------------------- | ------------------------------------- |
| `username`     | The YouTube username of the channel.                  | `yttalkjun`                           |
| `channel_name` | The display name of the channel.                      | `投资TALK君`                          |
| `question`     | The specific prompt to use for summarizing videos.    | `列出所有重要新聞並且摘要文中對新聞的觀點以及敘述` |
| `is_live`      | (Optional) Set to `true` to fetch live streams.       | `true`                                |


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